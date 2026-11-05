"""Viewport aggregation schemas for the global fire map."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FireCell(BaseModel):
    """One aggregated viewport cell. Counts are detections, never fires."""

    longitude: float = Field(description="Cell centre longitude")
    latitude: float = Field(description="Cell centre latitude")
    count: int
    modis: int
    viirs: int
    matched_viirs: int = 0
    max_frp_mw: float | None = None
    latest_acquired_at: datetime | None = None


class AggregateResponse(BaseModel):
    cells: list[FireCell]
    cell_degrees: float
    requested_cell_degrees: float | None = None
    zoom: int
    total_detections: int
    matched_viirs: int = 0
    returned_cells: int
    truncated: bool
    bbox: list[float]
    source: str = Field(default="live", description="rollup or live scan")
    harmonized: bool = Field(
        default=False,
        description="True when MODIS-associated VIIRS detections were removed",
    )
    note: str | None = None
