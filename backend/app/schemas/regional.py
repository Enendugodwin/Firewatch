"""Regional intelligence request models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CustomRegionRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    geometry: dict[str, Any] = Field(
        description="GeoJSON Polygon, MultiPolygon, Feature or FeatureCollection"
    )
    level: str = Field(default="custom", max_length=32)


class RadiusRegionRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0.05, le=2000)


class AnalyzeRequest(BaseModel):
    start_date: date
    end_date: date
    sensor: Literal["MODIS", "VIIRS"] | None = None
    synthetic: bool = False


class RegionOut(BaseModel):
    id: str
    slug: str
    name: str
    level: str
    boundary_kind: str
    bbox: list[float]
    area_km2: float | None = None
    vertices: int
    boundary_version: str
    source: str
    is_approximate: bool
    notes: str | None = None
    last_analyzed_at: datetime | None = None
    last_analysis_algorithm: str | None = None
    grid_degrees: float
    geometry: dict[str, Any] | None = None


class RegionCatalogOut(BaseModel):
    regions: list[RegionOut]
    total: int
    note: str
