"""System, registry and freshness schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.modules import ModuleStatus

FreshnessState = Literal["no_data", "stale", "delayed", "current", "unknown"]


class DatabaseStatus(BaseModel):
    dialect: str
    connected: bool
    postgis: bool | None = None
    latency_ms: float | None = None
    error: str | None = None


class DataStatus(BaseModel):
    """Everything the UI needs to describe data honestly."""

    freshness: FreshnessState
    freshness_reason: str
    firms_configured: bool
    sources_registered: int
    observations_stored: int | None = None
    last_ingested_at: datetime | None = None
    last_observation_at: datetime | None = None


class CapabilityStatus(BaseModel):
    authentication: bool = False
    rate_limiting: bool = False
    ai_assistant: bool = False
    reports: bool = False
    ingestion: bool = False
    spatial: bool = False


class ModuleStatusItem(BaseModel):
    key: str
    label: str
    route: str
    phase: str
    status: ModuleStatus
    summary: str
    planned: list[str] = Field(default_factory=list)


class SystemStatus(BaseModel):
    app_name: str
    app_version: str
    environment: str
    phase: str
    phase_name: str
    server_time: datetime
    uptime_seconds: float
    database: DatabaseStatus
    data: DataStatus
    capabilities: CapabilityStatus
    modules: list[ModuleStatusItem]


class SourceOut(BaseModel):
    code: str
    sensor: str
    satellite: str
    processing_level: str
    description: str
    status: Literal["not_ingested", "ingesting", "ok", "error"] = "not_ingested"
