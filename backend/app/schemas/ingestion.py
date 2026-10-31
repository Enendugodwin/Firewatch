"""Ingestion request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    source_code: str = Field(description="Registered FIRMS product, e.g. VIIRS_SNPP_NRT")
    start_date: date
    end_date: date
    tile: str | None = Field(
        default=None,
        description="Tile key from /admin/ingestion/tiles; omit for the whole world",
    )
    bbox: str | None = Field(
        default=None,
        description="Custom area as west,south,east,north (overrides tile)",
    )
    run_harmonization: bool = True
    run_events: bool = True


class IngestResponse(BaseModel):
    run_id: str | None
    source_code: str
    status: str
    records_received: int
    records_inserted: int
    records_rejected: int
    partitions_completed: int
    partitions_skipped: int
    rejections: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    is_synthetic: bool = False
    harmonization: dict[str, Any] | None = None
    events: dict[str, Any] | None = None


class IngestionRunOut(BaseModel):
    id: str
    source_code: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_received: int
    records_inserted: int
    records_rejected: int
    is_synthetic: bool
    error_message: str | None = None
    query_parameters: dict[str, Any] = Field(default_factory=dict)


class SourceHealth(BaseModel):
    code: str
    sensor: str
    satellite: str
    processing_level: str
    registered: bool
    observations: int
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None


class TileOut(BaseModel):
    key: str
    bbox: str


class AvailabilityRequest(BaseModel):
    source_code: str
    start_date: date
    end_date: date
