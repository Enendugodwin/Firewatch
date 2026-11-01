"""Daily activity rollup.

Eleven million rows cannot be grouped by day on every page load: a full scan takes
~20 s. PostgreSQL keeps a materialized rollup (day × sensor × confidence ×
day/night × satellite × product) that the calendar, analytics and the anomaly
engine read instead, so those views answer in milliseconds.

The rollup cannot answer row-level filters (`bbox`, `min_frp`), so those requests
fall back to the live scan. Progress is explicit: `rollup_status` reports whether
the fast path is available and when it was last refreshed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name
from app.db.models import FireObservation
from app.services.observation_queries import ObservationFilters

ROLLUP_NAME = "daily_activity"
CELL_ROLLUP_NAME = "cell_activity"
ROLLUP_MAX_AGE_MINUTES = 30

#: Filters the rollup can honour. Anything else needs the live scan.
_LIVE_ONLY_FILTERS = ("bbox", "min_frp")


def _cell_rollup_exists(session: Session) -> bool:
    if dialect_name(session) != "postgresql":
        return False
    return bool(
        session.scalar(
            text("SELECT 1 FROM pg_matviews WHERE matviewname = :name"),
            {"name": CELL_ROLLUP_NAME},
        )
    )


def cell_rows(session: Session, filters: ObservationFilters, *, limit: int) -> list[Any] | None:
    """
    Ranked 2° cells from the cell rollup, or None when the filters need a live
    scan (bbox, per-detection FRP floor) or the rollup is unavailable.
    """
    if not supports_rollup(filters) or not _cell_rollup_exists(session):
        return None

    clauses = []
    params: dict[str, Any] = {}
    if filters.start_date:
        clauses.append("day >= :start_date")
        params["start_date"] = filters.start_date
    if filters.end_date:
        clauses.append("day <= :end_date")
        params["end_date"] = filters.end_date
    if filters.start_at:
        clauses.append("day >= :start_at")
        params["start_at"] = filters.start_at.date()
    if filters.end_at:
        clauses.append("day < :end_at")
        params["end_at"] = filters.end_at.date()
    if filters.synthetic is not None:
        clauses.append("is_synthetic = :synthetic")
        params["synthetic"] = filters.synthetic

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    statement = text(
        "SELECT lat_index, lon_index, sum(detections) AS detections, "
        "sum(frp_sum_mw) AS frp_sum_mw, max(frp_max_mw) AS frp_max_mw "
        f"FROM {CELL_ROLLUP_NAME}{where} "
        "GROUP BY lat_index, lon_index ORDER BY sum(detections) DESC LIMIT :limit"
    )
    params["limit"] = limit
    return list(session.execute(statement, params).all())


def _rollup_exists(session: Session) -> bool:
    if dialect_name(session) != "postgresql":
        return False
    return bool(
        session.scalar(
            text(
                "SELECT 1 FROM pg_matviews WHERE matviewname = :name"
            ),
            {"name": ROLLUP_NAME},
        )
    )


def supports_rollup(filters: ObservationFilters) -> bool:
    return all(getattr(filters, name) is None for name in _LIVE_ONLY_FILTERS)


def refresh_rollup(session: Session) -> bool:
    """Rebuild the rollup after ingestion. Safe to call on SQLite (no-op)."""
    if not _rollup_exists(session):
        return False
    session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {ROLLUP_NAME}"))
    if _cell_rollup_exists(session):
        session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {CELL_ROLLUP_NAME}"))
    session.commit()
    return True


def rollup_status(session: Session) -> dict[str, Any]:
    if not _rollup_exists(session):
        return {"available": False, "dialect": dialect_name(session)}
    rows = session.scalar(text(f"SELECT count(*) FROM {ROLLUP_NAME}"))
    return {"available": True, "rows": int(rows or 0), "dialect": dialect_name(session)}


def activity_rows(session: Session, filters: ObservationFilters) -> list[Any]:
    """
    Rows with (day, sensor, confidence, daynight, satellite, source_code,
    is_synthetic, detections, frp_sum, frp_max). The rollup is used when the
    filters allow it; otherwise the query runs against the observations.
    """
    if supports_rollup(filters) and _rollup_exists(session):
        clauses = []
        params: dict[str, Any] = {}
        if filters.start_date:
            clauses.append("day >= :start_date")
            params["start_date"] = filters.start_date
        if filters.end_date:
            clauses.append("day <= :end_date")
            params["end_date"] = filters.end_date
        if filters.start_at:
            clauses.append("day >= :start_at")
            params["start_at"] = filters.start_at.date()
        if filters.end_at:
            clauses.append("day < :end_at")
            params["end_at"] = filters.end_at.date()
        if filters.sensor:
            clauses.append("sensor = :sensor")
            params["sensor"] = filters.sensor.upper()
        if filters.satellite:
            clauses.append("satellite = :satellite")
            params["satellite"] = filters.satellite
        if filters.daynight:
            clauses.append("daynight = :daynight")
            params["daynight"] = filters.daynight.upper()[:1]
        if filters.min_confidence:
            from app.services.observation_queries import CONFIDENCE_LADDER

            allowed = CONFIDENCE_LADDER.get(filters.min_confidence.lower())
            if allowed:
                clauses.append("confidence_category = ANY(:categories)")
                params["categories"] = list(allowed)
        if filters.synthetic is not None:
            clauses.append("is_synthetic = :synthetic")
            params["synthetic"] = filters.synthetic

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        statement = text(
            "SELECT day, sensor, confidence_category, daynight, satellite, source_code, "
            "is_synthetic, detections, frp_sum_mw, frp_max_mw "
            f"FROM {ROLLUP_NAME}{where}"
        )
        return list(session.execute(statement, params).all())

    return list(_live_rows(session, filters))


def _live_rows(session: Session, filters: ObservationFilters):
    from sqlalchemy import func, select

    from app.db.dialect import utc_day

    day = utc_day(FireObservation.acquired_at, dialect_name(session))
    return session.execute(
        filters.apply(
            select(
                day.label("day"),
                FireObservation.sensor,
                FireObservation.confidence_category,
                FireObservation.daynight,
                FireObservation.satellite,
                FireObservation.source_code,
                FireObservation.is_synthetic,
                func.count().label("detections"),
                func.sum(FireObservation.frp_mw).label("frp_sum_mw"),
                func.max(FireObservation.frp_mw).label("frp_max_mw"),
            )
        ).group_by(
            day,
            FireObservation.sensor,
            FireObservation.confidence_category,
            FireObservation.daynight,
            FireObservation.satellite,
            FireObservation.source_code,
            FireObservation.is_synthetic,
        )
    ).all()


def day_of(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
