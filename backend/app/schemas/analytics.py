"""Analytics and anomaly response schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyticsTotals(BaseModel):
    detections: int
    modis: int
    viirs: int
    frp_sum_mw: float
    frp_max_mw: float | None = None
    high_confidence: int
    active_days: int
    days: int
    mean_daily_detections: float


class DailyPoint(BaseModel):
    date: date
    detections: int
    modis: int
    viirs: int
    frp_sum_mw: float


class TopCell(BaseModel):
    latitude: float
    longitude: float
    detections: int
    frp_sum_mw: float
    frp_max_mw: float | None = None


class SensorBreakdown(BaseModel):
    satellite: str
    detections: int
    frp_sum_mw: float


class ProductBreakdown(BaseModel):
    source_code: str
    detections: int


class Breakdowns(BaseModel):
    confidence: dict[str, int]
    daynight: dict[str, int]
    satellites: list[SensorBreakdown]
    products: list[ProductBreakdown]
    synthetic_detections: int


class AnalyticsResponse(Breakdowns):
    start_date: date
    end_date: date
    totals: AnalyticsTotals
    series: list[DailyPoint]
    top_cells: list[TopCell]
    cell_degrees: float
    peaks: dict[str, Any]
    notes: list[str]


class AnomalyMethod(BaseModel):
    name: str
    version: str
    baseline_days: int
    min_baseline_days: int
    z_threshold: float
    metric: str
    mad_to_sigma: float
    comparison: str
    baseline_source: str = Field(
        default="preceding",
        description="preceding: earlier observed days; within_window: short-history fallback",
    )
    min_window_days: int = 4


class AnomalyBaseline(BaseModel):
    days: int
    median: float
    mad: float
    scale: float


class AnomalyPoint(BaseModel):
    date: date
    observed: float
    expected: float
    deviation: float
    robust_z: float | None = None
    severity: Literal[
        "normal", "below_baseline", "moderate", "high", "critical", "unknown_scale"
    ]
    explanation: str | None = None


class AnomalyRequirements(BaseModel):
    needed_days: int
    available_days: int
    note: str = Field(description="What is missing when the engine cannot score")


class AnomaliesResponse(BaseModel):
    status: Literal["ok", "insufficient_history"]
    method: AnomalyMethod
    baseline: AnomalyBaseline | None = None
    points: list[AnomalyPoint]
    anomalies: list[AnomalyPoint]
    evaluated_days: int
    observed_baseline_days: int
    requirements: AnomalyRequirements
    notes: list[str]
