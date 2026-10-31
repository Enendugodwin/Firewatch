"""Anomaly detection on daily detection counts.

Method: for each evaluated day, compare the observed value with the median of the
preceding ``baseline_days`` **observed** days (days with recorded source
availability), and score the deviation with a robust z-score:

    z = (x - median) / (1.4826 * MAD)

MAD is immune to a single huge day pulling the baseline, which is exactly what a
fire season looks like. Gaps are excluded from the baseline rather than counted as
zeros, so a missing day never manufactures an anomaly.

When the preceding history is shorter than ``min_baseline_days`` the engine falls
back to a **leave-one-out baseline over the evaluated window** (each day compared
with the median of the other observed days in the window), clearly labelled
``within_window``. That is a short-history approximation, not a seasonal baseline.

With too few days even for the fallback (fewer than ``min_window_days``), it
returns ``insufficient_history`` and states what is missing. No anomaly is
invented to fill the page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median, pstdev
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import DataSource, SourceAvailability
from app.services.calendar import daily_metrics
from app.services.observation_queries import ObservationFilters

METHOD_VERSION = "anomaly-robust-z-v1"
DEFAULT_BASELINE_DAYS = 30
DEFAULT_MIN_BASELINE_DAYS = 14
DEFAULT_Z_THRESHOLD = 3.0
#: Minimum observed days in the evaluated window for the short-history fallback.
DEFAULT_MIN_WINDOW_DAYS = 4
#: 1.4826 turns the MAD into a standard-deviation equivalent for normal data.
MAD_TO_SIGMA = 1.4826


@dataclass(frozen=True)
class Baseline:
    days: int
    median: float
    mad: float
    scale: float


def observed_days(session: Session, start: date, end: date, sensor: str | None) -> set[date]:
    """Days a selected source actually observed (available or checked-empty)."""
    statement: Select = (
        select(SourceAvailability.observation_date)
        .join(DataSource, DataSource.id == SourceAvailability.source_id)
        .where(
            SourceAvailability.observation_date >= start,
            SourceAvailability.observation_date <= end,
            SourceAvailability.status.in_(("available", "empty")),
        )
        .distinct()
    )
    if sensor:
        statement = statement.where(DataSource.sensor == sensor.upper())
    return {row[0] for row in session.execute(statement).all()}


def robust_baseline(values: list[float]) -> Baseline:
    """
    Median/MAD baseline. When MAD is zero - common with short or very stable
    windows - the standard deviation is used as the scale instead, so a real
    spike is still measurable; a constant series stays unrankable (scale 0).
    """
    center = float(median(values))
    deviations = [abs(value - center) for value in values]
    mad = float(median(deviations))
    scale = MAD_TO_SIGMA * mad
    if scale == 0 and len(values) > 1:
        scale = float(pstdev(values))
    return Baseline(days=len(values), median=center, mad=mad, scale=scale)


def severity_for(z: float) -> str:
    if z >= 5:
        return "critical"
    if z >= 4:
        return "high"
    if z >= 3:
        return "moderate"
    if z <= -3:
        # A large drop is informative but is not a fire anomaly; it is reported
        # separately so a gap is never mistaken for a quiet day.
        return "below_baseline"
    return "normal"


def _explain(
    day: date,
    observed: float,
    baseline: Baseline,
    z: float,
    source: str = "preceding",
) -> str:
    ratio = observed / baseline.median if baseline.median else None
    where = (
        f"over the preceding {baseline.days} observed days"
        if source == "preceding"
        else f"against the other {baseline.days} observed days in this window"
    )
    shape = f"{observed:.0f} detections against a baseline median of {baseline.median:.1f} {where}"
    if ratio is not None:
        shape += f" ({ratio:.1f}× the median)"
    return f"{day.isoformat()}: {shape}; robust z = {z:.2f}."


def detect_anomalies(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
    min_baseline_days: int = DEFAULT_MIN_BASELINE_DAYS,
    min_window_days: int = DEFAULT_MIN_WINDOW_DAYS,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    metric: str = "detections",
) -> dict[str, Any]:
    baseline_days = max(1, min(baseline_days, 365))
    min_baseline_days = max(2, min(min_baseline_days, baseline_days))
    min_window_days = max(3, min(min_window_days, 365))
    metric = "frp_sum_mw" if metric == "frp" else "detections"

    history_start = start - timedelta(days=baseline_days + 1)
    daily = daily_metrics(session, filters)
    observed = observed_days(session, history_start, end, filters.sensor)

    method = {
        "name": "robust_z",
        "version": METHOD_VERSION,
        "baseline_days": baseline_days,
        "min_baseline_days": min_baseline_days,
        "z_threshold": z_threshold,
        "metric": metric,
        "mad_to_sigma": MAD_TO_SIGMA,
        "comparison": "preceding observed days, gaps excluded",
        "baseline_source": "preceding",
        "min_window_days": min_window_days,
    }

    # Baseline over every observed day before the window, so the first evaluated
    # day already has a real baseline rather than an empty one.
    baseline_values: list[float] = []
    cursor = history_start
    while cursor < start:
        if cursor in observed:
            baseline_values.append(float(daily.get(cursor, {}).get(metric, 0.0)))
        cursor += timedelta(days=1)

    window_days = sorted(day for day in observed if start <= day <= end)
    window_values = {
        day: float(daily.get(day, {}).get(metric, 0.0)) for day in window_days
    }

    if len(baseline_values) >= min_baseline_days:
        baseline_source = "preceding"
        notes = [
            "Counts are detections, not fires.",
            "Severity bands: moderate z≥3, high z≥4, critical z≥5.",
            "Only days with recorded source availability are scored.",
        ]
    elif len(window_values) >= min_window_days:
        # Short history: compare each day with the rest of the window. Labelled
        # distinctly because it is a weaker claim than a preceding-history baseline.
        baseline_source = "within_window"
        baseline_values = list(window_values.values())
        notes = [
            "Counts are detections, not fires.",
            "Short-history mode: each day is compared with the other observed days in "
            "the window, not with a seasonal baseline.",
            "Ingest more history to switch to the preceding-history baseline.",
        ]
    else:
        return {
            "status": "insufficient_history",
            "method": method,
            "baseline": None,
            "points": [],
            "anomalies": [],
            "evaluated_days": 0,
            "observed_baseline_days": len(baseline_values),
            "requirements": {
                "needed_days": min_window_days,
                "available_days": len(window_values),
                "note": (
                    "Ingest more history for this scope: a baseline needs at least "
                    f"{min_window_days} observed days and this window has "
                    f"{len(window_values)}; the engine will not score anomalies without one."
                ),
            },
            "notes": [
                "An anomaly needs a baseline: a day is only unusual relative to its own history.",
                "Days without recorded source availability are excluded, not treated as zero.",
            ],
        }

    method["baseline_source"] = baseline_source
    method["comparison"] = (
        "preceding observed days, gaps excluded"
        if baseline_source == "preceding"
        else "other observed days in the evaluated window (short history)"
    )

    baseline = robust_baseline(baseline_values)
    points: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    day = start
    while day <= end:
        if day not in observed:
            day += timedelta(days=1)
            continue

        observed_value = window_values.get(day, float(daily.get(day, {}).get(metric, 0.0)))
        expected = baseline
        if baseline_source == "within_window":
            others = [value for other, value in window_values.items() if other != day]
            expected = robust_baseline(others) if len(others) >= 3 else baseline
        if expected.scale > 0:
            z = (observed_value - expected.median) / expected.scale
        elif observed_value > expected.median:
            # Zero dispersion: every baseline day was identical. A deviation is
            # real but cannot be expressed as a z-score.
            z = float("nan")
        else:
            z = 0.0

        severity = "normal"
        if z == z and abs(z) >= z_threshold:  # NaN-safe
            severity = severity_for(z)
        elif z != z and observed_value > expected.median:
            # Constant baseline: the departure is real but cannot be ranked.
            severity = "unknown_scale"

        point = {
            "date": day,
            "observed": round(observed_value, 2),
            "expected": round(expected.median, 2),
            "deviation": round(observed_value - expected.median, 2),
            "robust_z": None if z != z else round(z, 2),
            "severity": severity,
            "explanation": None,
        }
        if severity in ("moderate", "high", "critical"):
            point["explanation"] = _explain(
                day, observed_value, expected, 0.0 if z != z else z, baseline_source
            )
            anomalies.append(point)
        elif severity == "unknown_scale":
            point["explanation"] = (
                f"{day.isoformat()}: baseline has no dispersion, so this deviation "
                "cannot be ranked against it."
            )
        points.append(point)
        day += timedelta(days=1)

    return {
        "status": "ok",
        "method": method,
        "baseline": {
            "days": baseline.days,
            "median": round(baseline.median, 2),
            "mad": round(baseline.mad, 2),
            "scale": round(baseline.scale, 2),
        },
        "points": points,
        "anomalies": anomalies,
        "evaluated_days": len(points),
        "observed_baseline_days": len(baseline_values),
        "requirements": {
            "needed_days": min_baseline_days,
            "available_days": len(baseline_values),
            "note": (
                "Requirement satisfied."
                if baseline_source == "preceding"
                else "Short-history mode in use; more observed days will enable the "
                "preceding-history baseline."
            ),
        },
        "notes": notes,
    }
