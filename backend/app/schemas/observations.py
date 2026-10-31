"""Observation, match and event response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ObservationOut(BaseModel):
    id: str
    source_code: str
    source_record_id: str
    sensor: str
    satellite: str
    latitude: float
    longitude: float
    acquired_at: datetime
    confidence_raw: int | None = None
    confidence_category: str | None = None
    brightness_temperature: float | None = None
    brightness_channel: str | None = None
    frp_mw: float | None = None
    scan_km: float | None = None
    track_km: float | None = None
    daynight: str | None = None
    processing_version: str | None = None
    source_product: str
    quality_flags: dict[str, Any] = Field(default_factory=dict)
    is_synthetic: bool = False


class ObservationPage(BaseModel):
    items: list[ObservationOut]
    total: int
    limit: int
    offset: int


class ObservationBrief(BaseModel):
    id: str
    source_code: str
    sensor: str
    satellite: str
    latitude: float
    longitude: float
    acquired_at: datetime
    confidence_category: str | None = None
    frp_mw: float | None = None


class MatchOut(BaseModel):
    id: str
    observation_a: ObservationBrief
    observation_b: ObservationBrief
    temporal_delta_seconds: int
    spatial_distance_m: float
    footprint_overlap: float | None = None
    association_score: float
    match_status: str
    components: dict[str, Any]
    algorithm_version: str
    created_at: datetime


class MatchPage(BaseModel):
    items: list[MatchOut]
    total: int
    limit: int
    offset: int


class EventOut(BaseModel):
    id: str
    first_detected_at: datetime
    last_detected_at: datetime
    centroid_latitude: float
    centroid_longitude: float
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float
    observation_count: int
    sensor_count: int
    maximum_frp_mw: float | None = None
    aggregate_frp_mw: float | None = None
    clustering_method: str
    clustering_parameters: dict[str, Any]
    methodology_version: str


class HarmonizationSummary(BaseModel):
    observations: int
    modis_observations: int
    viirs_observations: int
    synthetic_observations: int
    matches_total: int
    matches_probable: int
    matches_possible: int
    matches_rejected: int
    events: int
    multi_sensor_events: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    last_run_scope: dict[str, Any] | None = None
    algorithm_version: str


class AlgorithmRunOut(BaseModel):
    id: str
    kind: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    parameters: dict[str, Any]
    stats: dict[str, Any]
    algorithm_version: str
    is_synthetic: bool
    error_message: str | None = None


class MatchRunRequest(BaseModel):
    """Overrides for the association model; defaults match the specification."""

    synthetic: bool | None = Field(
        default=None, description="Scope; omit to process both real and fixture data"
    )
    time_window_minutes: int = Field(default=180, ge=1, le=1440)
    max_distance_m: float = Field(default=2000.0, gt=0, le=50_000)
    probable_threshold: float = Field(default=0.75, ge=0, le=1)
    possible_threshold: float = Field(default=0.55, ge=0, le=1)
    store_threshold: float = Field(default=0.35, ge=0, le=1)
    run_events: bool = True
    bbox: str | None = Field(
        default=None, description="Restrict the analysis to west,south,east,north"
    )
    start_date: date | None = None
    end_date: date | None = None


class MatchRunResponse(BaseModel):
    scopes: list[dict[str, Any]]
    events: list[dict[str, Any]] = Field(default_factory=list)
