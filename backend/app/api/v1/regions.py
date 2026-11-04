"""Regional intelligence: boundaries, analysis runs and read endpoints.

``GET /regions`` keeps the original gazetteer ranking (now with a ``region_id``
so it can link into a region); everything below ``/regions/{id}`` is the regional
trend and seasonality engine. Reads serve the materialised regional statistics —
they never scan the observation table.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_admin
from app.db.models import GeographicRegion
from app.db.session import get_session
from app.schemas.regional import (
    AnalyzeRequest,
    CustomRegionRequest,
    RadiusRegionRequest,
    RegionCatalogOut,
    RegionOut,
)
from app.services import regional as regional_service
from app.services.calendar import validate_span
from app.services.observation_queries import ObservationFilters
from app.services.regions import regional_profiles

router = APIRouter(prefix="/regions", tags=["regions"])

SENSOR_PATTERN = "^(ALL|MODIS|VIIRS)$"


def _check_range(start: date, end: date) -> None:
    if start > end:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )


@router.get("", summary="Regional profiles for a period")
def list_regions(
    start_date: date = Query(..., description="First day (UTC)"),
    end_date: date = Query(..., description="Last day (UTC)"),
    limit: int = Query(10, ge=1, le=50),
    names: str | None = Query(None, description="Comma-separated country names"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    validate_span(start_date, end_date)

    filters = ObservationFilters(
        start_date=start_date, end_date=end_date, synthetic=synthetic
    )
    wanted = [piece.strip() for piece in names.split(",")] if names else None
    payload = regional_profiles(session, filters, limit=limit, names=wanted)

    # Link each approximate profile to its seeded region so the UI can open the
    # regional engine without re-resolving the name.
    regional_service.ensure_gazetteer_regions(session)
    ids = {
        row.slug: str(row.id)
        for row in session.scalars(select(GeographicRegion)).all()
    }
    for profile in payload["regions"]:
        iso = profile.get("iso")
        profile["region_id"] = ids.get(f"country-{iso.lower()}") if iso else None
    return payload


@router.get(
    "/catalog",
    response_model=RegionCatalogOut,
    summary="Selectable regions (gazetteer, imported and custom boundaries)",
)
def region_catalog(
    level: str | None = Query(None, description="country, state, province, custom, radius"),
    q: str | None = Query(None, description="Name search"),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
) -> RegionCatalogOut:
    return RegionCatalogOut(**regional_service.catalog(session, level=level, query=q, limit=limit))


@router.post(
    "/custom",
    dependencies=[Depends(require_admin)],
    response_model=RegionOut,
    status_code=201,
    summary="Create a region from a GeoJSON boundary",
)
def create_custom_region(
    payload: CustomRegionRequest, session: Session = Depends(get_session)
) -> RegionOut:
    region = regional_service.create_custom_region(
        session,
        name=payload.name,
        geojson=payload.geometry,
        level=payload.level,
    )
    return RegionOut(**regional_service.region_payload(region))


@router.post(
    "/radius",
    dependencies=[Depends(require_admin)],
    response_model=RegionOut,
    status_code=201,
    summary="Create a circular region around a point",
)
def create_radius_region(
    payload: RadiusRegionRequest, session: Session = Depends(get_session)
) -> RegionOut:
    region = regional_service.create_radius_region(
        session,
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
    )
    return RegionOut(**regional_service.region_payload(region))


@router.get("/{region_id}", response_model=RegionOut, summary="One region boundary")
def get_region(
    region_id: uuid.UUID,
    include_geometry: bool = Query(False, description="Include the stored GeoJSON"),
    session: Session = Depends(get_session),
) -> RegionOut:
    region = regional_service.get_region(session, region_id)
    return RegionOut(
        **regional_service.region_payload(region, include_geometry=include_geometry)
    )


@router.post(
    "/{region_id}/analyze",
    dependencies=[Depends(require_admin)],
    summary="Compute and store regional statistics for a window",
)
def analyze_region(
    region_id: uuid.UUID,
    payload: AnalyzeRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """
    One polygon-exact analysis pass over a bbox-prefiltered scan, then the
    region × day × sensor rows every read endpoint serves. Re-running the same
    window replaces its rows.
    """
    region = regional_service.get_region(session, region_id)
    return regional_service.analyze_region(
        session,
        region,
        start=payload.start_date,
        end=payload.end_date,
        sensor=payload.sensor,
        synthetic=payload.synthetic,
    )


@router.get("/{region_id}/overview", summary="Regional overview for a window")
def region_overview(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.overview(session, region, start=start_date, end=end_date, sensor=sensor)


@router.get("/{region_id}/daily", summary="Daily regional detections")
def region_daily(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.daily_series(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get("/{region_id}/monthly", summary="Monthly regional statistics")
def region_monthly(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.monthly_series(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get("/{region_id}/yearly", summary="Annual regional statistics with YoY change")
def region_yearly(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.yearly_series(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get(
    "/{region_id}/seasonality",
    summary="Monthly climatology and day-of-year profile",
)
def region_seasonality(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.seasonality(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get(
    "/{region_id}/trends",
    summary="Mann–Kendall significance, Sen's slope and rolling means",
)
def region_trends(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.trends(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get(
    "/{region_id}/anomalies",
    summary="Months that are unusual for their own calendar month",
)
def region_anomalies(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.anomalies(
        session, region, start=start_date, end=end_date, sensor=sensor
    )


@router.get(
    "/{region_id}/spatial-activity",
    summary="Recurring-activity grid inside the region",
)
def region_spatial_activity(
    region_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=2000),
    recurring_only: bool = Query(False, description="Only cells seen in two or more years"),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    region = regional_service.get_region(session, region_id)
    return regional_service.spatial_activity(
        session, region, limit=limit, recurring_only=recurring_only
    )


@router.get(
    "/{region_id}/sensor-comparison",
    summary="MODIS versus VIIRS coverage and agreement in the region",
)
def region_sensor_comparison(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    return regional_service.sensor_comparison(
        session, region, start=start_date, end=end_date
    )


@router.get("/{region_id}/export", summary="Monthly and yearly regional CSV")
def region_export(
    region_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    sensor: str = Query("ALL", pattern=SENSOR_PATTERN),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    _check_range(start_date, end_date)
    region = regional_service.get_region(session, region_id)
    body, filename = regional_service.export_csv(
        session, region, start=start_date, end=end_date, sensor=sensor
    )
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
