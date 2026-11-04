"""Daily and cell activity rollups.

Eleven million rows cannot be grouped by day on every page load. PostgreSQL keeps
two compact tables:

* ``daily_activity`` — day × sensor × confidence × day/night × satellite × product;
* ``cell_activity`` — day × 2° cell × sensor.

They are ordinary tables, not materialized views, so ingestion recomputes only the
days it touched (``refresh_rollup(since=...)``) instead of rebuilding the whole
history. The calendar, analytics, anomalies and the zoomed-out map read them.

The rollups cannot answer per-detection filters (`bbox`, `min_frp`) for the daily
shape; those requests fall back to the live scan. The cell rollup *can* answer a
bbox because a bbox maps to cell-index ranges, which is exactly what the map needs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name
from app.db.models import FireObservation
from app.services.observation_queries import BBox, ObservationFilters

ROLLUP_NAME = "daily_activity"
CELL_ROLLUP_NAME = "cell_activity"
ROLLUP_MAX_AGE_MINUTES = 30

#: Filters the daily rollup can honour. Anything else needs the live scan.
_LIVE_ONLY_FILTERS = ("bbox", "min_frp")


def _table_exists(session: Session, name: str) -> bool:
    if dialect_name(session) != "postgresql":
        return False
    return bool(
        session.scalar(
            text("SELECT to_regclass(:name)"), {"name": f"public.{name}"}
        )
    )


def _rollup_exists(session: Session) -> bool:
    return _table_exists(session, ROLLUP_NAME)


def _cell_rollup_exists(session: Session) -> bool:
    return _table_exists(session, CELL_ROLLUP_NAME)


def supports_rollup(filters: ObservationFilters) -> bool:
    return all(getattr(filters, name) is None for name in _LIVE_ONLY_FILTERS)


def _day_clauses(filters: ObservationFilters, params: dict[str, Any]) -> list[str]:
    clauses: list[str] = []
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
    return clauses


def cell_rows(session: Session, filters: ObservationFilters, *, limit: int) -> list[Any] | None:
    """
    Ranked 2° cells from the cell rollup, or None when the filters need a live
    scan (per-detection FRP floor) or the rollup is unavailable.
    """
    if filters.min_frp is not None or not _cell_rollup_exists(session):
        return None

    params: dict[str, Any] = {}
    clauses = _day_clauses(filters, params)
    if filters.sensor:
        clauses.append("sensor = :sensor")
        params["sensor"] = filters.sensor.upper()
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


def map_cells(
    session: Session,
    filters: ObservationFilters,
    *,
    bbox: BBox,
    cell_degrees: float,
    limit: int,
) -> list[dict[str, Any]] | None:
    """
    Aggregate the 2° cell rollup into the requested (coarser) map cell.

    Returns None when the rollup cannot honour the filters, so the caller falls
    back to the exact scan. The rollup has no day/night, confidence or satellite
    dimensions, and no per-detection FRP.
    """
    if (
        not _cell_rollup_exists(session)
        or filters.min_frp is not None
        or filters.daynight is not None
        or filters.min_confidence is not None
        or filters.satellite is not None
    ):
        return None
    if cell_degrees < 2.0:
        return None

    params: dict[str, Any] = {
        "cell": cell_degrees,
        "limit": limit,
        "lat_min": int((bbox.south + 90.0) // 2.0),
        "lat_max": int((bbox.north + 90.0) // 2.0),
        "lon_min": int((bbox.west + 180.0) // 2.0),
        "lon_max": int((bbox.east + 180.0) // 2.0),
    }
    clauses = _day_clauses(filters, params)
    clauses.extend(
        [
            "lat_index BETWEEN :lat_min AND :lat_max",
            "lon_index BETWEEN :lon_min AND :lon_max",
        ]
    )
    if filters.sensor:
        clauses.append("sensor = :sensor")
        params["sensor"] = filters.sensor.upper()
    if filters.synthetic is not None:
        clauses.append("is_synthetic = :synthetic")
        params["synthetic"] = filters.synthetic

    total_expr = "sum(harmonized)" if filters.harmonized else "sum(detections)"
    viirs_expr = (
        "sum(CASE WHEN sensor = 'VIIRS' THEN detections - matched_viirs ELSE 0 END)"
        if filters.harmonized
        else "sum(CASE WHEN sensor = 'VIIRS' THEN detections ELSE 0 END)"
    )
    statement = text(
        f"""
        WITH grouped AS (
            SELECT
                CAST(floor((lat_index * 2.0) / :cell) AS integer) AS lat_cell,
                CAST(floor((lon_index * 2.0) / :cell) AS integer) AS lon_cell,
                {total_expr} AS detections,
                sum(CASE WHEN sensor = 'MODIS' THEN detections ELSE 0 END) AS modis,
                {viirs_expr} AS viirs,
                max(frp_max_mw) AS max_frp_mw
            FROM {CELL_ROLLUP_NAME}
            WHERE {' AND '.join(clauses)}
            GROUP BY 1, 2
        )
        SELECT lat_cell, lon_cell, detections, modis, viirs, max_frp_mw
        FROM grouped
        ORDER BY detections DESC
        LIMIT :limit
        """
    )
    rows = session.execute(statement, params).all()
    return [
        {
            "lat_index": int(row.lat_cell),
            "lon_index": int(row.lon_cell),
            "detections": int(row.detections),
            "modis": int(row.modis or 0),
            "viirs": int(row.viirs or 0),
            "max_frp_mw": float(row.max_frp_mw) if row.max_frp_mw is not None else None,
        }
        for row in rows
    ]



def _cell_rollup_insert(
    session: Session, predicates: list[str], params: dict[str, Any]
) -> None:
    """Rebuild ``cell_activity`` for a window, with harmonized counts.

    ``matched_viirs`` is the number of distinct VIIRS detections in the cell/day
    that carry a probable or possible MODIS association. ``harmonized`` is the
    raw detection count minus those duplicates, matching the harmonized-series
    definition. Predicates use unqualified columns so they apply to both the
    observations and the matched-VIIRS branch.
    """
    outer_where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
    matched_where = "WHERE m.match_status IN ('probable', 'possible')"
    if predicates:
        matched_where += " AND " + " AND ".join(predicates)
    session.execute(
        text(
            f"""
            WITH matched AS (
                SELECT
                    CAST((b.acquired_at AT TIME ZONE 'UTC') AS date) AS day,
                    CAST(floor((b.latitude + 90.0) / 2.0) AS integer) AS lat_index,
                    CAST(floor((b.longitude + 180.0) / 2.0) AS integer) AS lon_index,
                    b.sensor AS sensor,
                    b.is_synthetic AS is_synthetic,
                    count(DISTINCT b.id)::bigint AS matched_viirs
                FROM observation_matches m
                JOIN fire_observations b ON b.id = m.observation_b_id
                {matched_where}
                GROUP BY 1, 2, 3, 4, 5
            )
            INSERT INTO {CELL_ROLLUP_NAME} (
                day, lat_index, lon_index, sensor, is_synthetic,
                detections, frp_sum_mw, frp_max_mw, matched_viirs, harmonized
            )
            SELECT
                CAST((f.acquired_at AT TIME ZONE 'UTC') AS date),
                CAST(floor((f.latitude + 90.0) / 2.0) AS integer),
                CAST(floor((f.longitude + 180.0) / 2.0) AS integer),
                f.sensor,
                f.is_synthetic,
                count(*)::bigint,
                COALESCE(sum(f.frp_mw), 0),
                max(f.frp_mw),
                COALESCE(max(mt.matched_viirs), 0)::bigint,
                (count(*) - COALESCE(max(mt.matched_viirs), 0))::bigint
            FROM fire_observations f
            LEFT JOIN matched mt
                ON mt.day = CAST((f.acquired_at AT TIME ZONE 'UTC') AS date)
                AND mt.lat_index = CAST(floor((f.latitude + 90.0) / 2.0) AS integer)
                AND mt.lon_index = CAST(floor((f.longitude + 180.0) / 2.0) AS integer)
                AND mt.sensor = f.sensor
                AND mt.is_synthetic = f.is_synthetic
            {outer_where}
            GROUP BY 1, 2, 3, 4, 5
            """
        ),
        params,
    )

def sensor_totals(
    session: Session, filters: ObservationFilters
) -> dict[str, int] | None:
    """Detection totals per sensor from the daily rollup, or None."""
    if (
        not _rollup_exists(session)
        or filters.bbox is not None
        or filters.min_frp is not None
        or filters.min_confidence is not None
        or filters.daynight is not None
        or filters.satellite is not None
    ):
        return None
    params: dict[str, Any] = {}
    clauses = _day_clauses(filters, params)
    if filters.synthetic is not None:
        clauses.append("is_synthetic = :synthetic")
        params["synthetic"] = filters.synthetic
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = session.execute(
        text(
            f"SELECT sensor, sum(detections) AS detections FROM {ROLLUP_NAME}"
            f"{where} GROUP BY sensor"
        ),
        params,
    ).all()
    return {sensor: int(count or 0) for sensor, count in rows}


def observation_totals(session: Session) -> tuple[int, int] | None:
    """(all, synthetic) detection counts from the daily rollup, or None."""
    if not _rollup_exists(session):
        return None
    row = session.execute(
        text(
            "SELECT COALESCE(sum(detections), 0)::bigint, "
            "COALESCE(sum(detections) FILTER (WHERE is_synthetic), 0)::bigint "
            f"FROM {ROLLUP_NAME}"
        )
    ).one()
    return int(row[0]), int(row[1])


def cell_matched_by_day(
    session: Session, filters: ObservationFilters
) -> dict[date, int] | None:
    """Matched VIIRS per day from the cell rollup, or None for a live scan.

    The cell rollup stores the per-cell matched count, so summing it per day is
    the same distinct-observation count the calendar needs, without joining
    millions of match rows.
    """
    if (
        not _cell_rollup_exists(session)
        or filters.min_frp is not None
        or filters.bbox is not None
        or filters.min_confidence is not None
        or filters.daynight is not None
        or filters.satellite is not None
    ):
        return None
    if (filters.sensor or "").upper() == "MODIS":
        return {}

    params: dict[str, Any] = {}
    clauses = _day_clauses(filters, params)
    clauses.append("sensor = 'VIIRS'")
    if filters.synthetic is not None:
        clauses.append("is_synthetic = :synthetic")
        params["synthetic"] = filters.synthetic
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = session.execute(
        text(
            f"SELECT day, sum(matched_viirs) AS matched FROM {CELL_ROLLUP_NAME}"
            f"{where} GROUP BY day"
        ),
        params,
    ).all()
    return {day: int(matched or 0) for day, matched in rows}


def refresh_rollup(session: Session, *, since: date | None = None) -> bool:
    """
    Rebuild the rollups. With ``since`` only that day and later are recomputed;
    without it the whole history is rebuilt (backfill / first run).

    Safe on SQLite (no-op). Returns True when a rollup exists and was refreshed.
    """
    if not _rollup_exists(session):
        return False

    if since is None:
        session.execute(text(f"TRUNCATE TABLE {ROLLUP_NAME}"))
        if _cell_rollup_exists(session):
            session.execute(text(f"TRUNCATE TABLE {CELL_ROLLUP_NAME}"))
        day_filter = ""
        params: dict[str, Any] = {}
    else:
        session.execute(text(f"DELETE FROM {ROLLUP_NAME} WHERE day >= :since"), {"since": since})
        if _cell_rollup_exists(session):
            session.execute(
                text(f"DELETE FROM {CELL_ROLLUP_NAME} WHERE day >= :since"), {"since": since}
            )
        day_filter = "WHERE CAST((acquired_at AT TIME ZONE 'UTC') AS date) >= :since"
        params = {"since": since}

    session.execute(
        text(
            f"""
            INSERT INTO {ROLLUP_NAME} (
                day, sensor, confidence_category, daynight, satellite, source_code,
                is_synthetic, detections, frp_sum_mw, frp_max_mw
            )
            SELECT
                CAST((acquired_at AT TIME ZONE 'UTC') AS date),
                sensor, confidence_category, daynight, satellite, source_code,
                is_synthetic, count(*)::bigint, COALESCE(sum(frp_mw), 0), max(frp_mw)
            FROM fire_observations
            {day_filter}
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            """
        ),
        params,
    )

    if _cell_rollup_exists(session):
        predicates = [day_filter.removeprefix("WHERE ")] if day_filter else []
        _cell_rollup_insert(session, predicates, params)

    session.commit()
    return True


def refresh_rollup_range(session: Session, start: date, end: date) -> bool:
    """Recompute only the days in ``[start, end]``.

    Backfills ingest in arbitrary order, so ``since`` is wrong for them: passing
    the first backfilled day rebuilds every later day as well (11 M+ rows) and
    can exceed the statement timeout. A bounded range touches only the days the
    windows actually changed.
    """
    if end < start:
        raise ValueError("end must be on or after start")
    if not _rollup_exists(session):
        return False

    tables = [ROLLUP_NAME]
    if _cell_rollup_exists(session):
        tables.append(CELL_ROLLUP_NAME)
    for table in tables:
        session.execute(
            text(f"DELETE FROM {table} WHERE day BETWEEN :start AND :end"),
            {"start": start, "end": end},
        )

    window = (
        "WHERE CAST((acquired_at AT TIME ZONE 'UTC') AS date) BETWEEN :start AND :end"
    )
    session.execute(
        text(
            f"""
            INSERT INTO {ROLLUP_NAME} (
                day, sensor, confidence_category, daynight, satellite, source_code,
                is_synthetic, detections, frp_sum_mw, frp_max_mw
            )
            SELECT
                CAST((acquired_at AT TIME ZONE 'UTC') AS date),
                sensor, confidence_category, daynight, satellite, source_code,
                is_synthetic, count(*)::bigint, COALESCE(sum(frp_mw), 0), max(frp_mw)
            FROM fire_observations
            {window}
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            """
        ),
        {"start": start, "end": end},
    )
    if _cell_rollup_exists(session):
        predicate = (
            "CAST((acquired_at AT TIME ZONE 'UTC') AS date) BETWEEN :start AND :end"
        )
        _cell_rollup_insert(session, [predicate], {"start": start, "end": end})
    session.commit()
    return True


def rollup_status(session: Session) -> dict[str, Any]:
    if not _rollup_exists(session):
        return {"available": False, "dialect": dialect_name(session)}
    rows = session.scalar(text(f"SELECT count(*) FROM {ROLLUP_NAME}"))
    latest = session.scalar(text(f"SELECT max(day) FROM {ROLLUP_NAME}"))
    cells = (
        session.scalar(text(f"SELECT count(*) FROM {CELL_ROLLUP_NAME}"))
        if _cell_rollup_exists(session)
        else None
    )
    return {
        "available": True,
        "rows": int(rows or 0),
        "cell_rows": int(cells) if cells is not None else None,
        "latest_day": latest.isoformat() if latest is not None else None,
        "dialect": dialect_name(session),
        "kind": "table",
    }


def activity_rows(session: Session, filters: ObservationFilters) -> list[Any]:
    """
    Rows with (day, sensor, confidence, daynight, satellite, source_code,
    is_synthetic, detections, frp_sum, frp_max). The rollup is used when the
    filters allow it; otherwise the query runs against the observations.
    """
    if supports_rollup(filters) and _rollup_exists(session):
        params: dict[str, Any] = {}
        clauses = _day_clauses(filters, params)
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
