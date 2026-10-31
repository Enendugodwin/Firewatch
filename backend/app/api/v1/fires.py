"""Fire observation search, inspection and map feeds."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import FireObservation
from app.db.session import get_session
from app.schemas.map import AggregateResponse
from app.schemas.observations import ObservationOut, ObservationPage
from app.services.map_aggregation import aggregate_observations
from app.services.observation_queries import (
    BBox,
    ObservationFilters,
    observation_to_dict,
    search_observations,
)

router = APIRouter(prefix="/fires", tags=["fires"])


def _filters(
    bbox: str | None,
    start_date: date | None,
    end_date: date | None,
    sensor: str | None,
    satellite: str | None,
    min_frp: float | None,
    daynight: str | None,
    synthetic: bool | None,
    min_confidence: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ObservationFilters:
    return ObservationFilters(
        bbox=BBox.parse(bbox) if bbox else None,
        start_date=start_date,
        end_date=end_date,
        start_at=start_at,
        end_at=end_at,
        sensor=sensor,
        satellite=satellite,
        min_frp=min_frp,
        daynight=daynight,
        min_confidence=min_confidence,
        synthetic=synthetic,
    )


@router.get("", response_model=ObservationPage, summary="Search fire observations")
def search_fires(
    bbox: str | None = Query(None, description="west,south,east,north"),
    start_date: date | None = None,
    end_date: date | None = None,
    start_at: datetime | None = Query(
        None, description="Exact start (ISO 8601, UTC), inclusive; overrides start_date"
    ),
    end_at: datetime | None = Query(
        None, description="Exact end (ISO 8601, UTC), exclusive; overrides end_date"
    ),
    sensor: str | None = Query(None, description="MODIS or VIIRS"),
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = Query(None, description="Filter labelled fixture data"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> ObservationPage:
    filters = _filters(
        bbox,
        start_date,
        end_date,
        sensor,
        satellite,
        min_frp,
        daynight,
        synthetic,
        min_confidence,
        start_at,
        end_at,
    )
    rows, total = search_observations(session, filters, limit=limit, offset=offset)
    return ObservationPage(
        items=[ObservationOut(**observation_to_dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sources", summary="Observation counts per FIRMS product")
def fire_sources(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    from sqlalchemy import func, select

    rows = session.execute(
        select(
            FireObservation.source_code,
            FireObservation.sensor,
            func.count(),
            func.max(FireObservation.acquired_at),
        )
        .group_by(FireObservation.source_code, FireObservation.sensor)
        .order_by(FireObservation.source_code)
    ).all()
    return [
        {
            "source_code": code,
            "sensor": sensor,
            "observations": int(count),
            "last_observation_at": latest,
            "synthetic": False,
        }
        for code, sensor, count, latest in rows
    ]


@router.get("/geojson", summary="Map-ready GeoJSON for the current filters")
def fires_geojson(
    bbox: str | None = Query(None, description="west,south,east,north"),
    start_date: date | None = None,
    end_date: date | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    sensor: str | None = None,
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = None,
    limit: int = Query(2000, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """
    GeoJSON is only for bounded result sets; global/zoomed-out views must use
    server-side aggregation or vector tiles so the browser never receives the
    full historical dataset.
    """
    filters = _filters(
        bbox,
        start_date,
        end_date,
        sensor,
        satellite,
        min_frp,
        daynight,
        synthetic,
        min_confidence,
        start_at,
        end_at,
    )
    rows, total = search_observations(session, filters, limit=limit, offset=0)
    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "id": str(row.id),
                "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
                "properties": {
                    "id": str(row.id),
                    "sensor": row.sensor,
                    "satellite": row.satellite,
                    "acquired_at": row.acquired_at.isoformat(),
                    "confidence": row.confidence_category,
                    "frp_mw": row.frp_mw,
                    "daynight": row.daynight,
                    "source": row.source_code,
                    "synthetic": row.is_synthetic,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "returned": len(features),
            "total": total,
            "truncated": total > len(features),
            "limit": limit,
        },
    }


@router.get(
    "/aggregate",
    response_model=AggregateResponse,
    summary="Viewport aggregation for zoomed-out map views",
)
def aggregate_fires(
    bbox: str = Query(..., description="west,south,east,north (required)"),
    zoom: int = Query(3, ge=0, le=14),
    start_date: date | None = None,
    end_date: date | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    sensor: str | None = Query(None, description="MODIS or VIIRS"),
    satellite: str | None = None,
    min_frp: float | None = Query(None, ge=0),
    daynight: str | None = Query(None, pattern="^[DdNn]$"),
    min_confidence: str | None = Query(None, pattern="^(?i)(low|nominal|high)$"),
    synthetic: bool | None = None,
    limit: int = Query(6000, ge=1, le=20000),
    session: Session = Depends(get_session),
) -> AggregateResponse:
    """
    Gridded counts so a world view never requests every stored detection.

    ``count`` is a count of detections in that cell, not a count of fires.
    """
    area = BBox.parse(bbox)
    filters = _filters(
        bbox,
        start_date,
        end_date,
        sensor,
        satellite,
        min_frp,
        daynight,
        synthetic,
        min_confidence,
        start_at,
        end_at,
    )
    result = aggregate_observations(session, filters, bbox=area, zoom=zoom, limit=limit)
    return AggregateResponse(**result)


@router.get("/{observation_id}", response_model=ObservationOut, summary="Observation details")
def get_fire(observation_id: str, session: Session = Depends(get_session)) -> ObservationOut:
    from sqlalchemy.exc import StatementError

    try:
        row = session.get(FireObservation, observation_id)
    except (ValueError, StatementError) as exc:
        raise AppError("not_found", "No observation with that identifier.") from exc
    if row is None:
        raise AppError("not_found", "No observation with that identifier.")
    return ObservationOut(**observation_to_dict(row))
