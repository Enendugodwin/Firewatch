"""Trends, rankings and breakdowns for the analytics workspace."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics import analytics_summary
from app.services.calendar import validate_span
from app.services.observation_queries import BBox, ObservationFilters

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/summary",
    response_model=AnalyticsResponse,
    summary="Trend, rankings and breakdowns for a period",
)
def analytics(
    start_date: date = Query(..., description="First day (UTC)"),
    end_date: date = Query(..., description="Last day (UTC)"),
    bbox: str | None = Query(None, description="west,south,east,north"),
    sensor: str | None = Query(None, description="MODIS or VIIRS"),
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    top: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> AnalyticsResponse:
    if start_date > end_date:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
    validate_span(start_date, end_date)

    filters = ObservationFilters(
        bbox=BBox.parse(bbox) if bbox else None,
        sensor=sensor,
        satellite=satellite,
        min_frp=min_frp,
        daynight=daynight,
        min_confidence=min_confidence,
        synthetic=synthetic,
    )
    result = analytics_summary(
        session, filters, start=start_date, end=end_date, top=top
    )
    return AnalyticsResponse(**result)
