"""Analytics: trend series, rankings and breakdowns over stored detections.

Everything is computed from the same filtered set as the map and the calendar, so
a number shown here always reconciles with those views. Counts are detections.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name, grid_index
from app.db.models import FireObservation
from app.services.normalization import satellite_label
from app.services.observation_queries import ObservationFilters
from app.services.rollups import activity_rows, cell_rows, day_of

#: Rankings use a coarse grid, not administrative boundaries: a "cell" is a
#: geographic area, never a country.
RANKING_CELL_DEGREES = 2.0


def _days(start: date, end: date) -> list[date]:
    out: list[date] = []
    cursor = start
    while cursor <= end:
        out.append(cursor)
        cursor += timedelta(days=1)
    return out


def _top_cells(
    session: Session, filters: ObservationFilters, *, limit: int
) -> list[dict[str, Any]]:
    """Ranked cells. Aggregated directly over the table: wrapping a wide select
    in a subquery makes SQLite materialise every row first."""
    cell = RANKING_CELL_DEGREES
    rolled = cell_rows(session, filters, limit=limit)
    if rolled is not None:
        return [
            {
                "latitude": round((float(row.lat_index) + 0.5) * cell - 90.0, 4),
                "longitude": round((float(row.lon_index) + 0.5) * cell - 180.0, 4),
                "detections": int(row.detections or 0),
                "frp_sum_mw": round(float(row.frp_sum_mw or 0.0), 2),
                "frp_max_mw": round(float(row.frp_max_mw), 2)
                if row.frp_max_mw is not None
                else None,
            }
            for row in rolled
        ]

    dialect = dialect_name(session)
    lon_index = grid_index(FireObservation.longitude, 180.0, cell, dialect)
    lat_index = grid_index(FireObservation.latitude, 90.0, cell, dialect)

    statement = filters.apply(
        select(
            lon_index.label("lon_index"),
            lat_index.label("lat_index"),
            func.count().label("count"),
            func.sum(FireObservation.frp_mw).label("frp_sum_mw"),
            func.max(FireObservation.frp_mw).label("frp_max_mw"),
        )
    ).group_by(lon_index, lat_index)
    statement = statement.order_by(func.count().desc()).limit(limit)

    cells = []
    for lon_idx, lat_idx, count, frp_sum, frp_max in session.execute(statement).all():
        cells.append(
            {
                "latitude": round((float(lat_idx) + 0.5) * cell - 90.0, 4),
                "longitude": round((float(lon_idx) + 0.5) * cell - 180.0, 4),
                "detections": int(count),
                "frp_sum_mw": round(float(frp_sum or 0.0), 2),
                "frp_max_mw": round(float(frp_max), 2) if frp_max is not None else None,
            }
        )
    return cells


def _grouped_scan(session: Session, filters: ObservationFilters) -> dict[str, Any]:
    """
    Rows grouped by day and the dimensions every breakdown needs, from the daily
    rollup when possible. Ten million rows cannot afford one scan per breakdown,
    so the series, sensor split, confidence, day/night, satellites and products
    all come from this single result.
    """
    rows = activity_rows(session, filters)

    daily: dict[Any, dict[str, Any]] = {}
    confidence = {"high": 0, "nominal": 0, "low": 0, "unknown": 0}
    daynight = {"D": 0, "N": 0, "unknown": 0}
    satellites: dict[str, dict[str, Any]] = {}
    products: dict[str, int] = {}

    for row in rows:
        day_value = day_of(row.day)
        count = int(row.detections or 0)
        frp_sum = float(row.frp_sum_mw or 0.0)
        frp_max = float(row.frp_max_mw) if row.frp_max_mw is not None else None

        bucket = daily.setdefault(
            day_value,
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

        category = (row.confidence_category or "unknown").lower()
        confidence[category if category in confidence else "unknown"] += count
        if category == "high":
            bucket["high_confidence"] += count

        code = (row.daynight or "").upper()
        daynight[code if code in ("D", "N") else "unknown"] += count

        label = satellite_label(row.satellite) or row.satellite or "unknown"
        entry = satellites.setdefault(
            label, {"satellite": label, "detections": 0, "frp_sum_mw": 0.0}
        )
        entry["detections"] += count
        entry["frp_sum_mw"] += frp_sum

        products[row.source_code] = products.get(row.source_code, 0) + count

    return {
        "daily": daily,
        "confidence": confidence,
        "daynight": daynight,
        "satellites": sorted(
            satellites.values(), key=lambda item: item["detections"], reverse=True
        ),
        "products": sorted(
            ({"source_code": code, "detections": count} for code, count in products.items()),
            key=lambda item: item["detections"],
            reverse=True,
        ),
    }


def analytics_summary(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    top: int = 10,
) -> dict[str, Any]:
    grouped = _grouped_scan(session, filters)
    daily = grouped["daily"]
    days = _days(start, end)

    series: list[dict[str, Any]] = []
    total_detections = 0
    total_modis = 0
    total_viirs = 0
    total_frp = 0.0
    total_frp_max: float | None = None
    total_high = 0
    active_days = 0
    peak_detections: dict[str, Any] = {"date": None, "detections": 0}
    peak_frp: dict[str, Any] = {"date": None, "frp_mw": None}

    for day in days:
        metrics = daily.get(day, {})
        detections = int(metrics.get("detections", 0))
        frp_sum = float(metrics.get("frp_sum_mw", 0.0))
        day_max = metrics.get("frp_max_mw")

        series.append(
            {
                "date": day,
                "detections": detections,
                "modis": int(metrics.get("modis", 0)),
                "viirs": int(metrics.get("viirs", 0)),
                "frp_sum_mw": round(frp_sum, 2),
            }
        )

        total_detections += detections
        total_modis += int(metrics.get("modis", 0))
        total_viirs += int(metrics.get("viirs", 0))
        total_frp += frp_sum
        total_high += int(metrics.get("high_confidence", 0))
        if detections > 0:
            active_days += 1
        if detections > peak_detections["detections"]:
            peak_detections = {"date": day, "detections": detections}
        if day_max is not None:
            if peak_frp["frp_mw"] is None or day_max > peak_frp["frp_mw"]:
                peak_frp = {"date": day, "frp_mw": float(day_max)}
            if total_frp_max is None or day_max > total_frp_max:
                total_frp_max = float(day_max)

    totals = {
        "detections": total_detections,
        "modis": total_modis,
        "viirs": total_viirs,
        "frp_sum_mw": round(total_frp, 2),
        "frp_max_mw": round(total_frp_max, 2) if total_frp_max is not None else None,
        "high_confidence": total_high,
        "active_days": active_days,
        "days": len(days),
        "mean_daily_detections": (
            round(total_detections / len(days), 1) if days else 0.0
        ),
    }

    top_cells = _top_cells(session, filters, limit=max(1, min(top, 50)))

    return {
        "start_date": start,
        "end_date": end,
        "totals": totals,
        "series": series,
        "top_cells": top_cells,
        "cell_degrees": RANKING_CELL_DEGREES,
        "peaks": {"detections": peak_detections, "frp": peak_frp},
        "confidence": grouped["confidence"],
        "daynight": grouped["daynight"],
        "satellites": grouped["satellites"],
        "products": grouped["products"],
        "synthetic_detections": 0,
        "notes": [
            "Counts are thermal detections, not fires.",
            "Rankings use a fixed geographic grid, not administrative boundaries.",
            "Days without observations are shown as zero detections only in the series; "
            "check data coverage before reading a gap as quiet.",
        ],
    }
