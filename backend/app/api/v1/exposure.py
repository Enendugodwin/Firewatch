"""Exposure screening against operator-registered assets."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.services.calendar import validate_span
from app.services.exposure import (
    asset_counts,
    create_asset,
    delete_asset,
    list_assets,
    screen_assets,
)
from app.services.observation_queries import ObservationFilters

router = APIRouter(prefix="/exposure", tags=["exposure"])


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str | None = Field(default=None, max_length=48)


class AssetOut(BaseModel):
    id: str
    name: str
    category: str
    latitude: float
    longitude: float


def _asset_out(asset: Any) -> AssetOut:
    return AssetOut(
        id=str(asset.id),
        name=asset.name,
        category=asset.category,
        latitude=asset.latitude,
        longitude=asset.longitude,
    )


@router.get("", summary="Exposure screening summary")
def exposure_summary(session: Session = Depends(get_session)) -> dict[str, object]:
    return {
        "asset_count": asset_counts(session),
        "endpoints": ["/api/v1/exposure/assets", "/api/v1/exposure/screen"],
        "note": (
            "Screening measures proximity to detections for assets you register. "
            "No population or infrastructure dataset is bundled, so this is not a "
            "risk score."
        ),
    }


@router.get("/assets", response_model=list[AssetOut], summary="Watched assets")
def get_assets(session: Session = Depends(get_session)) -> list[AssetOut]:
    return [_asset_out(asset) for asset in list_assets(session)]


@router.post("/assets", response_model=AssetOut, status_code=201, summary="Register an asset")
def add_asset(payload: AssetIn, session: Session = Depends(get_session)) -> AssetOut:
    asset = create_asset(
        session,
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        category=payload.category,
    )
    return _asset_out(asset)


@router.delete("/assets/{asset_id}", status_code=204, summary="Remove an asset")
def remove_asset(asset_id: str, session: Session = Depends(get_session)) -> None:
    if not delete_asset(session, asset_id):
        raise AppError("not_found", "No watched asset with that identifier.")


@router.get("/screen", summary="Detections near each watched asset")
def screen(
    start_date: date = Query(..., description="First day (UTC)"),
    end_date: date = Query(..., description="Last day (UTC)"),
    radius_km: float = Query(50.0, gt=0, le=2000),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if start_date > end_date:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
    validate_span(start_date, end_date)

    filters = ObservationFilters(
        start_date=start_date, end_date=end_date, synthetic=synthetic
    )
    return screen_assets(session, filters, radius_km=radius_km)
