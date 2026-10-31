"""Ingestion administration: triggers, job history, source health."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import DataSource, FireObservation, IngestionRun
from app.db.session import get_session
from app.schemas.ingestion import (
    AvailabilityRequest,
    IngestAllRequest,
    IngestAllResponse,
    IngestionRequest,
    IngestionRunOut,
    IngestResponse,
    SourceHealth,
    TileOut,
)
from app.services import events as events_service
from app.services import harmonization as harmonization_service
from app.services.firms.tiles import WORLD, Tile, global_tiles
from app.services.ingestion import ingest_range, sync_availability
from app.services.observation_queries import BBox
from app.services.sources import FIRMS_SOURCES, get_source

router = APIRouter(prefix="/admin/ingestion", tags=["admin"])


@router.get("/tiles", response_model=list[TileOut], summary="Ingestion tiles")
def list_tiles() -> list[TileOut]:
    return [TileOut(key="world", bbox=WORLD.bbox)] + [
        TileOut(key=tile.key, bbox=tile.bbox) for tile in global_tiles()
    ]


@router.get("/jobs", response_model=list[IngestionRunOut], summary="Ingestion job history")
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[IngestionRunOut]:
    rows = session.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    ).all()
    return [
        IngestionRunOut(
            id=str(row.id),
            source_code=row.source.source_code if row.source else None,
            status=row.status,
            started_at=row.started_at,
            completed_at=row.completed_at,
            records_received=row.records_received,
            records_inserted=row.records_inserted,
            records_rejected=row.records_rejected,
            is_synthetic=row.is_synthetic,
            error_message=row.error_message,
            query_parameters=row.query_parameters or {},
        )
        for row in rows
    ]


@router.get("/sources", response_model=list[SourceHealth], summary="Source health")
def source_health(
    session: Session = Depends(get_session),
) -> list[SourceHealth]:
    registered = {row.source_code for row in session.query(DataSource).all()}
    counts = {
        code: int(count)
        for code, count in session.execute(
            select(FireObservation.source_code, func.count()).group_by(FireObservation.source_code)
        ).all()
    }

    last_runs: dict[str, IngestionRun] = {}
    for recent in session.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(200)
    ).all():
        code = recent.source.source_code if recent.source else None
        if code and code not in last_runs:
            last_runs[code] = recent

    payload: list[SourceHealth] = []
    for source in FIRMS_SOURCES:
        latest_run = last_runs.get(source.code)
        payload.append(
            SourceHealth(
                code=source.code,
                sensor=source.sensor,
                satellite=source.satellite,
                processing_level=source.processing_level,
                registered=source.code in registered,
                observations=counts.get(source.code, 0),
                last_run_status=latest_run.status if latest_run else None,
                last_run_at=(
                    (latest_run.completed_at or latest_run.started_at) if latest_run else None
                ),
                last_error=latest_run.error_message if latest_run else None,
            )
        )
    return payload


@router.post("/run", response_model=IngestResponse, summary="Run an ingestion window")
async def run_ingestion(
    request: IngestionRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> IngestResponse:
    window_days = (request.end_date - request.start_date).days + 1
    if window_days < 1:
        raise AppError(
            "unprocessable",
            "end_date must not be before start_date.",
            details={"start_date": str(request.start_date), "end_date": str(request.end_date)},
        )
    if window_days > 5:
        raise AppError(
            "unprocessable",
            "Request at most five days per call; use a backfill script for longer ranges.",
            details={"window_days": window_days, "max_days": 5},
        )

    if get_source(request.source_code) is None:
        raise AppError(
            "bad_request",
            f"Unknown source {request.source_code!r}.",
            details={"supported": [source.code for source in FIRMS_SOURCES]},
        )
    if not settings.firms_configured:
        raise AppError(
            "unavailable",
            "FIRMS_MAP_KEY is not configured, so NASA observations cannot be retrieved.",
            details={
                "hint": "Set FIRMS_MAP_KEY in the backend environment, then restart the API.",
                "fixture": "scripts/ingest_fixture.py loads labelled synthetic data for demos.",
            },
        )

    tile = WORLD
    if request.bbox:
        area = BBox.parse(request.bbox)
        tile = Tile(
            key=f"bbox_{area.west:g}_{area.south:g}_{area.east:g}_{area.north:g}",
            west=area.west,
            south=area.south,
            east=area.east,
            north=area.north,
        )
    elif request.tile and request.tile != "world":
        candidate = next((item for item in global_tiles() if item.key == request.tile), None)
        if candidate is None:
            raise AppError("bad_request", f"Unknown tile {request.tile!r}.")
        tile = candidate

    result = await run_in_threadpool(
        ingest_range,
        request.source_code,
        start_date=request.start_date,
        end_date=request.end_date,
        tile=tile,
    )

    harmonization_result = None
    events_result = None
    if request.run_harmonization and result.records_inserted:
        harmonization_result = await run_in_threadpool(
            harmonization_service.run_harmonization, is_synthetic=False
        )
        if request.run_events:
            events_result = await run_in_threadpool(
                events_service.run_event_clustering, is_synthetic=False
            )

    return IngestResponse(
        run_id=result.run_id,
        source_code=result.source_code,
        status=result.status,
        records_received=result.records_received,
        records_inserted=result.records_inserted,
        records_rejected=result.records_rejected,
        partitions_completed=result.partitions_completed,
        partitions_skipped=result.partitions_skipped,
        rejections=result.rejections,
        errors=result.errors,
        is_synthetic=result.is_synthetic,
        harmonization=harmonization_result,
        events=events_result,
    )


@router.post(
    "/run-all",
    response_model=IngestAllResponse,
    summary="Run the same window for every registered source",
)
async def run_all_sources(
    request: IngestAllRequest,
    settings: Settings = Depends(get_settings),
) -> IngestAllResponse:
    """
    One request, every product. Sources run sequentially so the database is not
    hammered, and a failing source does not abort the others: its error is
    returned in its own result entry.
    """
    window_days = (request.end_date - request.start_date).days + 1
    if window_days < 1:
        raise AppError(
            "unprocessable",
            "end_date must not be before start_date.",
            details={"start_date": str(request.start_date), "end_date": str(request.end_date)},
        )
    if window_days > 5:
        raise AppError(
            "unprocessable",
            "Request at most five days per call; use a backfill script for longer ranges.",
            details={"window_days": window_days, "max_days": 5},
        )
    if not settings.firms_configured:
        raise AppError(
            "unavailable",
            "FIRMS_MAP_KEY is not configured, so NASA observations cannot be retrieved.",
            details={
                "hint": "Set FIRMS_MAP_KEY in the backend environment, then restart the API.",
                "fixture": "scripts/ingest_fixture.py loads labelled synthetic data for demos.",
            },
        )

    codes = request.source_codes or [source.code for source in FIRMS_SOURCES]
    unknown = [code for code in codes if get_source(code) is None]
    if unknown:
        raise AppError(
            "bad_request",
            "Unknown source code(s) requested.",
            details={"unknown": unknown, "supported": [source.code for source in FIRMS_SOURCES]},
        )

    tile = WORLD
    if request.bbox:
        area = BBox.parse(request.bbox)
        tile = Tile(
            key=f"bbox_{area.west:g}_{area.south:g}_{area.east:g}_{area.north:g}",
            west=area.west,
            south=area.south,
            east=area.east,
            north=area.north,
        )
    elif request.tile and request.tile != "world":
        candidate = next((item for item in global_tiles() if item.key == request.tile), None)
        if candidate is None:
            raise AppError("bad_request", f"Unknown tile {request.tile!r}.")
        tile = candidate

    results = []
    inserted_total = 0
    received_total = 0
    rejected_total = 0
    succeeded = 0

    for code in codes:
        try:
            result = await run_in_threadpool(
                ingest_range,
                code,
                start_date=request.start_date,
                end_date=request.end_date,
                tile=tile,
            )
        except Exception as error:  # noqa: BLE001 - one source must not abort the rest
            results.append(
                IngestResponse(
                    run_id=None,
                    source_code=code,
                    status="failed",
                    records_received=0,
                    records_inserted=0,
                    records_rejected=0,
                    partitions_completed=0,
                    partitions_skipped=0,
                    errors=[str(error)],
                )
            )
            continue

        if result.status == "failed":
            results.append(
                IngestResponse(
                    run_id=result.run_id,
                    source_code=result.source_code,
                    status=result.status,
                    records_received=result.records_received,
                    records_inserted=result.records_inserted,
                    records_rejected=result.records_rejected,
                    partitions_completed=result.partitions_completed,
                    partitions_skipped=result.partitions_skipped,
                    rejections=result.rejections,
                    errors=result.errors,
                    is_synthetic=result.is_synthetic,
                )
            )
            continue

        succeeded += 1
        inserted_total += result.records_inserted
        received_total += result.records_received
        rejected_total += result.records_rejected
        results.append(
            IngestResponse(
                run_id=result.run_id,
                source_code=result.source_code,
                status=result.status,
                records_received=result.records_received,
                records_inserted=result.records_inserted,
                records_rejected=result.records_rejected,
                partitions_completed=result.partitions_completed,
                partitions_skipped=result.partitions_skipped,
                rejections=result.rejections,
                errors=result.errors,
                is_synthetic=result.is_synthetic,
            )
        )

    harmonization_result = None
    events_result = None
    if inserted_total and request.run_harmonization:
        harmonization_result = await run_in_threadpool(
            harmonization_service.run_harmonization, is_synthetic=False
        )
        if request.run_events:
            events_result = await run_in_threadpool(
                events_service.run_event_clustering, is_synthetic=False
            )

    return IngestAllResponse(
        start_date=request.start_date,
        end_date=request.end_date,
        sources_requested=len(codes),
        sources_succeeded=succeeded,
        sources_failed=len(codes) - succeeded,
        records_received=received_total,
        records_inserted=inserted_total,
        records_rejected=rejected_total,
        results=results,
        harmonization=harmonization_result,
        events=events_result,
    )


@router.post("/availability", summary="Check which dates a source actually observed")
async def check_availability(
    request: AvailabilityRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.firms_configured:
        raise AppError(
            "unavailable",
            "FIRMS_MAP_KEY is not configured, so availability cannot be verified.",
            details={"hint": "Set FIRMS_MAP_KEY in the backend environment."},
        )
    counts = await run_in_threadpool(
        sync_availability,
        request.source_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {
        "source_code": request.source_code,
        "start_date": request.start_date,
        "end_date": request.end_date,
        **counts,
        "checked_at": datetime.now(UTC),
        "note": (
            "Dates inside the provider coverage window are observed days, even when they "
            "contain zero detections. Dates outside it are recorded as before/after coverage."
        ),
    }
