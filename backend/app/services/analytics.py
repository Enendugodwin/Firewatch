"""Analytics: trend series, rankings and breakdowns over stored detections.

Everything is computed from the same filtered set as the map and the calendar, so
a number shown here always reconciles with those views. Counts are detections.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.db.models import FireObservation
from app.services.calendar import daily_metrics
from app.services.normalization import satellite_label
from app.services.observation_queries import ObservationFilters

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
    lon_index = cast((FireObservation.longitude + 180.0) / cell, Integer)
    lat_index = cast((FireObservation.latitude + 90.0) / cell, Integer)

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


def _breakdown(session: Session, filters: ObservationFilters) -> dict[str, Any]:
    confidence = {"high": 0, "nominal": 0, "low": 0, "unknown": 0}
    rows = session.execute(
        filters.apply(
            select(FireObservation.confidence_category, func.count()).group_by(
                FireObservation.confidence_category
            )
        )
    ).all()
    for category, count in rows:
        key = (category or "unknown").lower()
        confidence[key if key in confidence else "unknown"] += int(count)

    daynight = {"D": 0, "N": 0, "unknown": 0}
    rows = session.execute(
        filters.apply(
            select(FireObservation.daynight, func.count()).group_by(FireObservation.daynight)
        )
    ).all()
    for code, count in rows:
        key = (code or "").upper()
        daynight[key if key in ("D", "N") else "unknown"] += int(count)

    satellites = [
        {
            "satellite": satellite_label(satellite) or satellite or "unknown",
            "detections": int(count),
            "frp_sum_mw": round(float(frp or 0.0), 2),
        }
        for satellite, count, frp in session.execute(
            filters.apply(
                select(
                    FireObservation.satellite,
                    func.count(),
                    func.sum(FireObservation.frp_mw),
                ).group_by(FireObservation.satellite)
            )
        ).all()
    ]
    satellites.sort(key=lambda item: item["detections"], reverse=True)

    products = [
        {"source_code": code, "detections": int(count)}
        for code, count in session.execute(
            filters.apply(
                select(FireObservation.source_code, func.count()).group_by(
                    FireObservation.source_code
                )
            )
        ).all()
    ]
    products.sort(key=lambda item: item["detections"], reverse=True)

    synthetic = (
        session.scalar(
            filters.apply(
                select(func.count())
                .select_from(FireObservation)
                .where(FireObservation.is_synthetic.is_(True))
            )
        )
        or 0
    )

    return {
        "confidence": confidence,
        "daynight": daynight,
        "satellites": satellites,
        "products": products,
        "synthetic_detections": int(synthetic),
    }


def analytics_summary(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    top: int = 10,
) -> dict[str, Any]:
    daily = daily_metrics(session, filters)
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

    breakdown = _breakdown(session, filters)
    top_cells = _top_cells(session, filters, limit=max(1, min(top, 50)))

    return {
        "start_date": start,
        "end_date": end,
        "totals": totals,
        "series": series,
        "top_cells": top_cells,
        "cell_degrees": RANKING_CELL_DEGREES,
        "peaks": {"detections": peak_detections, "frp": peak_frp},
        **breakdown,
        "notes": [
            "Counts are thermal detections, not fires.",
            "Rankings use a fixed geographic grid, not administrative boundaries.",
            "Days without observations are shown as zero detections only in the series; "
            "check data coverage before reading a gap as quiet.",
        ],
    }
