"""Regional trend and seasonality engine.

Answers, for one boundary and one period: how much activity, when it peaks, how
it is trending with a significance test, whether a month is unusual for that time
of year, where activity recurs, and whether MODIS and VIIRS agree.

Efficiency rule: the read endpoints never scan ``fire_observations``. A region is
analysed once (``POST /regions/{id}/analyze``), which writes region × day × sensor
rows plus a recurring-activity grid; every page load afterwards reads those rows.

Scientific rules enforced here:

* the bounding box is only a SQL prefilter — published counts use the polygon;
* a day with no detections is a zero only when a source recorded coverage for it;
* combined series are labelled and never substituted for sensor series;
* a trend is not called significant without enough years, and seasonality needs
  the same calendar month observed in at least two years.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import fmean, median, pstdev
from typing import Any

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.dialect import dialect_name, utc_day
from app.db.models import (
    DataSource,
    FireObservation,
    GeographicRegion,
    RegionalCellStatistic,
    RegionalDailyStatistic,
    SourceAvailability,
)
from app.services.gazetteer import COUNTRIES, Place
from app.services.geometry import (
    CELL_DEGREES,
    RegionGeometry,
    bbox_boundary,
    cell_centre,
    cell_of,
    circle_boundary,
    load_boundary,
    mask_points,
    parse_boundary,
)
from app.services.trends import theil_sen

ALGORITHM_VERSION = "regional-stats-v1"

#: A single analysis pass refuses to buffer more than this many candidate rows.
MAX_SCAN_ROWS = 1_500_000
#: Regional analysis may span longer than a calendar view, but not indefinitely.
MAX_REGION_YEARS = 30

MIN_SEASONAL_YEARS = 2
MIN_SEASONAL_MONTHS = 6
MIN_TREND_YEARS = 8
MIN_ANOMALY_YEARS = 4
MAD_TO_SIGMA = 1.4826

#: A month contributes to climatology only when this share of its days is covered.
MONTH_COVERAGE_FLOOR = 0.8
#: A year is "complete" for trend purposes above this coverage share.
YEAR_COVERAGE_FLOOR = 0.9

SENSORS = ("MODIS", "VIIRS")
GAZETTEER_HALF_DEGREES = 6.0

@dataclass
class _SensorAggregate:
    count: int = 0
    frp_sum: float = 0.0
    frp_max: float | None = None
    high: int = 0


@dataclass
class _CellAggregate:
    count: int = 0
    frp_sum: float = 0.0
    frp_max: float | None = None
    years: set[int] = field(default_factory=set)


REGION_NOTE = (
    "Counts are satellite thermal detections, not fires. A boundary's bounding box is "
    "only a query prefilter; published counts are computed against the polygon."
)


# ---------------------------------------------------------------------------
# Region registry
# ---------------------------------------------------------------------------


def _slug_uuid(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"firewatch:region:{slug}")


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "region"
    return f"{base[:120]}-{uuid.uuid4().hex[:8]}"


def _gazetteer_boundary(place: Place) -> RegionGeometry:
    from app.services.regions import region_box

    box = region_box(place, GAZETTEER_HALF_DEGREES)
    return bbox_boundary(box.west, box.south, box.east, box.north)


def ensure_gazetteer_regions(session: Session) -> int:
    """
    Seed one approximate country region per gazetteer entry. Idempotent: IDs are
    deterministic UUIDv5 values, so a slug always resolves to the same region.
    """
    existing = set(
        session.scalars(
            select(GeographicRegion.slug).where(GeographicRegion.source == "gazetteer")
        ).all()
    )
    created = 0
    for place in COUNTRIES:
        if not place.iso:
            continue
        slug = f"country-{place.iso.lower()}"
        if slug in existing:
            continue
        boundary = _gazetteer_boundary(place)
        west, south, east, north = boundary.bbox
        session.add(
            GeographicRegion(
                id=_slug_uuid(slug),
                slug=slug,
                name=place.name,
                level="country",
                boundary_kind="bbox",
                geometry=boundary.geometry,
                bbox_west=west,
                bbox_south=south,
                bbox_east=east,
                bbox_north=north,
                area_km2=boundary.area_km2,
                vertices=boundary.vertices,
                boundary_version="gazetteer-v1",
                source="gazetteer",
                is_approximate=True,
                notes=(
                    "Approximate centroid box from the offline gazetteer, not a country "
                    "boundary. Import a real polygon to replace it."
                ),
            )
        )
        created += 1
    if created:
        session.commit()
    return created


def region_payload(region: GeographicRegion, *, include_geometry: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(region.id),
        "slug": region.slug,
        "name": region.name,
        "level": region.level,
        "boundary_kind": region.boundary_kind,
        "bbox": [
            region.bbox_west,
            region.bbox_south,
            region.bbox_east,
            region.bbox_north,
        ],
        "area_km2": region.area_km2,
        "vertices": region.vertices,
        "boundary_version": region.boundary_version,
        "source": region.source,
        "is_approximate": region.is_approximate,
        "notes": region.notes,
        "last_analyzed_at": region.last_analyzed_at,
        "last_analysis_algorithm": region.last_analysis_algorithm,
        "grid_degrees": CELL_DEGREES,
    }
    if include_geometry:
        payload["geometry"] = region.geometry
    return payload


def catalog(
    session: Session,
    *,
    level: str | None = None,
    query: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    ensure_gazetteer_regions(session)
    clauses = []
    if level:
        clauses.append(GeographicRegion.level == level.lower())
    if query:
        clauses.append(GeographicRegion.name.ilike(f"%{query.strip()}%"))
    total = session.scalar(
        select(func.count()).select_from(GeographicRegion).where(*clauses)
    )
    rows = session.scalars(
        select(GeographicRegion)
        .where(*clauses)
        .order_by(GeographicRegion.is_approximate, GeographicRegion.name)
        .limit(max(1, min(limit, 500)))
    ).all()
    return {
        "regions": [region_payload(row) for row in rows],
        "total": int(total or 0),
        "note": (
            "Gazetteer regions are approximate boxes and are labelled as such. "
            "Upload a GeoJSON boundary for an exact administrative or custom region."
        ),
    }


def get_region(session: Session, region_id: uuid.UUID) -> GeographicRegion:
    region = session.get(GeographicRegion, region_id)
    if region is None:
        raise AppError("not_found", "No region with that identifier.")
    return region


def create_region(
    session: Session,
    *,
    name: str,
    boundary: RegionGeometry,
    level: str = "custom",
    boundary_kind: str = "polygon",
    source: str = "custom",
    is_approximate: bool = False,
    notes: str | None = None,
    slug: str | None = None,
) -> GeographicRegion:
    clean_name = (name or "").strip()
    if not 2 <= len(clean_name) <= 200:
        raise AppError("bad_request", "Region name must be 1–200 characters.")
    west, south, east, north = boundary.bbox
    region = GeographicRegion(
        id=_slug_uuid(slug) if slug else uuid.uuid4(),
        slug=slug or _slugify(clean_name),
        name=clean_name,
        level=level.lower(),
        boundary_kind=boundary_kind,
        geometry=boundary.geometry,
        bbox_west=west,
        bbox_south=south,
        bbox_east=east,
        bbox_north=north,
        area_km2=boundary.area_km2,
        vertices=boundary.vertices,
        boundary_version="v1",
        source=source,
        is_approximate=is_approximate,
        notes=notes,
    )
    session.add(region)
    session.commit()
    return region


def create_custom_region(
    session: Session,
    *,
    name: str,
    geojson: dict[str, Any],
    level: str = "custom",
) -> GeographicRegion:
    return create_region(
        session,
        name=name,
        boundary=parse_boundary(geojson),
        level=level,
        boundary_kind="polygon",
        source="custom",
    )


def create_radius_region(
    session: Session, *, name: str, latitude: float, longitude: float, radius_km: float
) -> GeographicRegion:
    return create_region(
        session,
        name=name,
        boundary=circle_boundary(latitude, longitude, radius_km),
        level="radius",
        boundary_kind="circle",
        source="radius",
        notes=f"Radius buffer of {radius_km} km around {latitude:.4f}, {longitude:.4f}.",
    )


# ---------------------------------------------------------------------------
# Analysis pass
# ---------------------------------------------------------------------------


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _validate_window(start: date, end: date) -> None:
    if start > end:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    if (end - start).days + 1 > 366 * MAX_REGION_YEARS:
        raise AppError(
            "bad_request",
            f"Regional analysis is limited to {MAX_REGION_YEARS} years per run.",
        )


def _coverage_rows(
    session: Session, start: date, end: date, sensors: Sequence[str]
) -> dict[tuple[date, str], dict[str, int]]:
    statement = (
        select(
            SourceAvailability.observation_date,
            DataSource.sensor,
            SourceAvailability.status,
            func.count(),
        )
        .join(DataSource, DataSource.id == SourceAvailability.source_id)
        .where(
            SourceAvailability.observation_date >= start,
            SourceAvailability.observation_date <= end,
            DataSource.sensor.in_(list(sensors)),
        )
        .group_by(
            SourceAvailability.observation_date, DataSource.sensor, SourceAvailability.status
        )
    )
    coverage: dict[tuple[date, str], dict[str, int]] = {}
    for raw_day, sensor, status, count in session.execute(statement):
        key = (_as_date(raw_day), sensor)
        entry = coverage.setdefault(key, {"observed_sources": 0, "missing_sources": 0})
        normalised = (status or "").lower()
        if normalised in {"available", "empty"}:
            entry["observed_sources"] += int(count)
        else:
            entry["missing_sources"] += int(count)
    return coverage


def analyze_region(
    session: Session,
    region: GeographicRegion,
    *,
    start: date,
    end: date,
    sensor: str | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    """
    Compute region × day × sensor statistics for a window and persist them.

    One polygon-exact pass over the bbox-prefiltered observations. Re-running the
    same window replaces its rows, so results cannot accumulate stale counts.
    """
    _validate_window(start, end)
    requested = [sensor.upper()] if sensor else list(SENSORS)
    unknown = [item for item in requested if item not in SENSORS]
    if unknown:
        raise AppError("bad_request", f"Unknown sensor(s): {', '.join(unknown)}")

    geometry = load_boundary(region.geometry)
    shape = geometry.to_shape()
    dialect = dialect_name(session)
    day_expr = utc_day(FireObservation.acquired_at, dialect)

    lats: list[float] = []
    lons: list[float] = []
    meta: list[tuple[date, str, float | None, str | None]] = []

    statement = select(
        day_expr.label("day"),
        FireObservation.latitude,
        FireObservation.longitude,
        FireObservation.sensor,
        FireObservation.frp_mw,
        FireObservation.confidence_category,
    ).where(
        day_expr >= start,
        day_expr <= end,
        FireObservation.is_synthetic == synthetic,
        FireObservation.sensor.in_(requested),
        FireObservation.latitude >= region.bbox_south,
        FireObservation.latitude <= region.bbox_north,
        FireObservation.longitude >= region.bbox_west,
        FireObservation.longitude <= region.bbox_east,
    )

    candidates = 0
    for row in session.execute(statement).yield_per(100_000):
        lats.append(float(row.latitude))
        lons.append(float(row.longitude))
        meta.append(
            (
                _as_date(row.day),
                row.sensor,
                float(row.frp_mw) if row.frp_mw is not None else None,
                row.confidence_category,
            )
        )
        candidates += 1
        if candidates > MAX_SCAN_ROWS:
            raise AppError(
                "bad_request",
                "This region and period are too large for one analysis pass; narrow the period.",
                details={"max_rows": MAX_SCAN_ROWS, "rows": candidates},
            )

    mask = mask_points(shape, np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))

    daily: dict[tuple[date, str], _SensorAggregate] = {}
    cells: dict[tuple[int, int], _CellAggregate] = {}

    for index in np.flatnonzero(mask):
        day, sensor_code, frp, confidence = meta[int(index)]
        entry = daily.setdefault((day, sensor_code), _SensorAggregate())
        entry.count += 1
        if frp is not None:
            entry.frp_sum += frp
            if entry.frp_max is None or frp > entry.frp_max:
                entry.frp_max = frp
        if (confidence or "").lower() == "high":
            entry.high += 1

        lat_index, lon_index = cell_of(float(lats[int(index)]), float(lons[int(index)]))
        cell = cells.setdefault((lat_index, lon_index), _CellAggregate())
        cell.count += 1
        if frp is not None:
            cell.frp_sum += frp
            if cell.frp_max is None or frp > cell.frp_max:
                cell.frp_max = frp
        cell.years.add(day.year)

    coverage = _coverage_rows(session, start, end, requested)

    # Replace the window's rows; the grid is range-wide, so it is rebuilt.
    session.execute(
        delete(RegionalDailyStatistic).where(
            RegionalDailyStatistic.region_id == region.id,
            RegionalDailyStatistic.activity_date >= start,
            RegionalDailyStatistic.activity_date <= end,
        )
    )
    session.execute(
        delete(RegionalCellStatistic).where(RegionalCellStatistic.region_id == region.id)
    )

    rows: list[dict[str, Any]] = []
    covered_days = 0
    day_cursor = start
    while day_cursor <= end:
        totals = _SensorAggregate()
        observed_sources = 0
        missing_sources = 0
        for sensor_code in requested:
            sensor_entry = daily.get((day_cursor, sensor_code))
            cov = coverage.get(
                (day_cursor, sensor_code),
                {"observed_sources": 0, "missing_sources": 0},
            )
            observed_sources += cov["observed_sources"]
            missing_sources += cov["missing_sources"]
            if sensor_entry is None and cov["observed_sources"] == 0:
                continue
            payload = sensor_entry or _SensorAggregate()
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "region_id": region.id,
                    "activity_date": day_cursor,
                    "sensor": sensor_code,
                    "detection_count": payload.count,
                    "frp_sum_mw": round(payload.frp_sum, 3),
                    "frp_max_mw": round(payload.frp_max, 3)
                    if payload.frp_max is not None
                    else None,
                    "high_confidence_count": payload.high,
                    "coverage": {
                        "observed_sources": cov["observed_sources"],
                        "missing_sources": cov["missing_sources"],
                        "state": "observed" if cov["observed_sources"] else "unobserved",
                    },
                    "algorithm_version": ALGORITHM_VERSION,
                }
            )
            totals.count += payload.count
            totals.frp_sum += payload.frp_sum
            if payload.frp_max is not None and (
                totals.frp_max is None or payload.frp_max > totals.frp_max
            ):
                totals.frp_max = payload.frp_max
            totals.high += payload.high

        if totals.count > 0 or observed_sources > 0:
            covered_days += 1
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "region_id": region.id,
                    "activity_date": day_cursor,
                    "sensor": "ALL",
                    "detection_count": totals.count,
                    "frp_sum_mw": round(totals.frp_sum, 3),
                    "frp_max_mw": round(totals.frp_max, 3)
                    if totals.frp_max is not None
                    else None,
                    "high_confidence_count": totals.high,
                    "coverage": {
                        "observed_sources": observed_sources,
                        "missing_sources": missing_sources,
                        "requested_sources": len(requested),
                        "state": "observed" if observed_sources else "unobserved",
                    },
                    "algorithm_version": ALGORITHM_VERSION,
                }
            )
        day_cursor += timedelta(days=1)

    cell_rows = [
        {
            "id": uuid.uuid4(),
            "region_id": region.id,
            "lat_index": lat_index,
            "lon_index": lon_index,
            "detection_count": cell.count,
            "frp_sum_mw": round(cell.frp_sum, 3),
            "frp_max_mw": round(cell.frp_max, 3) if cell.frp_max is not None else None,
            "years_with_detections": len(cell.years),
            "first_year": min(cell.years) if cell.years else None,
            "last_year": max(cell.years) if cell.years else None,
            "algorithm_version": ALGORITHM_VERSION,
        }
        for (lat_index, lon_index), cell in cells.items()
    ]

    if rows:
        session.bulk_insert_mappings(RegionalDailyStatistic, rows)
    if cell_rows:
        session.bulk_insert_mappings(RegionalCellStatistic, cell_rows)

    region.last_analyzed_at = datetime.now(UTC)
    region.last_analysis_algorithm = ALGORITHM_VERSION
    session.commit()

    return {
        "status": "ok",
        "region_id": str(region.id),
        "window": {"start": start, "end": end},
        "sensors": requested,
        "synthetic": synthetic,
        "scanned_candidates": candidates,
        "detections_in_region": sum(item.count for item in daily.values()),
        "days_covered": covered_days,
        "days_requested": (end - start).days + 1,
        "rows_written": len(rows),
        "cells": len(cell_rows),
        "algorithm_version": ALGORITHM_VERSION,
        "notes": [
            REGION_NOTE,
            "The bounding box prefiltered candidates; counts use the polygon.",
            "A day is a real zero only when a source recorded coverage for it.",
        ],
    }


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------


def _stats_rows(
    session: Session,
    region_id: uuid.UUID,
    start: date,
    end: date,
    sensor: str = "ALL",
) -> list[dict[str, Any]]:
    statement = (
        select(
            RegionalDailyStatistic.activity_date,
            RegionalDailyStatistic.detection_count,
            RegionalDailyStatistic.frp_sum_mw,
            RegionalDailyStatistic.frp_max_mw,
            RegionalDailyStatistic.high_confidence_count,
            RegionalDailyStatistic.coverage,
        )
        .where(
            RegionalDailyStatistic.region_id == region_id,
            RegionalDailyStatistic.activity_date >= start,
            RegionalDailyStatistic.activity_date <= end,
            RegionalDailyStatistic.sensor == sensor,
        )
        .order_by(RegionalDailyStatistic.activity_date)
    )
    return [
        {
            "date": _as_date(row.activity_date),
            "detections": int(row.detection_count),
            "frp_sum_mw": float(row.frp_sum_mw or 0.0),
            "frp_max_mw": float(row.frp_max_mw) if row.frp_max_mw is not None else None,
            "high_confidence": int(row.high_confidence_count or 0),
            "coverage": row.coverage,
        }
        for row in session.execute(statement).all()
    ]


def _not_analyzed(region: GeographicRegion, start: date, end: date, sensor: str) -> dict[str, Any]:
    return {
        "status": "not_analyzed",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        "requirements": {
            "note": (
                "This region has not been analysed for this window. Run "
                f"POST /api/v1/regions/{region.id}/analyze with the same period, then reload. "
                "No statistic is invented for an unanalysed region."
            )
        },
    }


def _monthly(
    rows: Sequence[dict[str, Any]],
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["date"].year, row["date"].month)
        entry = buckets.setdefault(
            key,
            {
                "year": key[0],
                "month": key[1],
                "detections": 0,
                "frp_sum_mw": 0.0,
                "frp_max_mw": None,
                "high_confidence": 0,
                "covered_days": 0,
                "active_days": 0,
            },
        )
        entry["detections"] += row["detections"]
        entry["frp_sum_mw"] += row["frp_sum_mw"]
        if row["frp_max_mw"] is not None and (
            entry["frp_max_mw"] is None or row["frp_max_mw"] > entry["frp_max_mw"]
        ):
            entry["frp_max_mw"] = row["frp_max_mw"]
        entry["high_confidence"] += row["high_confidence"]
        entry["covered_days"] += 1
        if row["detections"] > 0:
            entry["active_days"] += 1

    months: list[dict[str, Any]] = []
    for key in sorted(buckets):
        entry = buckets[key]
        days = _days_in_month(key[0], key[1])
        # Coverage is measured against the days requested in this window, not the
        # whole month: a six-day request must not look like a 6/31 month.
        expected = days
        if start is not None and end is not None:
            month_start = date(key[0], key[1], 1)
            month_end = date(key[0], key[1], days)
            expected = (min(month_end, end) - max(month_start, start)).days + 1
        months.append(
            {
                **entry,
                "days_in_month": days,
                "expected_days": expected,
                "coverage": round(entry["covered_days"] / expected, 4) if expected else 0.0,
                "frp_sum_mw": round(entry["frp_sum_mw"], 3),
                "frp_max_mw": round(entry["frp_max_mw"], 3)
                if entry["frp_max_mw"] is not None
                else None,
            }
        )
    return months


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _yearly(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        entry = buckets.setdefault(
            row["date"].year,
            {
                "year": row["date"].year,
                "detections": 0,
                "frp_sum_mw": 0.0,
                "frp_max_mw": None,
                "high_confidence": 0,
                "covered_days": 0,
                "active_days": 0,
            },
        )
        entry["detections"] += row["detections"]
        entry["frp_sum_mw"] += row["frp_sum_mw"]
        if row["frp_max_mw"] is not None and (
            entry["frp_max_mw"] is None or row["frp_max_mw"] > entry["frp_max_mw"]
        ):
            entry["frp_max_mw"] = row["frp_max_mw"]
        entry["high_confidence"] += row["high_confidence"]
        entry["covered_days"] += 1
        if row["detections"] > 0:
            entry["active_days"] += 1

    years: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for year in sorted(buckets):
        entry = buckets[year]
        days_in_year = 366 if _is_leap(year) else 365
        coverage = min(1.0, entry["covered_days"] / days_in_year)
        change = None
        if previous is not None and previous["detections"] > 0:
            change = round(
                (entry["detections"] - previous["detections"]) / previous["detections"], 4
            )
        years.append(
            {
                **entry,
                "days_in_year": days_in_year,
                "coverage": round(coverage, 4),
                "complete": coverage >= YEAR_COVERAGE_FLOOR,
                "yoy_change": change,
                "frp_sum_mw": round(entry["frp_sum_mw"], 3),
                "frp_max_mw": round(entry["frp_max_mw"], 3)
                if entry["frp_max_mw"] is not None
                else None,
            }
        )
        previous = entry
    return years


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _seasonality(
    rows: Sequence[dict[str, Any]], months: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    usable = [entry for entry in months if entry["coverage"] >= MONTH_COVERAGE_FLOOR]
    per_month: dict[int, list[float]] = defaultdict(list)
    for entry in usable:
        per_month[int(entry["month"])].append(float(entry["detections"]))

    overall = fmean([fmean(values) for values in per_month.values()]) if per_month else None

    profile: list[dict[str, Any]] = []
    for month_number in range(1, 13):
        values = per_month.get(month_number, [])
        mean_value = fmean(values) if values else None
        profile.append(
            {
                "month": month_number,
                "mean": round(mean_value, 3) if mean_value is not None else None,
                "median": round(float(median(values)), 3) if values else None,
                "p90": round(float(np.percentile(values, 90)), 3) if values else None,
                "years": len(values),
                "sufficient": len(values) >= MIN_SEASONAL_YEARS,
                "index": round(mean_value / overall, 4)
                if mean_value is not None and overall
                else None,
            }
        )

    sufficient_months = [item for item in profile if item["sufficient"]]
    years_available = sorted({int(entry["year"]) for entry in usable})

    if len(years_available) < MIN_SEASONAL_YEARS:
        status = "single_year" if years_available else "insufficient_history"
    elif len(sufficient_months) >= MIN_SEASONAL_MONTHS:
        status = "ok"
    else:
        status = "partial"

    peak = trough = amplitude = None
    if status == "ok":
        ranked = sorted(sufficient_months, key=lambda item: float(item["index"]))
        trough, peak = ranked[0], ranked[-1]
        if trough["index"] and trough["index"] > 0:
            amplitude = round(float(peak["index"]) / float(trough["index"]), 3)

    # Day-of-year curve: a 15-day window across every available year.
    day_values: dict[date, float] = {row["date"]: float(row["detections"]) for row in rows}
    day_profile: list[dict[str, Any]] = []
    for doy in range(1, 367):
        samples = []
        sample_years = set()
        for year in years_available:
            probe = date(year, 1, 1) + timedelta(days=doy - 1)
            for offset in range(-7, 8):
                neighbour = probe + timedelta(days=offset)
                value = day_values.get(neighbour)
                if value is not None:
                    samples.append(value)
                    sample_years.add(neighbour.year)
        day_profile.append(
            {
                "day_of_year": doy,
                "mean": round(fmean(samples), 3) if samples else None,
                "samples": len(samples),
                "years": len(sample_years),
            }
        )

    if status == "ok" and len(years_available) == 2:
        note = (
            "Two years is the minimum; treat this profile as preliminary until a third "
            "year confirms it."
        )
    elif status == "single_year":
        note = (
            "Only one year of coverage is available. The profile describes that year; it "
            "is not a seasonal climatology and no index, peak or trough is claimed."
        )
    elif status == "partial":
        note = (
            f"{len(sufficient_months)} of 12 months have at least {MIN_SEASONAL_YEARS} "
            "years of coverage; peak and trough are withheld until at least "
            f"{MIN_SEASONAL_MONTHS} months qualify."
        )
    else:
        note = "No covered month is available in this window, so no profile can be computed."

    return {
        "status": status,
        "method": "monthly-climatology",
        "version": ALGORITHM_VERSION,
        "years": years_available,
        "months": profile,
        "peak_month": peak["month"] if peak else None,
        "trough_month": trough["month"] if trough else None,
        "seasonal_amplitude": amplitude,
        "sufficient_months": len(sufficient_months),
        "required_months": MIN_SEASONAL_MONTHS,
        "day_of_year": {
            "smoothing_days": 15,
            "coverage": "mean of a ±7-day window across available years",
            "points": day_profile,
        },
        "requirements": {
            "needed_years": MIN_SEASONAL_YEARS,
            "available_years": len(years_available),
            "note": note,
        },
    }


def mann_kendall(values: Sequence[float]) -> dict[str, Any]:
    """
    Mann–Kendall trend test with tie correction, plus Sen's slope.

    The p-value assumes independent observations. ``serial_correlation`` is
    returned so a caller can see when that assumption is weak; a p-value alone is
    never treated as proof.
    """
    clean = [float(value) for value in values]
    n = len(clean)
    if n < 3:
        return {
            "status": "insufficient_data",
            "n": n,
            "s": None,
            "z": None,
            "p_value": None,
            "trend": "unknown",
            "sen_slope_per_year": None,
            "serial_correlation": None,
        }

    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            difference = clean[j] - clean[i]
            s += 1 if difference > 0 else (-1 if difference < 0 else 0)

    counts: dict[float, int] = {}
    for value in clean:
        counts[value] = counts.get(value, 0) + 1
    ties = sum(count * (count - 1) * (2 * count + 5) for count in counts.values())
    variance = (n * (n - 1) * (2 * n + 5) - ties) / 18.0

    if variance <= 0:
        z = 0.0
    elif s > 0:
        z = (s - 1) / math.sqrt(variance)
    elif s < 0:
        z = (s + 1) / math.sqrt(variance)
    else:
        z = 0.0

    p_value = math.erfc(abs(z) / math.sqrt(2))
    if p_value < 0.05 and z > 0:
        trend = "significant_increase"
    elif p_value < 0.05 and z < 0:
        trend = "significant_decrease"
    else:
        trend = "no_significant_trend"

    sen_slope, _ = theil_sen([float(index) for index in range(n)], clean)

    serial = None
    if n >= 3:
        mean_value = fmean(clean)
        denominator = sum((value - mean_value) ** 2 for value in clean)
        if denominator:
            numerator = sum(
                (clean[index] - mean_value) * (clean[index - 1] - mean_value)
                for index in range(1, n)
            )
            serial = round(numerator / denominator, 4)

    return {
        "status": "ok",
        "n": n,
        "s": s,
        "z": round(z, 4),
        "p_value": round(p_value, 6),
        "trend": trend,
        "sen_slope_per_year": round(sen_slope, 4),
        "sen_slope_per_decade": round(sen_slope * 10, 3),
        "serial_correlation": serial,
        "tie_correction": ties > 0,
    }


def _rolling(values: Sequence[tuple[date, float]], window: int) -> list[dict[str, Any]]:
    out = []
    for index, (day, _value) in enumerate(values):
        if index + 1 < window:
            continue
        window_values = [item[1] for item in values[index + 1 - window : index + 1]]
        out.append(
            {
                "date": day,
                "mean": round(fmean(window_values), 3),
                "days": window,
            }
        )
    return out


def _trends(
    rows: Sequence[dict[str, Any]],
    years: Sequence[dict[str, Any]],
    months: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    complete = [year for year in years if year["complete"]]
    values = [float(year["detections"]) for year in complete]
    mk = mann_kendall(values)

    status = "ok" if len(complete) >= MIN_TREND_YEARS else "insufficient_years"

    seasonal: list[dict[str, Any]] = []
    for month in range(1, 13):
        series = [
            float(item["detections"])
            for item in months
            if item["month"] == month and item["coverage"] >= MONTH_COVERAGE_FLOOR
        ]
        if len(series) >= 5:
            result = mann_kendall(series)
            seasonal.append(
                {
                    "month": month,
                    "years": len(series),
                    "trend": result["trend"],
                    "p_value": result["p_value"],
                    "sen_slope_per_year": result["sen_slope_per_year"],
                }
            )

    daily_points = [(row["date"], float(row["detections"])) for row in rows]

    return {
        "status": status,
        "method": "mann-kendall + sen-slope",
        "version": ALGORITHM_VERSION,
        "annual": [
            {
                "year": year["year"],
                "detections": year["detections"],
                "complete": year["complete"],
                "coverage": year["coverage"],
            }
            for year in years
        ],
        "yoy": [
            {"year": year["year"], "change": year["yoy_change"]}
            for year in years
            if year["yoy_change"] is not None
        ],
        "rolling": {
            "daily_30": _rolling(daily_points, 30)[-1:] if len(daily_points) >= 30 else [],
            "daily_90": _rolling(daily_points, 90)[-1:] if len(daily_points) >= 90 else [],
            "monthly_12": _rolling(
                [
                    (date(item["year"], item["month"], 1), float(item["detections"]))
                    for item in months
                ],
                12,
            )[-1:]
            if len(months) >= 12
            else [],
        },
        "mann_kendall": mk,
        "significant": status == "ok" and mk["p_value"] is not None and mk["p_value"] < 0.05,
        "seasonal_trends": seasonal,
        "requirements": {
            "needed_years": MIN_TREND_YEARS,
            "available_complete_years": len(complete),
            "note": (
                "Requirement satisfied."
                if status == "ok"
                else (
                    f"A significance test needs {MIN_TREND_YEARS} complete years; this window "
                    f"has {len(complete)}. Year-over-year changes are still shown, without a "
                    "significance claim."
                )
            ),
        },
        "caveats": [
            "Mann–Kendall assumes independent observations; serial_correlation is reported.",
            "Only complete years enter the test; partial years are labelled complete=false.",
            "A change in sensor availability is not a change in fire activity.",
        ],
    }


def _robust_baseline(values: Sequence[float]) -> tuple[float, float, float]:
    center = float(median(values))
    mad = float(median([abs(value - center) for value in values]))
    scale = MAD_TO_SIGMA * mad
    if scale == 0 and len(values) > 1:
        scale = float(pstdev(values))
    return center, mad, scale


def _severity(z: float) -> str:
    if z >= 5:
        return "critical"
    if z >= 4:
        return "high"
    if z >= 3:
        return "moderate"
    if z <= -3:
        return "below_baseline"
    return "normal"


def _anomalies(months: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_month: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in months:
        if item["coverage"] >= MONTH_COVERAGE_FLOOR:
            by_month[item["month"]].append(item)

    items = []
    evaluated = 0
    for month, entries in by_month.items():
        if len(entries) < MIN_ANOMALY_YEARS + 1:
            continue
        for entry in entries:
            history = [
                float(other["detections"]) for other in entries if other["year"] != entry["year"]
            ]
            if len(history) < MIN_ANOMALY_YEARS:
                continue
            center, mad, scale = _robust_baseline(history)
            evaluated += 1
            if scale > 0:
                z = (entry["detections"] - center) / scale
            elif entry["detections"] > center:
                z = float("nan")
            else:
                z = 0.0
            severity = "unknown_scale" if z != z else _severity(z)
            deviation = (
                round((entry["detections"] - center) / center, 4) if center else None
            )
            items.append(
                {
                    "period": f"{entry['year']}-{month:02d}",
                    "year": entry["year"],
                    "month": month,
                    "observed": entry["detections"],
                    "expected_median": round(center, 3),
                    "mad": round(mad, 3),
                    "scale": round(scale, 3),
                    "deviation_ratio": deviation,
                    "robust_z": None if z != z else round(z, 3),
                    "severity": severity,
                    "baseline_years": len(history),
                    "method": "robust_z_same_month",
                    "version": ALGORITHM_VERSION,
                }
            )

    ranked = [item for item in items if item["severity"] in {"moderate", "high", "critical"}]
    ranked.sort(key=lambda item: abs(item["robust_z"] or 0), reverse=True)

    return {
        "status": "ok" if evaluated else "insufficient_history",
        "method": {
            "name": "robust_z_same_month",
            "version": ALGORITHM_VERSION,
            "comparison": "same calendar month in other years",
            "min_baseline_years": MIN_ANOMALY_YEARS,
        },
        "evaluated_months": evaluated,
        "count": len(ranked),
        "anomalies": ranked,
        "requirements": {
            "needed_baseline_years": MIN_ANOMALY_YEARS,
            "note": (
                "Requirement satisfied."
                if evaluated
                else (
                    f"A same-month baseline needs {MIN_ANOMALY_YEARS} other years for that "
                    "month; this window does not have them, so no anomaly is claimed."
                )
            ),
        },
        "notes": [
            "January is compared with historical Januarys, never with the whole year.",
            "A negative deviation is reported separately as below_baseline.",
        ],
    }


def _overall_status(region: GeographicRegion, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "analyzed": bool(rows) or region.last_analyzed_at is not None,
        "rows": len(rows),
    }


def overview(
    session: Session,
    region: GeographicRegion,
    *,
    start: date,
    end: date,
    sensor: str = "ALL",
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)

    months = _monthly(rows, start=start, end=end)
    years = _yearly(rows)
    seasonality = _seasonality(rows, months)
    trends = _trends(rows, years, months)
    anomalies = _anomalies(months)

    total = sum(row["detections"] for row in rows)
    covered = len(rows)
    requested_days = (end - start).days + 1
    peak = max(
        (item for item in seasonality["months"] if item["mean"] is not None),
        key=lambda item: float(item["mean"]),
        default=None,
    )
    mk = trends["mann_kendall"]

    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        "totals": {
            "detections": total,
            "frp_sum_mw": round(sum(row["frp_sum_mw"] for row in rows), 3),
            "frp_max_mw": max(
                (row["frp_max_mw"] for row in rows if row["frp_max_mw"] is not None),
                default=None,
            ),
            "high_confidence": sum(row["high_confidence"] for row in rows),
            "active_days": sum(1 for row in rows if row["detections"] > 0),
            "covered_days": covered,
            "requested_days": requested_days,
            "coverage": round(covered / requested_days, 4) if requested_days else 0.0,
        },
        "peak_month": (
            {
                "month": peak["month"],
                "mean_detections": peak["mean"],
                "years": peak["years"],
            }
            if peak
            else None
        ),
        "trend": {
            "status": trends["status"],
            "direction": mk["trend"],
            "p_value": mk["p_value"],
            "sen_slope_per_year": mk["sen_slope_per_year"],
            "complete_years": trends["requirements"]["available_complete_years"],
            "note": trends["requirements"]["note"],
        },
        "anomalies": {
            "status": anomalies["status"],
            "count": anomalies["count"],
            "evaluated_months": anomalies["evaluated_months"],
        },
        "sensor_note": (
            "Combined detections. MODIS and VIIRS are never assumed interchangeable; "
            "see /sensor-comparison before comparing their levels."
        ),
        "notes": [REGION_NOTE, seasonality["requirements"]["note"]],
    }


def monthly_series(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        "months": _monthly(rows, start=start, end=end),
        "notes": [REGION_NOTE],
    }


def yearly_series(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        "years": _yearly(rows),
        "notes": [REGION_NOTE],
    }


def daily_series(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        "days": [
            {
                **row,
                "date": row["date"].isoformat(),
            }
            for row in rows
        ],
        "notes": [REGION_NOTE, "A day is present only when it was analysed or observed."],
    }


def seasonality(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    months = _monthly(rows, start=start, end=end)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        **{key: value for key, value in _seasonality(rows, months).items()},
        "notes": [REGION_NOTE],
    }


def trends(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    months = _monthly(rows, start=start, end=end)
    years = _yearly(rows)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        **_trends(rows, years, months),
    }


def anomalies(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> dict[str, Any]:
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        return _not_analyzed(region, start, end, sensor)
    return {
        "status": "ok",
        "region": region_payload(region),
        "window": {"start": start, "end": end, "sensor": sensor},
        **_anomalies(_monthly(rows, start=start, end=end)),
    }


def spatial_activity(
    session: Session,
    region: GeographicRegion,
    *,
    limit: int = 200,
    recurring_only: bool = False,
) -> dict[str, Any]:
    statement = (
        select(RegionalCellStatistic)
        .where(RegionalCellStatistic.region_id == region.id)
        .order_by(RegionalCellStatistic.detection_count.desc())
        .limit(max(1, min(limit, 2000)))
    )
    cells = session.scalars(statement).all()
    if not cells:
        return {
            "status": "not_analyzed",
            "region": region_payload(region),
            "requirements": {
                "note": (
                    "No spatial summary is stored for this region yet. Run "
                    f"POST /api/v1/regions/{region.id}/analyze first."
                )
            },
        }

    years_seen = {cell.last_year for cell in cells if cell.last_year is not None}
    span = (max(years_seen) - min(years_seen) + 1) if years_seen else 1
    payload = []
    for cell in cells:
        latitude, longitude = cell_centre(cell.lat_index, cell.lon_index)
        recurrence = cell.years_with_detections / span if span else 0.0
        if recurring_only and cell.years_with_detections < 2:
            continue
        payload.append(
            {
                "lat_index": cell.lat_index,
                "lon_index": cell.lon_index,
                "latitude": round(latitude, 4),
                "longitude": round(longitude, 4),
                "detections": int(cell.detection_count),
                "frp_sum_mw": round(float(cell.frp_sum_mw or 0.0), 3),
                "frp_max_mw": round(float(cell.frp_max_mw), 3)
                if cell.frp_max_mw is not None
                else None,
                "years_with_detections": int(cell.years_with_detections),
                "recurrence": round(recurrence, 4),
                "first_year": cell.first_year,
                "last_year": cell.last_year,
            }
        )

    return {
        "status": "ok",
        "region": region_payload(region),
        "grid_degrees": CELL_DEGREES,
        "cells": payload,
        "returned": len(payload),
        "notes": [
            REGION_NOTE,
            "This is a 0.5° screening grid, not an H3 index (H3 is not installed here).",
            "Recurrence is the share of years in the analysed window with a detection in the cell.",
        ],
    }


def sensor_comparison(
    session: Session, region: GeographicRegion, *, start: date, end: date
) -> dict[str, Any]:
    rows_all = _stats_rows(session, region.id, start, end, "ALL")
    if not rows_all:
        return _not_analyzed(region, start, end, "ALL")

    per_sensor: dict[str, dict[str, Any]] = {}
    monthly_by_sensor: dict[str, dict[str, float]] = {}
    for sensor in SENSORS:
        rows = _stats_rows(session, region.id, start, end, sensor)
        if not rows:
            continue
        totals = {
            "detections": sum(row["detections"] for row in rows),
            "active_days": sum(1 for row in rows if row["detections"] > 0),
            "covered_days": len(rows),
            "first_date": rows[0]["date"].isoformat(),
            "last_date": rows[-1]["date"].isoformat(),
        }
        per_sensor[sensor] = totals
        monthly_by_sensor[sensor] = {
            f"{row['date'].year}-{row['date'].month:02d}": float(row["detections"]) for row in rows
        }

    correlation = None
    if len(monthly_by_sensor) == 2:
        import numpy as _np

        keys = sorted(set(monthly_by_sensor["MODIS"]) & set(monthly_by_sensor["VIIRS"]))
        if len(keys) >= 3:
            left = _np.array([monthly_by_sensor["MODIS"][key] for key in keys])
            right = _np.array([monthly_by_sensor["VIIRS"][key] for key in keys])
            if left.std() > 0 and right.std() > 0:
                correlation = {
                    "pearson_r": round(float(_np.corrcoef(left, right)[0, 1]), 4),
                    "months": len(keys),
                    "method": "monthly totals where both sensors have coverage",
                }

    status = "ok" if len(per_sensor) == 2 else "single_sensor"
    return {
        "status": status,
        "region": region_payload(region),
        "window": {"start": start, "end": end},
        "sensors": per_sensor,
        "correlation": correlation,
        "notes": [
            REGION_NOTE,
            "MODIS and VIIRS have different records, pixel sizes and channels; levels are "
            "never assumed interchangeable.",
            "A gap in one sensor's coverage is not evidence of a change in fire activity.",
        ],
        "requirements": {
            "note": (
                "Both sensors are present in this window."
                if status == "ok"
                else (
                    "Only one sensor has coverage in this window; no cross-sensor "
                    "comparison is claimed."
                )
            )
        },
    }


def export_csv(
    session: Session, region: GeographicRegion, *, start: date, end: date, sensor: str
) -> tuple[str, str]:
    """Monthly and yearly regional statistics as one self-describing CSV."""
    rows = _stats_rows(session, region.id, start, end, sensor)
    if not rows:
        raise AppError(
            "not_found",
            "This region has no analysed statistics for that window.",
            details={"region_id": str(region.id)},
        )
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "region",
            "region_id",
            "level",
            "sensor",
            "period_type",
            "period",
            "detections",
            "frp_sum_mw",
            "frp_max_mw",
            "high_confidence",
            "covered_days",
            "coverage",
            "algorithm_version",
        ]
    )
    for month in _monthly(rows, start=start, end=end):
        writer.writerow(
            [
                region.name,
                str(region.id),
                region.level,
                sensor,
                "month",
                f"{month['year']}-{month['month']:02d}",
                month["detections"],
                month["frp_sum_mw"],
                month["frp_max_mw"],
                month["high_confidence"],
                month["covered_days"],
                month["coverage"],
                ALGORITHM_VERSION,
            ]
        )
    for year in _yearly(rows):
        writer.writerow(
            [
                region.name,
                str(region.id),
                region.level,
                sensor,
                "year",
                str(year["year"]),
                year["detections"],
                year["frp_sum_mw"],
                year["frp_max_mw"],
                year["high_confidence"],
                year["covered_days"],
                year["coverage"],
                ALGORITHM_VERSION,
            ]
        )
    filename = f"firewatch-{region.slug}-{start.isoformat()}-{end.isoformat()}.csv"
    return buffer.getvalue(), filename
