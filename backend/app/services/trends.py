"""Trend, anomaly and seasonality intelligence for the burning calendar.

Three questions are answered with three different methods, and never blended into
one number:

* **Trend** — Theil–Sen slope over *observed* days. Gaps are excluded, never
  filled with zeros, so a missing day cannot bend the line.
* **Anomalies** — the robust-z engine in :mod:`app.services.anomalies`, reused
  here and surfaced per day so the calendar can mark the cells.
* **Seasonality** — per calendar-month means computed across years, with an
  explicit gate: one year is a profile, not a climatology. Fewer than two years
  of history returns ``single_year`` and no seasonal index is invented.

Every result states what it could not measure. A window with too few observed
days returns ``insufficient_history`` rather than a confident-looking flat line.

Counts are detections, not fires.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from math import ceil
from statistics import fmean, median
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.services.anomalies import detect_anomalies, observed_days
from app.services.calendar import MAX_SPAN_DAYS, daily_metrics
from app.services.observation_queries import ObservationFilters

METHOD_VERSION = "calendar-intel-v1"

#: Below this many observed days the trend is reported as insufficient.
TREND_MIN_OBSERVATIONS = 10
#: Trailing mean over this many *observed* days (gaps skipped, not zero-filled).
SMOOTHING_OBSERVATIONS = 7
#: Pairwise-slope budget for Theil–Sen; larger windows are deterministically thinned.
MAX_PAIRWISE_SLOPES = 250_000
#: A seasonal pattern needs at least this many distinct years.
SEASON_MIN_YEARS = 2
#: A month counts as covered in a year only with this many observed days.
SEASON_MIN_DAYS_PER_MONTH_YEAR = 5
#: Months with enough multi-year support before peak/trough are declared.
SEASON_MIN_SUFFICIENT_MONTHS = 9

METRIC_FIELDS = {
    "detections": "detections",
    "frp": "frp_sum_mw",
    "high_confidence": "high_confidence",
}
MONTH_LABELS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def _metric_field(metric: str) -> str:
    return METRIC_FIELDS.get(metric, "detections")


def theil_sen(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """
    Robust slope from the median of pairwise slopes.

    A least-squares line is dragged by one huge fire day; the median slope is
    not. Windows too large for every pair are thinned with a fixed stride, which
    keeps the estimate deterministic instead of random.
    """
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, float(ys[0])

    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)

    pairs = n * (n - 1) // 2
    if pairs > MAX_PAIRWISE_SLOPES:
        stride = int(ceil((pairs / MAX_PAIRWISE_SLOPES) ** 0.5))
        x = x[::stride]
        y = y[::stride]
        if len(x) < 2:  # pragma: no cover - pathological tiny window
            return 0.0, float(median(ys))

    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    valid = dx != 0
    if not valid.any():  # pragma: no cover - all points share one x value
        return 0.0, float(median(y))
    slopes = (y[j] - y[i])[valid] / dx[valid]
    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    return slope, intercept


def trailing_mean(values: list[float | None], window: int = SMOOTHING_OBSERVATIONS) -> list:
    """Trailing mean over observed values; a gap stays a gap, it does not enter."""
    out: list[float | None] = []
    recent: list[float] = []
    for value in values:
        if value is None:
            out.append(None)
            continue
        recent.append(value)
        if len(recent) > window:
            recent.pop(0)
        out.append(round(fmean(recent), 3))
    return out


def _trend_block(
    series: list[dict[str, Any]], metric: str
) -> dict[str, Any]:
    observed = [point for point in series if point["value"] is not None]
    total_days = len(series)
    observed_days_count = len(observed)
    coverage = observed_days_count / total_days if total_days else 0.0

    if observed_days_count < TREND_MIN_OBSERVATIONS:
        return {
            "status": "insufficient_history",
            "method": "theil-sen",
            "version": METHOD_VERSION,
            "metric": metric,
            "observations": observed_days_count,
            "slope_per_day": None,
            "slope_per_30_days": None,
            "direction": "unknown",
            "change_ratio": None,
            "confidence": "low",
            "coverage": round(coverage, 4),
            "requirements": {
                "needed_observations": TREND_MIN_OBSERVATIONS,
                "available_observations": observed_days_count,
                "note": (
                    "A trend needs at least "
                    f"{TREND_MIN_OBSERVATIONS} observed days; this window has "
                    f"{observed_days_count}. Missing days are not filled with zeros."
                ),
            },
        }

    xs = [float(index) for index, _ in enumerate(observed)]
    ys = [float(point["value"]) for point in observed]
    slope, _ = theil_sen(xs, ys)

    values = [point["value"] for point in observed]
    level = float(median(values))
    slope_30 = slope * 30.0
    flat_band = max(1.0, 0.05 * abs(level))
    direction = (
        "flat"
        if abs(slope_30) <= flat_band
        else "rising" if slope_30 > 0 else "falling"
    )

    first_mean = fmean(values[:SMOOTHING_OBSERVATIONS])
    last_mean = fmean(values[-SMOOTHING_OBSERVATIONS:])
    change_ratio = round(last_mean / first_mean, 4) if first_mean else None

    if observed_days_count < 21 or coverage < 0.5:
        confidence = "low"
    elif observed_days_count < 60 or coverage < 0.8:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "status": "ok",
        "method": "theil-sen",
        "version": METHOD_VERSION,
        "metric": metric,
        "observations": observed_days_count,
        "slope_per_day": round(slope, 4),
        "slope_per_30_days": round(slope_30, 3),
        "direction": direction,
        "change_ratio": change_ratio,
        "confidence": confidence,
        "coverage": round(coverage, 4),
        "level_median": round(level, 3),
        "flat_band_per_30_days": round(flat_band, 3),
        "requirements": {
            "needed_observations": TREND_MIN_OBSERVATIONS,
            "available_observations": observed_days_count,
            "note": "Requirement satisfied.",
        },
    }


def _seasonality_block(
    daily: dict[date, dict[str, Any]],
    observed: set[date],
    *,
    first_year: int,
    last_year: int,
    metric: str,
) -> dict[str, Any]:
    """
    Per calendar-month means across years, with a hard sufficiency gate.

    A month's value is the mean of its **yearly monthly means**, so a year with
    twice as many observed days does not dominate. A month is only used when at
    least :data:`SEASON_MIN_YEARS` years each observed it on at least
    :data:`SEASON_MIN_DAYS_PER_MONTH_YEAR` days.
    """
    field = _metric_field(metric)
    per_year_month: dict[tuple[int, int], list[float]] = {}
    observed_years: set[int] = set()

    for day in sorted(observed):
        if day.year < first_year or day.year > last_year:
            continue
        observed_years.add(day.year)
        value = float(daily.get(day, {}).get(field, 0.0))
        per_year_month.setdefault((day.year, day.month), []).append(value)

    months: list[dict[str, Any]] = []
    for month in range(1, 13):
        year_means: list[float] = []
        for year in range(first_year, last_year + 1):
            values = per_year_month.get((year, month), [])
            if len(values) >= SEASON_MIN_DAYS_PER_MONTH_YEAR:
                year_means.append(fmean(values))
        sufficient = len(year_means) >= SEASON_MIN_YEARS
        months.append(
            {
                "month": month,
                "label": MONTH_LABELS[month - 1],
                "mean": round(fmean(year_means), 3) if year_means else None,
                "years": len(year_means),
                "sufficient": sufficient,
                "index": None,
            }
        )

    sufficient_months = [entry for entry in months if entry["sufficient"]]
    baseline = (
        fmean([entry["mean"] for entry in sufficient_months])
        if sufficient_months
        else None
    )

    for entry in months:
        if entry["sufficient"] and baseline:
            entry["index"] = round(float(entry["mean"]) / baseline, 4)

    if not observed_years:
        status = "insufficient_history"
    elif len(observed_years) < SEASON_MIN_YEARS:
        status = "single_year"
    elif len(sufficient_months) >= SEASON_MIN_SUFFICIENT_MONTHS:
        status = "ok"
    else:
        status = "partial"

    peak = trough = amplitude = None
    if status == "ok":
        ranked = sorted(sufficient_months, key=lambda entry: float(entry["index"]))
        trough, peak = ranked[0], ranked[-1]
        if trough["index"] and trough["index"] > 0:
            amplitude = round(float(peak["index"]) / float(trough["index"]), 3)

    if status == "ok" and len(observed_years) == 2:
        note = (
            "Two years is the minimum for a seasonal comparison; treat the profile "
            "as preliminary until a third year confirms it."
        )
    elif status == "single_year":
        note = (
            "Only one year of history is available. The monthly profile describes "
            "that year; it is not a seasonal climatology and no seasonal index, "
            "peak or trough is claimed."
        )
    elif status == "partial":
        note = (
            f"{len(sufficient_months)} of 12 months have at least "
            f"{SEASON_MIN_YEARS} years of coverage. The profile is shown for those "
            "months only; peak and trough are withheld until at least "
            f"{SEASON_MIN_SUFFICIENT_MONTHS} months qualify."
        )
    elif status == "insufficient_history":
        note = (
            "No observed days in the seasonal window, so no profile can be "
            "computed. Missing days are not treated as zero."
        )
    else:
        note = "Requirement satisfied."

    return {
        "status": status,
        "method": "monthly-climatology",
        "version": METHOD_VERSION,
        "metric": metric,
        "years": sorted(observed_years),
        "years_requested": last_year - first_year + 1,
        "first_year": first_year,
        "last_year": last_year,
        "months": months,
        "baseline_mean": round(baseline, 3) if baseline is not None else None,
        "sufficient_months": len(sufficient_months),
        "required_months": SEASON_MIN_SUFFICIENT_MONTHS,
        "peak_month": peak["label"] if peak else None,
        "trough_month": trough["label"] if trough else None,
        "seasonal_amplitude": amplitude,
        "requirements": {
            "needed_years": SEASON_MIN_YEARS,
            "available_years": len(observed_years),
            "needed_days_per_month_year": SEASON_MIN_DAYS_PER_MONTH_YEAR,
            "note": note,
        },
    }


def calendar_intelligence(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    metric: str = "detections",
    season_years: int = 5,
    baseline_days: int = 30,
    z_threshold: float = 3.0,
) -> dict[str, Any]:
    """One call, three analyses: trend, anomaly markers and seasonal profile."""
    field = _metric_field(metric)
    season_years = max(1, min(int(season_years), 6))

    # Historical daily activity: enough for the anomaly baseline and the seasonal
    # window, capped so a single request cannot scan two decades.
    history_start = date(end.year - season_years + 1, 1, 1)
    baseline_start = max(
        start - timedelta(days=baseline_days + 1),
        date(start.year - 12, 1, 1),
    )
    history_start = min(history_start, baseline_start)
    while (end - history_start).days + 1 > MAX_SPAN_DAYS:
        season_years -= 1
        if season_years < 1:
            history_start = baseline_start
            break
        history_start = min(
            date(end.year - season_years + 1, 1, 1),
            baseline_start,
        )

    history_filters = replace(
        filters,
        start_date=history_start,
        end_date=end,
        start_at=None,
        end_at=None,
    )
    daily = daily_metrics(session, history_filters)
    observed = observed_days(session, history_start, end, filters.sensor)

    # --- trend series ------------------------------------------------------
    values: list[float | None] = []
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        if cursor in observed:
            values.append(float(daily.get(cursor, {}).get(field, 0.0)))
        else:
            values.append(None)
        cursor += timedelta(days=1)

    smooth = trailing_mean(values)

    # --- anomalies (reuse the robust-z engine on the widened series) -------
    anomalies = detect_anomalies(
        session,
        filters,
        start=start,
        end=end,
        baseline_days=baseline_days,
        z_threshold=z_threshold,
        metric=metric,
        daily=daily,
    )
    severity_by_day = {
        point["date"] if isinstance(point["date"], date) else date.fromisoformat(point["date"]):
        point["severity"]
        for point in anomalies.get("points", [])
    }

    series = [
        {
            "date": day,
            "value": None if value is None else round(value, 3),
            "observed": value is not None,
            "trailing_mean": smooth[index],
            "severity": severity_by_day.get(day, "unobserved" if value is None else "normal"),
        }
        for index, (day, value) in enumerate(zip(days, values, strict=True))
    ]

    trend = _trend_block(series, metric)

    seasonality = _seasonality_block(
        daily,
        observed,
        first_year=history_start.year,
        last_year=end.year,
        metric=metric,
    )

    observed_in_window = sum(1 for value in values if value is not None)
    window = {
        "start": start,
        "end": end,
        "days": len(days),
        "observed_days": observed_in_window,
        "missing_days": len(days) - observed_in_window,
        "coverage": round(observed_in_window / len(days), 4) if days else 0.0,
        "metric": metric,
        "history_start": min(history_start, start),
    }

    notes = [
        "Counts are detections, not fires.",
        "Missing days are excluded from the trend and the seasonal profile; they are never zero.",
        "Trends use a Theil–Sen slope, which resists a single extreme day.",
        "An anomaly needs a baseline: a day is only unusual relative to its own observed history.",
        seasonality["requirements"]["note"],
    ]
    if metric == "frp":
        notes.append(
            "FRP is a sum of per-detection reported values; a change in the sensor mix "
            "changes the total independently of fire activity."
        )

    return {
        "status": "ok",
        "method": {"name": "calendar-intelligence", "version": METHOD_VERSION},
        "window": window,
        "trend": {**trend, "series": series},
        "anomalies": {
            "status": anomalies.get("status"),
            "method": anomalies.get("method"),
            "baseline": anomalies.get("baseline"),
            "count": len(anomalies.get("anomalies", [])),
            "items": anomalies.get("anomalies", []),
            "evaluated_days": anomalies.get("evaluated_days", 0),
            "requirements": anomalies.get("requirements"),
        },
        "seasonality": seasonality,
        "notes": notes,
    }
