"""Anomaly detection over daily detection counts."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.schemas.analytics import AnomaliesResponse
from app.services.anomalies import (
    DEFAULT_BASELINE_DAYS,
    DEFAULT_MIN_BASELINE_DAYS,
    DEFAULT_MIN_WINDOW_DAYS,
    DEFAULT_Z_THRESHOLD,
    detect_anomalies,
)
from app.services.calendar import validate_span
from app.services.observation_queries import BBox, ObservationFilters

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=AnomaliesResponse, summary="Detected daily anomalies")
def list_anomalies(
    start_date: date = Query(..., description="First evaluated day (UTC)"),
    end_date: date = Query(..., description="Last evaluated day (UTC)"),
    baseline_days: int = Query(DEFAULT_BASELINE_DAYS, ge=1, le=365),
    min_baseline_days: int = Query(DEFAULT_MIN_BASELINE_DAYS, ge=2, le=365),
    min_window_days: int = Query(DEFAULT_MIN_WINDOW_DAYS, ge=3, le=365),
    z_threshold: float = Query(DEFAULT_Z_THRESHOLD, ge=1, le=20),
    metric: str = Query("detections", pattern="^(detections|frp|high_confidence)$"),
    bbox: str | None = Query(None, description="west,south,east,north"),
    sensor: str | None = Query(None, description="MODIS or VIIRS"),
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> AnomaliesResponse:
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
    result = detect_anomalies(
        session,
        filters,
        start=start_date,
        end=end_date,
        baseline_days=baseline_days,
        min_baseline_days=min_baseline_days,
        min_window_days=min_window_days,
        z_threshold=z_threshold,
        metric=metric,
    )
    return AnomaliesResponse(**result)
