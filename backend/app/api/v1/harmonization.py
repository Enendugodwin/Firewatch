"""MODIS/VIIRS harmonization: summary, inspectable matches, events, run control."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError
from app.db.models import (
    AlgorithmRun,
    FireEvent,
    FireObservation,
    ObservationMatch,
)
from app.db.session import get_session
from app.schemas.observations import (
    AlgorithmRunOut,
    EventOut,
    HarmonizationSummary,
    MatchOut,
    MatchPage,
    MatchRunRequest,
    MatchRunResponse,
    ObservationBrief,
)
from app.services import events as events_service
from app.services import harmonization as harmonization_service
from app.services.observation_queries import (
    BBox,
    event_stats,
    match_counts,
    sensor_counts,
)

router = APIRouter(prefix="/harmonization", tags=["harmonization"])


def _brief(observation: FireObservation) -> ObservationBrief:
    return ObservationBrief(
        id=str(observation.id),
        source_code=observation.source_code,
        sensor=observation.sensor,
        satellite=observation.satellite,
        latitude=observation.latitude,
        longitude=observation.longitude,
        acquired_at=observation.acquired_at,
        confidence_category=observation.confidence_category,
        frp_mw=observation.frp_mw,
    )


def _match_out(row: ObservationMatch) -> MatchOut:
    return MatchOut(
        id=str(row.id),
        observation_a=_brief(row.observation_a),
        observation_b=_brief(row.observation_b),
        temporal_delta_seconds=row.temporal_delta_seconds,
        spatial_distance_m=row.spatial_distance_m,
        footprint_overlap=row.footprint_overlap,
        association_score=row.association_score,
        match_status=row.match_status,
        components=row.components or {},
        algorithm_version=row.algorithm_version,
        created_at=row.created_at,
    )


@router.get("/summary", response_model=HarmonizationSummary, summary="Harmonization statistics")
def summary(session: Session = Depends(get_session)) -> HarmonizationSummary:
    sensors = sensor_counts(session)
    counts = match_counts(session)
    total_events, multi_sensor_events = event_stats(session)
    synthetic = (
        session.scalar(
            select(func.count())
            .select_from(FireObservation)
            .where(FireObservation.is_synthetic.is_(True))
        )
        or 0
    )
    last_run = session.scalars(
        select(AlgorithmRun)
        .where(AlgorithmRun.kind == "harmonization")
        .order_by(AlgorithmRun.started_at.desc())
        .limit(1)
    ).first()

    return HarmonizationSummary(
        observations=sum(sensors.values()),
        modis_observations=sensors.get("MODIS", 0),
        viirs_observations=sensors.get("VIIRS", 0),
        synthetic_observations=int(synthetic),
        matches_total=counts.get("total", 0),
        matches_probable=counts.get("probable", 0),
        matches_possible=counts.get("possible", 0),
        matches_rejected=counts.get("rejected", 0),
        events=total_events,
        multi_sensor_events=multi_sensor_events,
        last_run_at=last_run.completed_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
        parameters=(last_run.parameters if last_run else {}),
        last_run_scope=(last_run.parameters or {}).get("scope") if last_run else None,
        algorithm_version=harmonization_service.ALGORITHM_VERSION,
    )


@router.get("/matches", response_model=MatchPage, summary="Probable cross-sensor matches")
def list_matches(
    status: str | None = Query(None, pattern="^(probable|possible|rejected)$"),
    min_score: float | None = Query(None, ge=0, le=1),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> MatchPage:
    stmt = select(ObservationMatch)
    if status:
        stmt = stmt.where(ObservationMatch.match_status == status)
    if min_score is not None:
        stmt = stmt.where(ObservationMatch.association_score >= min_score)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(ObservationMatch.association_score.desc()).limit(limit).offset(offset)
    ).all()
    return MatchPage(
        items=[_match_out(row) for row in rows], total=int(total), limit=limit, offset=offset
    )


@router.get("/matches/{match_id}", response_model=MatchOut, summary="Match evidence")
def get_match(match_id: str, session: Session = Depends(get_session)) -> MatchOut:
    from sqlalchemy.exc import StatementError

    try:
        row = session.get(ObservationMatch, match_id)
    except (ValueError, StatementError) as exc:
        raise AppError("not_found", "No match with that identifier.") from exc
    if row is None:
        raise AppError("not_found", "No match with that identifier.")
    return _match_out(row)


@router.get("/events", response_model=list[EventOut], summary="Estimated fire events")
def list_events(
    limit: int = Query(50, ge=1, le=500),
    min_observations: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> list[EventOut]:
    rows = session.scalars(
        select(FireEvent)
        .where(FireEvent.observation_count >= min_observations)
        .order_by(FireEvent.observation_count.desc(), FireEvent.first_detected_at.desc())
        .limit(limit)
    ).all()
    return [
        EventOut(
            id=str(row.id),
            first_detected_at=row.first_detected_at,
            last_detected_at=row.last_detected_at,
            centroid_latitude=row.centroid_latitude,
            centroid_longitude=row.centroid_longitude,
            min_latitude=row.min_latitude,
            max_latitude=row.max_latitude,
            min_longitude=row.min_longitude,
            max_longitude=row.max_longitude,
            observation_count=row.observation_count,
            sensor_count=row.sensor_count,
            maximum_frp_mw=row.maximum_frp_mw,
            aggregate_frp_mw=row.aggregate_frp_mw,
            clustering_method=row.clustering_method,
            clustering_parameters=row.clustering_parameters or {},
            methodology_version=row.methodology_version,
        )
        for row in rows
    ]


@router.post("/run", response_model=MatchRunResponse, summary="Launch a harmonization pass")
async def run_matching(
    request: MatchRunRequest | None = None,
    session: Session = Depends(get_session),
) -> MatchRunResponse:
    request = request or MatchRunRequest()
    if not (request.probable_threshold > request.possible_threshold >= request.store_threshold):
        raise AppError(
            "unprocessable",
            "Thresholds must satisfy probable > possible >= store.",
            details={
                "probable": request.probable_threshold,
                "possible": request.possible_threshold,
                "store": request.store_threshold,
            },
        )
    params = harmonization_service.MatchParameters(
        time_window_minutes=request.time_window_minutes,
        max_distance_m=request.max_distance_m,
        probable_threshold=request.probable_threshold,
        possible_threshold=request.possible_threshold,
        store_threshold=request.store_threshold,
    )

    if request.synthetic is None:
        has_real = bool(
            session.scalar(
                select(func.count())
                .select_from(FireObservation)
                .where(FireObservation.is_synthetic.is_(False))
            )
        )
        has_synthetic = bool(
            session.scalar(
                select(func.count())
                .select_from(FireObservation)
                .where(FireObservation.is_synthetic.is_(True))
            )
        )
        scopes = [scope for scope, present in ((False, has_real), (True, has_synthetic)) if present]
    else:
        scopes = [request.synthetic]

    if not scopes:
        raise AppError(
            "conflict",
            "No observations to harmonize. Ingest data first.",
            details={"hint": "POST /api/v1/admin/ingestion/run or load the labelled fixture."},
        )

    bbox = BBox.parse(request.bbox) if request.bbox else None
    if request.start_date and request.end_date and request.end_date < request.start_date:
        raise AppError(
            "unprocessable",
            "end_date must not be before start_date.",
            details={"start_date": str(request.start_date), "end_date": str(request.end_date)},
        )

    results = []
    for scope in scopes:
        results.append(
            await run_in_threadpool(
                harmonization_service.run_harmonization,
                params=params,
                is_synthetic=scope,
                bbox=bbox,
                start_date=request.start_date,
                end_date=request.end_date,
            )
        )

    event_results = []
    if request.run_events:
        for scope in scopes:
            event_results.append(
                await run_in_threadpool(
                    events_service.run_event_clustering,
                    is_synthetic=scope,
                    bbox=bbox,
                    start_date=request.start_date,
                    end_date=request.end_date,
                )
            )

    return MatchRunResponse(scopes=results, events=event_results)


@router.get("/jobs", response_model=list[AlgorithmRunOut], summary="Recent algorithm runs")
def list_jobs(
    kind: str | None = Query(None, pattern="^(harmonization|event_clustering)$"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[AlgorithmRunOut]:
    stmt = select(AlgorithmRun)
    if kind:
        stmt = stmt.where(AlgorithmRun.kind == kind)
    rows = session.scalars(stmt.order_by(AlgorithmRun.started_at.desc()).limit(limit)).all()
    return [
        AlgorithmRunOut(
            id=str(row.id),
            kind=row.kind,
            status=row.status,
            started_at=row.started_at,
            completed_at=row.completed_at,
            parameters=row.parameters or {},
            stats=row.stats or {},
            algorithm_version=row.algorithm_version,
            is_synthetic=row.is_synthetic,
            error_message=row.error_message,
        )
        for row in rows
    ]


@router.get("/jobs/{job_id}", response_model=AlgorithmRunOut, summary="Job status")
def get_job(job_id: str, session: Session = Depends(get_session)) -> AlgorithmRunOut:
    from sqlalchemy.exc import StatementError

    try:
        row = session.get(AlgorithmRun, job_id)
    except (ValueError, StatementError) as exc:
        raise AppError("not_found", "No job with that identifier.") from exc
    if row is None:
        raise AppError("not_found", "No job with that identifier.")
    return AlgorithmRunOut(
        id=str(row.id),
        kind=row.kind,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        parameters=row.parameters or {},
        stats=row.stats or {},
        algorithm_version=row.algorithm_version,
        is_synthetic=row.is_synthetic,
        error_message=row.error_message,
    )


@router.get("/status", summary="Harmonization engine status")
def engine_status() -> dict[str, object]:
    return {
        "algorithm_version": harmonization_service.ALGORITHM_VERSION,
        "event_methodology_version": events_service.METHODOLOGY_VERSION,
        "defaults": harmonization_service.MatchParameters().__dict__,
        "event_defaults": events_service.ClusterParameters().__dict__,
        "checked_at": datetime.now(UTC),
        "note": (
            "Scores are association scores, not probabilities that two detections are the "
            "same physical fire. Estimated events are not confirmed wildfires."
        ),
    }
