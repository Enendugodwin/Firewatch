"""History runner request and job schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class HistoryDatasetOut(BaseModel):
    key: str
    label: str
    sources: list[str]
    history: bool


class HistoryRegionOut(BaseModel):
    key: str
    name: str
    bbox: str
    note: str


class HistoryWindowOut(BaseModel):
    start_date: date
    end_date: date


class HistorySourcePlanOut(BaseModel):
    source_code: str
    requested_start: date
    requested_end: date
    coverage_start: date | None = None
    coverage_end: date | None = None
    coverage_known: bool
    windows: list[HistoryWindowOut]
    days: int
    note: str | None = None


class HistoryPlanRequest(BaseModel):
    datasets: list[str] = Field(min_length=1, description="Dataset keys, e.g. modis_history")
    start_date: date
    end_date: date
    region: str | None = Field(None, description="Catalogue region key")
    bbox: str | None = Field(None, description="west,south,east,north, alternative to region")
    harmonize: bool = Field(
        False, description="Run the association pass over the ingested span afterwards"
    )
    refresh_every: int = Field(
        100, ge=0, le=10000, description="Refresh rollups every N windows; 0 = only at the end"
    )
    resume: bool = Field(True, description="Rerun skips completed partitions and days")


class HistoryJobCreate(HistoryPlanRequest):
    pass


class HistoryPlanOut(BaseModel):
    request: dict[str, Any]
    tile: dict[str, Any]
    total_requests: int
    total_days: int
    both_sensors: bool
    harmonization_span: dict[str, str] | None = None
    sources: list[HistorySourcePlanOut]
    warnings: list[str]


class HistoryJobOut(BaseModel):
    id: str
    kind: str
    status: str
    datasets: list[str]
    region: str | None
    bbox: str | None
    start_date: date
    end_date: date
    harmonize: bool
    progress: dict[str, Any]
    summary: dict[str, Any]
    error_message: str | None
    cancel_requested: bool
    stale: bool = Field(
        False, description="A running job whose process has stopped updating it"
    )
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
