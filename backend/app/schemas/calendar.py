"""Historical burning calendar schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.observations import ObservationOut

BucketState = Literal["active", "quiet", "unobserved"]


class BucketCoverage(BaseModel):
    """Days in the bucket by what the sources reported."""

    observed: int = Field(description="Days a selected source observed (including empty days)")
    empty: int = Field(description="Days a source was checked and returned no detections")
    missing: int = Field(description="Days a source reported the date as missing or pending")
    unknown: int = Field(description="Days with no availability record at all")


class CalendarBucket(BaseModel):
    start: date
    end: date
    label: str
    state: BucketState = Field(
        description=(
            "active: detections present; quiet: observed with none; "
            "unobserved: no availability recorded, never read as zero"
        )
    )
    coverage: BucketCoverage
    detections: int
    modis: int
    viirs: int
    matched_viirs: int = Field(
        default=0, description="VIIRS detections with a cross-sensor association"
    )
    harmonized: int = Field(
        default=0, description="detections minus matched_viirs; never a fire count"
    )
    frp_sum_mw: float
    frp_max_mw: float | None = None
    high_confidence: int


class CalendarTotals(BaseModel):
    detections: int
    modis: int
    viirs: int
    matched_viirs: int = 0
    harmonized: int = 0
    frp_sum_mw: float
    frp_max_mw: float | None = None
    high_confidence: int
    active_buckets: int
    quiet_buckets: int
    unobserved_buckets: int
    buckets: int


class CalendarResponse(BaseModel):
    granularity: Literal["day", "week", "month", "year"]
    start_date: date
    end_date: date
    buckets: list[CalendarBucket]
    totals: CalendarTotals
    notes: list[str]


class CalendarDrilldown(BaseModel):
    bucket: CalendarBucket
    total: int
    returned: int
    limit: int
    items: list[ObservationOut]


class CalendarMonth(BaseModel):
    """A month with data, for the calendar's month picker."""

    month: str = Field(description="YYYY-MM")
    start: date
    end: date
    detections: int
    active_days: int
    observed_days: int


class TrendPoint(BaseModel):
    """One day of the trend series. ``value`` is null when nothing observed it."""

    date: date
    value: float | None = None
    observed: bool
    trailing_mean: float | None = None
    severity: str = Field(
        description="normal, moderate/high/critical, below_baseline, or unobserved"
    )


class TrendBlock(BaseModel):
    status: Literal["ok", "insufficient_history"]
    method: str
    version: str
    metric: str
    observations: int
    slope_per_day: float | None = None
    slope_per_30_days: float | None = None
    direction: Literal["rising", "falling", "flat", "unknown"]
    change_ratio: float | None = None
    confidence: Literal["low", "medium", "high"]
    coverage: float
    level_median: float | None = None
    flat_band_per_30_days: float | None = None
    requirements: dict[str, Any]
    series: list[TrendPoint]


class SeasonMonth(BaseModel):
    month: int
    label: str
    mean: float | None = None
    years: int
    sufficient: bool
    index: float | None = None


class SeasonalityBlock(BaseModel):
    status: Literal["ok", "partial", "single_year", "insufficient_history"]
    method: str
    version: str
    metric: str
    years: list[int]
    years_requested: int
    first_year: int
    last_year: int
    months: list[SeasonMonth]
    baseline_mean: float | None = None
    sufficient_months: int
    required_months: int
    peak_month: str | None = None
    trough_month: str | None = None
    seasonal_amplitude: float | None = None
    requirements: dict[str, Any]


class CalendarAnomalyBlock(BaseModel):
    status: str | None = None
    method: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None
    count: int
    items: list[dict[str, Any]]
    evaluated_days: int
    requirements: dict[str, Any] | None = None


class CalendarWindow(BaseModel):
    start: date
    end: date
    days: int
    observed_days: int
    missing_days: int
    coverage: float
    metric: str
    history_start: date


class CalendarIntelligenceResponse(BaseModel):
    """Trend, anomaly markers and seasonal profile for one calendar window."""

    status: str
    method: dict[str, Any]
    window: CalendarWindow
    trend: TrendBlock
    anomalies: CalendarAnomalyBlock
    seasonality: SeasonalityBlock
    notes: list[str]
