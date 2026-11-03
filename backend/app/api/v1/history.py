"""Start, inspect and cancel long historical runs.

These endpoints exist because a multi-year backfill takes hours. The request is
persisted as a ``history_jobs`` row and executed after the response is sent; the
client polls the job. Progress is written between windows (and between
harmonized days), and cancel is a flag the runner checks at the same boundaries,
so cancelling never loses completed work.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import HistoryJob
from app.db.session import get_session
from app.schemas.history import (
    HistoryDatasetOut,
    HistoryJobCreate,
    HistoryJobOut,
    HistoryPlanOut,
    HistoryPlanRequest,
    HistoryRegionOut,
)
from app.services import history_runner
from app.services.firms.client import FirmsAuthError

router = APIRouter(prefix="/history", tags=["history"])


def _require_firms(settings: Settings) -> None:
    if not settings.firms_configured:
        raise AppError(
            "unavailable",
            "FIRMS_MAP_KEY is not configured, so history cannot be planned or run.",
            details={
                "hint": "Set FIRMS_MAP_KEY in the backend environment, then restart the API.",
                "fixture": "scripts/ingest_fixture.py loads labelled synthetic data.",
            },
        )


def _request(payload: HistoryPlanRequest) -> history_runner.HistoryRequest:
    try:
        return history_runner.HistoryRequest(
            datasets=tuple(payload.datasets),
            start=payload.start_date,
            end=payload.end_date,
            region=payload.region,
            bbox=payload.bbox,
            harmonize=payload.harmonize,
            refresh_every=payload.refresh_every,
            resume=payload.resume,
        )
    except ValueError as error:
        raise AppError("unprocessable", str(error)) from error


def _job_out(job: HistoryJob) -> HistoryJobOut:
    return HistoryJobOut(**history_runner.job_as_dict(job))


def _run_job(job_id: uuid.UUID) -> None:
    """Background entry point; the job row records any failure."""
    with contextlib.suppress(Exception):
        history_runner.execute_history_job(job_id)


@router.get("/datasets", response_model=list[HistoryDatasetOut], summary="Datasets")
def datasets() -> list[HistoryDatasetOut]:
    return [HistoryDatasetOut(**item) for item in history_runner.dataset_catalogue()]


@router.get("/regions", response_model=list[HistoryRegionOut], summary="Backfill regions")
def regions() -> list[HistoryRegionOut]:
    return [HistoryRegionOut(**item) for item in history_runner.region_catalogue()]


@router.post(
    "/plan",
    response_model=HistoryPlanOut,
    summary="Preview the windows a request would fetch",
)
def plan(
    payload: HistoryPlanRequest,
    settings: Settings = Depends(get_settings),
) -> HistoryPlanOut:
    _require_firms(settings)
    request = _request(payload)
    try:
        planned = history_runner.plan_history(request)
    except FirmsAuthError as error:
        raise AppError("unavailable", str(error)) from error
    return HistoryPlanOut(**planned.as_dict())


@router.post(
    "/jobs",
    response_model=HistoryJobOut,
    status_code=202,
    summary="Start a historical run",
)
def create_job(
    payload: HistoryJobCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HistoryJobOut:
    _require_firms(settings)
    request = _request(payload)

    candidates = session.scalars(
        select(HistoryJob).where(HistoryJob.status.in_(("queued", "running")))
    ).all()
    # A job whose process died leaves a running row behind; it is resumable, not
    # a reason to block every new request forever.
    active = [
        job for job in candidates if job.status == "queued" or not history_runner.job_is_stale(job)
    ]
    if active:
        raise AppError(
            "conflict",
            "Another history job is queued or running; wait for it or cancel it first.",
            details={"active_jobs": len(active)},
        )

    job_id = history_runner.create_job(request)
    job = session.get(HistoryJob, job_id)
    if job is None:  # pragma: no cover - the row was just written
        raise AppError("internal", "The history job could not be created.")
    background.add_task(_run_job, job.id)
    return _job_out(job)


@router.get("/jobs", response_model=list[HistoryJobOut], summary="Recent history jobs")
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[HistoryJobOut]:
    rows = session.scalars(
        select(HistoryJob).order_by(HistoryJob.created_at.desc()).limit(limit)
    ).all()
    return [_job_out(row) for row in rows]


def _get_job(job_id: str, session: Session) -> HistoryJob:
    try:
        uid = uuid.UUID(job_id)
    except ValueError as error:
        raise AppError("bad_request", "job_id must be a UUID.") from error
    job = session.get(HistoryJob, uid)
    if job is None:
        raise AppError("not_found", f"History job {job_id} does not exist.")
    return job


@router.get("/jobs/{job_id}", response_model=HistoryJobOut, summary="History job status")
def get_job(job_id: str, session: Session = Depends(get_session)) -> HistoryJobOut:
    return _job_out(_get_job(job_id, session))


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=HistoryJobOut,
    summary="Ask a running job to stop between windows",
)
def cancel_job(job_id: str, session: Session = Depends(get_session)) -> HistoryJobOut:
    job = _get_job(job_id, session)
    if job.status not in ("queued", "running"):
        raise AppError(
            "conflict",
            f"Job is already {job.status}.",
            details={"status": job.status},
        )
    job.cancel_requested = True
    session.commit()
    session.refresh(job)
    return _job_out(job)


@router.post(
    "/jobs/{job_id}/resume",
    response_model=HistoryJobOut,
    status_code=202,
    summary="Resume a failed or cancelled job (completed work is skipped)",
)
def resume_job(
    job_id: str,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HistoryJobOut:
    _require_firms(settings)
    job = _get_job(job_id, session)
    if job.status == "queued" or (
        job.status == "running" and not history_runner.job_is_stale(job)
    ):
        raise AppError(
            "conflict",
            f"Job is already {job.status}.",
            details={"status": job.status},
        )
    job.status = "queued"
    job.cancel_requested = False
    job.error_message = None
    job.completed_at = None
    session.commit()
    session.refresh(job)
    background.add_task(_run_job, job.id)
    return _job_out(job)


@router.get(
    "/jobs/{job_id}/summary",
    summary="Final summary of a finished job",
)
def job_summary(
    job_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    job = _get_job(job_id, session)
    return {
        "id": str(job.id),
        "status": job.status,
        "summary": job.summary or {},
        "progress": job.progress or {},
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


__all__ = ["router"]
