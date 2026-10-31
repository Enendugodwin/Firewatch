"""Historical burning calendar.

Buckets are always materialised for the whole requested range, even when a day
holds no detections, and every bucket carries what the sources actually observed.
A day with no rows is therefore never presented as a day with zero activity: it
is ``quiet`` only when a source reported availability for that date, and
``unobserved`` when nothing is known about it.

Counts are detections, not fires. FRP values are sums/maxima of the stored
per-detection measurements.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal, cast

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import DataSource, FireObservation, SourceAvailability
from app.services.observation_queries import ObservationFilters

Granularity = Literal["day", "week", "month", "year"]

GRANULARITIES: tuple[Granularity, ...] = ("day", "week", "month", "year")

#: A calendar request may span six years; past that the UI needs a specific view.
MAX_SPAN_DAYS = 366 * 6


@dataclass(frozen=True)
class Bucket:
    start: date
    end: date


def parse_granularity(value: str) -> Granularity:
    normalised = (value or "").strip().lower()
    if normalised not in GRANULARITIES:
        raise AppError(
            "bad_request",
            "granularity must be one of day, week, month or year.",
            details={"received": value},
        )
    return cast(Granularity, normalised)


def bucket_for(day: date, granularity: Granularity) -> Bucket:
    if granularity == "day":
        return Bucket(day, day)
    if granularity == "week":
        start = day - timedelta(days=day.weekday())
        return Bucket(start, start + timedelta(days=6))
    if granularity == "month":
        start = day.replace(day=1)
        return Bucket(
            start, date(start.year, start.month, monthrange(start.year, start.month)[1])
        )
    return Bucket(date(day.year, 1, 1), date(day.year, 12, 31))


def bucket_label(bucket: Bucket, granularity: Granularity) -> str:
    if granularity == "day":
        return bucket.start.isoformat()
    if granularity == "week":
        return f"{bucket.start.isoformat()} week"
    if granularity == "month":
        return bucket.start.strftime("%Y-%m")
    return str(bucket.start.year)


def buckets_between(start: date, end: date, granularity: Granularity) -> list[Bucket]:
    """Every bucket overlapping the range, in order, without gaps."""
    buckets: list[Bucket] = []
    cursor = start
    seen: set[date] = set()
    while cursor <= end:
        bucket = bucket_for(cursor, granularity)
        if bucket.start not in seen:
            seen.add(bucket.start)
            buckets.append(bucket)
        cursor = bucket.end + timedelta(days=1)
    return buckets


def validate_span(start: date, end: date) -> None:
    if start > end:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    if (end - start).days + 1 > MAX_SPAN_DAYS:
        raise AppError(
            "bad_request",
            "Calendar range is too large; narrow it to six years or less.",
            details={"max_days": MAX_SPAN_DAYS},
        )


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:  # pragma: no cover - defensive
        return None


def _daily_metrics(session: Session, filters: ObservationFilters) -> dict[date, dict[str, Any]]:
    """
    One grouped query; the SQL date function is portable across SQLite/PostgreSQL.

    Only the five columns the aggregation needs are selected, so SQLite never
    materialises a wide intermediate table for the whole range.
    """
    day = func.date(FireObservation.acquired_at).label("day")
    statement = filters.apply(
        select(
            day,
            func.count().label("detections"),
            func.sum(case((FireObservation.sensor == "MODIS", 1), else_=0)).label("modis"),
            func.sum(case((FireObservation.sensor == "VIIRS", 1), else_=0)).label("viirs"),
            func.sum(FireObservation.frp_mw).label("frp_sum_mw"),
            func.max(FireObservation.frp_mw).label("frp_max_mw"),
            func.sum(case((FireObservation.confidence_category == "high", 1), else_=0)).label(
                "high_confidence"
            ),
        )
    ).group_by(func.date(FireObservation.acquired_at))

    rows: dict[date, dict[str, Any]] = {}
    for raw_day, detections, modis, viirs, frp_sum, frp_max, high in session.execute(statement):
        parsed = _as_date(raw_day)
        if parsed is None:
            continue
        rows[parsed] = {
            "detections": int(detections or 0),
            "modis": int(modis or 0),
            "viirs": int(viirs or 0),
            "frp_sum_mw": float(frp_sum or 0.0),
            "frp_max_mw": float(frp_max) if frp_max is not None else None,
            "high_confidence": int(high or 0),
        }
    return rows


def _availability(
    session: Session, start: date, end: date, sensor: str | None
) -> dict[date, dict[str, int]]:
    """
    Per-day coverage: how many selected sources observed, were checked and empty,
    or are missing/unknown. A date with no record stays unknown rather than zero.
    """
    statement: Select = (
        select(SourceAvailability.observation_date, SourceAvailability.status, func.count())
        .join(DataSource, DataSource.id == SourceAvailability.source_id)
        .where(
            SourceAvailability.observation_date >= start,
            SourceAvailability.observation_date <= end,
        )
        .group_by(SourceAvailability.observation_date, SourceAvailability.status)
    )
    if sensor:
        statement = statement.where(DataSource.sensor == sensor.upper())

    coverage: dict[date, dict[str, int]] = {}
    for raw_day, status, count in session.execute(statement):
        parsed = _as_date(raw_day)
        if parsed is None:
            continue
        entry = coverage.setdefault(parsed, {"observed": 0, "empty": 0, "missing": 0})
        normalised = (status or "").lower()
        if normalised == "available":
            entry["observed"] += int(count)
        elif normalised == "empty":
            entry["observed"] += int(count)
            entry["empty"] += int(count)
        else:
            entry["missing"] += int(count)
    return coverage


def _bucket_coverage(bucket: Bucket, coverage: dict[date, dict[str, int]]) -> dict[str, int]:
    counts = {"observed": 0, "empty": 0, "missing": 0, "unknown": 0}
    cursor = bucket.start
    while cursor <= bucket.end:
        entry = coverage.get(cursor)
        if entry is None:
            counts["unknown"] += 1
        else:
            if entry["observed"]:
                counts["observed"] += 1
            if entry["empty"]:
                counts["empty"] += 1
            if entry["missing"]:
                counts["missing"] += 1
            if not entry["observed"] and not entry["missing"]:
                counts["unknown"] += 1
        cursor += timedelta(days=1)
    return counts


def calendar_activity(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    granularity: Granularity,
) -> dict[str, Any]:
    validate_span(start, end)

    daily = _daily_metrics(session, filters)
    coverage = _availability(session, start, end, filters.sensor)

    total_detections = 0
    total_modis = 0
    total_viirs = 0
    total_frp_sum = 0.0
    total_frp_max: float | None = None
    total_high = 0
    active_buckets = 0
    quiet_buckets = 0
    unobserved_buckets = 0

    buckets: list[dict[str, Any]] = []
    for bucket in buckets_between(start, end, granularity):
        detections = 0
        modis = 0
        viirs = 0
        high_confidence = 0
        frp_sum = 0.0
        frp_max: float | None = None

        cursor = bucket.start
        while cursor <= bucket.end:
            day_metrics = daily.get(cursor)
            if day_metrics:
                detections += day_metrics["detections"]
                modis += day_metrics["modis"]
                viirs += day_metrics["viirs"]
                high_confidence += day_metrics["high_confidence"]
                frp_sum += day_metrics["frp_sum_mw"]
                day_max = day_metrics["frp_max_mw"]
                if day_max is not None and (frp_max is None or day_max > frp_max):
                    frp_max = day_max
            cursor += timedelta(days=1)

        bucket_coverage = _bucket_coverage(bucket, coverage)
        if detections > 0:
            state = "active"
        elif bucket_coverage["observed"] > 0 or bucket_coverage["empty"] > 0:
            state = "quiet"
        else:
            state = "unobserved"

        total_detections += detections
        total_modis += modis
        total_viirs += viirs
        total_high += high_confidence
        total_frp_sum += frp_sum
        if frp_max is not None and (total_frp_max is None or frp_max > total_frp_max):
            total_frp_max = frp_max
        if state == "active":
            active_buckets += 1
        elif state == "quiet":
            quiet_buckets += 1
        else:
            unobserved_buckets += 1

        buckets.append(
            {
                "start": bucket.start,
                "end": bucket.end,
                "label": bucket_label(bucket, granularity),
                "state": state,
                "coverage": bucket_coverage,
                "detections": detections,
                "modis": modis,
                "viirs": viirs,
                "frp_sum_mw": round(frp_sum, 3),
                "frp_max_mw": round(frp_max, 3) if frp_max is not None else None,
                "high_confidence": high_confidence,
            }
        )

    totals = {
        "detections": total_detections,
        "modis": total_modis,
        "viirs": total_viirs,
        "frp_sum_mw": round(total_frp_sum, 3),
        "frp_max_mw": round(total_frp_max, 3) if total_frp_max is not None else None,
        "high_confidence": total_high,
        "active_buckets": active_buckets,
        "quiet_buckets": quiet_buckets,
        "unobserved_buckets": unobserved_buckets,
        "buckets": len(buckets),
    }

    return {
        "granularity": granularity,
        "start_date": start,
        "end_date": end,
        "buckets": buckets,
        "totals": totals,
        "notes": [
            "Each bucket counts thermal detections, not fires.",
            "quiet means a source observed that period with no detections; "
            "unobserved means no availability was recorded, so it is not zero.",
        ],
    }
