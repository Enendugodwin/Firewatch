"""Server-side viewport aggregation for the global fire map.

Zoomed-out views must never download the full observation set. Cells are computed
in SQL over a shifted coordinate so truncation is equivalent to floor in both
SQLite and PostgreSQL, keeping the same code path portable.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name, grid_index
from app.db.models import FireObservation
from app.services.observation_queries import BBox, ObservationFilters

#: Never aggregate finer than ~5.5 km (0.05°) or coarser than 45°.
MIN_CELL_DEGREES = 0.05
MAX_CELL_DEGREES = 45.0


def grid_degrees(zoom: int) -> float:
    """Cell size for a zoom level: 45° at z0 down to 0.05° at high zoom."""
    zoom = max(0, min(14, int(zoom)))
    raw = 360.0 / (2 ** (zoom + 2))
    return max(MIN_CELL_DEGREES, min(MAX_CELL_DEGREES, raw))


def aggregate_observations(
    session: Session,
    filters: ObservationFilters,
    *,
    bbox: BBox,
    zoom: int,
    limit: int = 6000,
) -> dict[str, Any]:
    cell = grid_degrees(zoom)

    # Filter once, then aggregate over that derived table so filters and
    # grouping cannot diverge.
    scoped = filters.apply(select(FireObservation)).subquery()

    dialect = dialect_name(session)
    lon_index = grid_index(scoped.c.longitude, 180.0, cell, dialect)
    lat_index = grid_index(scoped.c.latitude, 90.0, cell, dialect)

    statement = (
        select(
            lon_index.label("lon_index"),
            lat_index.label("lat_index"),
            func.count().label("count"),
            func.sum(case((scoped.c.sensor == "MODIS", 1), else_=0)).label("modis"),
            func.sum(case((scoped.c.sensor == "VIIRS", 1), else_=0)).label("viirs"),
            func.max(scoped.c.frp_mw).label("max_frp_mw"),
            func.max(scoped.c.acquired_at).label("latest_acquired_at"),
        )
        .group_by(lon_index, lat_index)
        .order_by(func.count().desc())
        .limit(limit + 1)
    )

    rows = session.execute(statement).all()
    truncated = len(rows) > limit
    rows = rows[:limit]

    cells = []
    total = 0
    for lon_idx, lat_idx, count, modis, viirs, max_frp, latest in rows:
        total += int(count)
        cells.append(
            {
                "longitude": round((float(lon_idx) + 0.5) * cell - 180.0, 6),
                "latitude": round((float(lat_idx) + 0.5) * cell - 90.0, 6),
                "count": int(count),
                "modis": int(modis or 0),
                "viirs": int(viirs or 0),
                "max_frp_mw": float(max_frp) if max_frp is not None else None,
                "latest_acquired_at": latest,
            }
        )

    return {
        "cells": cells,
        "cell_degrees": cell,
        "zoom": int(zoom),
        "total_detections": total,
        "returned_cells": len(cells),
        "truncated": truncated,
        "bbox": bbox.as_list(),
    }
