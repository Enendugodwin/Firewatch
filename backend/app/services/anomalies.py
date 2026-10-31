"""Anomaly detection on daily detection counts.

Method: for each evaluated day, compare the observed value with the median of the
preceding ``baseline_days`` **observed** days (days with recorded source
availability), and score the deviation with a robust z-score:

    z = (x - median) / (1.4826 * MAD)

MAD is immune to a single huge day pulling the baseline, which is exactly what a
fire season looks like. Gaps are excluded from the baseline rather than counted as
zeros, so a missing day never manufactures an anomaly.

The engine refuses to score when there is not enough history: with fewer than
``min_baseline_days`` observed baseline days it returns ``insufficient_history``
and states what is missing. No anomaly is invented to fill the page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
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
    center = float(median(values))
    deviations = [abs(value - center) for value in values]
    mad = float(median(deviations))
    return Baseline(days=len(values), median=center, mad=mad, scale=MAD_TO_SIGMA * mad)


def severity_for(z: float) -> str:
    if z >= 5:
        return "critical"
    if z >= 4:
        return "high"
    if z >= 3:
        return "moderate"
    return "normal"


def _explain(day: date, observed: float, baseline: Baseline, z: float) -> str:
    ratio = observed / baseline.median if baseline.median else None
    shape = (
        f"{observed:.0f} detections against a baseline median of {baseline.median:.1f} "
        f"over the preceding {baseline.days} observed days"
    )
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
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    metric: str = "detections",
) -> dict[str, Any]:
    baseline_days = max(1, min(baseline_days, 365))
    min_baseline_days = max(2, min(min_baseline_days, baseline_days))
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
    }

    # Baseline over every observed day before the window, so the first evaluated
    # day already has a real baseline rather than an empty one.
    baseline_values: list[float] = []
    cursor = history_start
    while cursor < start:
        if cursor in observed:
            baseline_values.append(float(daily.get(cursor, {}).get(metric, 0.0)))
        cursor += timedelta(days=1)

    if len(baseline_values) < min_baseline_days:
        return {
            "status": "insufficient_history",
            "method": method,
            "baseline": None,
            "points": [],
            "anomalies": [],
            "evaluated_days": 0,
            "observed_baseline_days": len(baseline_values),
            "requirements": {
                "needed_days": min_baseline_days,
                "available_days": len(baseline_values),
                "note": (
                    "Ingest more history for this scope; the engine will not score "
                    "anomalies without a baseline."
                ),
            },
            "notes": [
                "An anomaly needs a baseline: a day is only unusual relative to its own history.",
                "Days without recorded source availability are excluded, not treated as zero.",
            ],
        }

    baseline = robust_baseline(baseline_values)
    points: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    day = start
    while day <= end:
        if day not in observed:
            day += timedelta(days=1)
            continue

        observed_value = float(daily.get(day, {}).get(metric, 0.0))
        if baseline.scale > 0:
            z = (observed_value - baseline.median) / baseline.scale
        elif observed_value > baseline.median:
            # Zero dispersion: every baseline day was identical. A deviation is
            # real but cannot be expressed as a z-score.
            z = float("nan")
        else:
            z = 0.0

        severity = "normal"
        if z == z and z >= z_threshold:  # NaN-safe
            severity = severity_for(z)
        elif z != z and observed_value > baseline.median:
            severity = "unknown_scale"

        point = {
            "date": day,
            "observed": round(observed_value, 2),
            "expected": round(baseline.median, 2),
            "deviation": round(observed_value - baseline.median, 2),
            "robust_z": None if z != z else round(z, 2),
            "severity": severity,
            "explanation": None,
        }
        if severity in ("moderate", "high", "critical", "unknown_scale"):
            point["explanation"] = _explain(day, observed_value, baseline, 0.0 if z != z else z)
            anomalies.append(point)
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
            "note": "Requirement satisfied.",
        },
        "notes": [
            "Counts are detections, not fires.",
            "Severity bands: moderate z≥3, high z≥4, critical z≥5.",
            "Only days with recorded source availability are scored.",
        ],
    }
