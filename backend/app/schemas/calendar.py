"""Historical burning calendar schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal

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
    frp_sum_mw: float
    frp_max_mw: float | None = None
    high_confidence: int


class CalendarTotals(BaseModel):
    detections: int
    modis: int
    viirs: int
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
