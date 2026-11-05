"""Server-side viewport aggregation for the global fire map.

Zoomed-out views must never download the full observation set. Two paths:

* **Rollup path** — when the requested cell is at least 2° and the filters are
  dimensions the cell rollup stores, aggregate the 2° rollup into the requested
  coarser cell. A world view reads thousands of rows instead of millions.
* **Live path** — otherwise compute cells in SQL over the observations. Cells are
  computed over a shifted coordinate so truncation is equivalent to floor in both
  SQLite and PostgreSQL.

The response states which path answered and the cell size actually used, because
the rollup snaps to a 2° multiple and never pretends to a finer resolution.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name, grid_index
from app.db.models import FireObservation
from app.services import rollups
from app.services.observation_queries import BBox, ObservationFilters

#: Never aggregate finer than ~5.5 km (0.05°) or coarser than 45°.
MIN_CELL_DEGREES = 0.05
MAX_CELL_DEGREES = 45.0
#: The rollup is built on 2° cells, so it cannot answer a finer map cell.
ROLLUP_CELL_DEGREES = 2.0


def grid_degrees(zoom: int) -> float:
    """Cell size for a zoom level: 45° at z0 down to 0.05° at high zoom."""
    zoom = max(0, min(14, int(zoom)))
    raw = 360.0 / (2 ** (zoom + 2))
    return max(MIN_CELL_DEGREES, min(MAX_CELL_DEGREES, raw))


def rollup_cell_degrees(cell: float) -> float | None:
    """
    Snap a requested cell to the nearest 2° multiple the rollup can serve.

    Returns None below 2°, where the rollup cannot help and the live scan is the
    only honest answer.
    """
    if cell < ROLLUP_CELL_DEGREES:
        return None
    return max(ROLLUP_CELL_DEGREES, round(cell / ROLLUP_CELL_DEGREES) * ROLLUP_CELL_DEGREES)


def aggregate_observations(
    session: Session,
    filters: ObservationFilters,
    *,
    bbox: BBox,
    zoom: int,
    limit: int = 6000,
) -> dict[str, Any]:
    cell = grid_degrees(zoom)
    effective = rollup_cell_degrees(cell)
    if effective is not None:
        rollup_rows = rollups.map_cells(
            session, filters, bbox=bbox, cell_degrees=effective, limit=limit + 1
        )
        if rollup_rows is not None:
            truncated = len(rollup_rows) > limit
            rollup_rows = rollup_rows[:limit]
            cells = []
            total = 0
            total_matched = 0
            for row in rollup_rows:
                total += row["detections"]
                total_matched += int(row.get("matched_viirs") or 0)
                cells.append(
                    {
                        "longitude": round(
                            (float(row["lon_index"]) + 0.5) * effective - 180.0, 6
                        ),
                        "latitude": round(
                            (float(row["lat_index"]) + 0.5) * effective - 90.0, 6
                        ),
                        "count": row["detections"],
                        "modis": row["modis"],
                        "viirs": row["viirs"],
                        "matched_viirs": int(row.get("matched_viirs") or 0),
                        "max_frp_mw": row["max_frp_mw"],
                        # The rollup has no per-detection timestamps.
                        "latest_acquired_at": None,
                    }
                )
            return {
                "cells": cells,
                "cell_degrees": effective,
                "requested_cell_degrees": cell,
                "zoom": int(zoom),
                "total_detections": total,
                "matched_viirs": total_matched,
                "returned_cells": len(cells),
                "truncated": truncated,
                "bbox": bbox.as_list(),
                "source": "rollup",
                "harmonized": filters.harmonized,
                "note": (
                    "Aggregated from the 2° cell rollup; the returned cell size is the "
                    "nearest 2° multiple at or above the requested size."
                ),
            }

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
                "matched_viirs": 0,
                "max_frp_mw": float(max_frp) if max_frp is not None else None,
                "latest_acquired_at": latest,
            }
        )

    return {
        "cells": cells,
        "cell_degrees": cell,
        "requested_cell_degrees": cell,
        "zoom": int(zoom),
        "total_detections": total,
        "matched_viirs": 0,
        "returned_cells": len(cells),
        "truncated": truncated,
        "bbox": bbox.as_list(),
        "source": "live",
        "harmonized": filters.harmonized,
        "note": (
            "Harmonized view: VIIRS detections with a probable or possible MODIS "
            "association are excluded, so counts are deduplicated detections, not fires."
            if filters.harmonized
            else None
        ),
    }
