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

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.dialect import dialect_name, utc_day
from app.db.models import DataSource, FireObservation, ObservationMatch, SourceAvailability
from app.services.observation_queries import ObservationFilters
from app.services.rollups import activity_rows, day_of

Granularity = Literal["day", "week", "month", "year"]

GRANULARITIES: tuple[Granularity, ...] = ("day", "week", "month", "year")

#: Statuses that count as "the same hotspot seen twice" for the harmonised series.
MATCH_STATUSES: tuple[str, ...] = ("probable", "possible")

#: Matches the regional engine: a calendar may cover the whole stored archive.
MAX_SPAN_DAYS = 366 * 30


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
            "Calendar range is too large; narrow it to 30 years or less.",
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


def daily_metrics(session: Session, filters: ObservationFilters) -> dict[date, dict[str, Any]]:
    """
    Day buckets for the calendar, anomaly engine and reports. Reads the daily
    rollup when the filters allow it, otherwise scans the observations.
    """
    rows = activity_rows(session, filters)

    daily: dict[date, dict[str, Any]] = {}
    for row in rows:
        day = day_of(row.day)
        count = int(row.detections or 0)
        frp_sum = float(row.frp_sum_mw or 0.0)
        frp_max = float(row.frp_max_mw) if row.frp_max_mw is not None else None

        bucket = daily.setdefault(
            day,
            {
                "detections": 0,
                "modis": 0,
                "viirs": 0,
                "frp_sum_mw": 0.0,
                "frp_max_mw": None,
                "high_confidence": 0,
            },
        )
        bucket["detections"] += count
        if row.sensor == "MODIS":
            bucket["modis"] += count
        elif row.sensor == "VIIRS":
            bucket["viirs"] += count
        bucket["frp_sum_mw"] += frp_sum
        if frp_max is not None and (bucket["frp_max_mw"] is None or frp_max > bucket["frp_max_mw"]):
            bucket["frp_max_mw"] = frp_max
        if (row.confidence_category or "").lower() == "high":
            bucket["high_confidence"] += count
    return daily


def matched_viirs_by_day(
    session: Session, filters: ObservationFilters
) -> dict[date, int]:
    """Distinct VIIRS detections on each day with a MODIS association.

    The harmonised calendar subtracts these from the raw daily count so a hotspot
    seen by both sensors is not counted twice. Days never scanned for
    associations return nothing here and therefore keep their raw count.
    """
    if (filters.sensor or "").upper() == "MODIS":
        # A MODIS-only view has no VIIRS detections to deduplicate.
        return {}

    day_expr = utc_day(FireObservation.acquired_at, dialect_name(session))
    statement = (
        select(day_expr.label("day"), func.count(func.distinct(FireObservation.id)))
        .join(ObservationMatch, ObservationMatch.observation_b_id == FireObservation.id)
        .where(
            ObservationMatch.match_status.in_(MATCH_STATUSES),
            FireObservation.sensor == "VIIRS",
        )
    )
    statement = filters.apply(statement)

    matched: dict[date, int] = {}
    for raw_day, count in session.execute(statement.group_by(day_expr)):
        day = _as_date(raw_day)
        if day is not None:
            matched[day] = int(count)
    return matched


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

    daily = daily_metrics(session, filters)
    matched_by_day = matched_viirs_by_day(session, filters)
    coverage = _availability(session, start, end, filters.sensor)

    total_detections = 0
    total_matched = 0
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
        matched = 0
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
            matched += matched_by_day.get(cursor, 0)
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
        total_matched += matched
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
                "matched_viirs": matched,
                "harmonized": max(0, detections - matched),
                "frp_sum_mw": round(frp_sum, 3),
                "frp_max_mw": round(frp_max, 3) if frp_max is not None else None,
                "high_confidence": high_confidence,
            }
        )

    totals = {
        "detections": total_detections,
        "modis": total_modis,
        "viirs": total_viirs,
        "matched_viirs": total_matched,
        "harmonized": max(0, total_detections - total_matched),
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
            "harmonized = detections - distinct VIIRS detections with a probable or "
            "possible MODIS association on the same day. Days not yet scanned for "
            "associations keep their raw count, so harmonized is never below the "
            "documented de-duplication.",
        ],
    }
