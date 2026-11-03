"""Run large detections datasets over arbitrary date ranges.

The scripts are thin wrappers around this module. A caller chooses a **dataset**
(a named bundle of FIRMS products), a **date range** and optionally a **region**;
the runner plans five-day windows, clamps them to the product coverage, ingests
each window as a resumable partition, optionally harmonizes the same span, and
refreshes the rollups.

Two entry points:

* :func:`run_history` - synchronous, no database job row; for scripts and tests.
* :func:`create_job` / :func:`execute_history_job` - a persisted
  ``history_jobs`` row with progress and cancellation, for the API.

Nothing here downloads a window outside reported coverage, and a day that was
never processed is never labelled ``empty`` (see ``docs/historical_backfill.md``).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from app.core.logging import get_logger
from app.db.models import HistoryJob
from app.db.session import session_scope
from app.services.firms.client import (
    AvailabilityWindow,
    FirmsAuthError,
    FirmsClient,
    FirmsError,
)
from app.services.firms.tiles import WORLD, Tile
from app.services.harmonization import run_harmonization_range
from app.services.historical_backfill import REGIONS, plan_windows, resolve_tile
from app.services.ingestion import build_client, ingest_range
from app.services.observation_queries import BBox
from app.services.rollups import refresh_rollup
from app.services.sources import get_source

logger = get_logger(__name__)

#: Five days is the FIRMS area-endpoint maximum.
WINDOW_DAYS = 5


@dataclass(frozen=True)
class Dataset:
    """A named bundle of products a caller can ask for."""

    key: str
    label: str
    sources: tuple[str, ...]
    history: bool


DATASETS: dict[str, Dataset] = {
    "modis_history": Dataset(
        key="modis_history",
        label="MODIS standard processing (long record)",
        sources=("MODIS_SP",),
        history=True,
    ),
    "viirs_snpp_history": Dataset(
        key="viirs_snpp_history",
        label="VIIRS standard processing, Suomi-NPP only (the long VIIRS record)",
        sources=("VIIRS_SNPP_SP",),
        history=True,
    ),
    "viirs_history": Dataset(
        key="viirs_history",
        label="VIIRS standard processing (SNPP, NOAA-20, NOAA-21)",
        sources=("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"),
        history=True,
    ),
    "all_history": Dataset(
        key="all_history",
        label="Every standard-processing product",
        sources=("MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP"),
        history=True,
    ),
    "nrt": Dataset(
        key="nrt",
        label="Near-real-time products (rolling window)",
        sources=("MODIS_NRT", "VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"),
        history=False,
    ),
    "all_products": Dataset(
        key="all_products",
        label="Every supported product",
        sources=(
            "MODIS_SP",
            "VIIRS_SNPP_SP",
            "VIIRS_NOAA20_SP",
            "VIIRS_NOAA21_SP",
            "MODIS_NRT",
            "VIIRS_SNPP_NRT",
            "VIIRS_NOAA20_NRT",
            "VIIRS_NOAA21_NRT",
        ),
        history=False,
    ),
}


def dataset_catalogue() -> list[dict[str, Any]]:
    return [
        {
            "key": dataset.key,
            "label": dataset.label,
            "sources": list(dataset.sources),
            "history": dataset.history,
        }
        for dataset in DATASETS.values()
    ]


def region_catalogue() -> list[dict[str, Any]]:
    return [
        {
            "key": region.key,
            "name": region.name,
            "bbox": region.bbox,
            "note": region.note,
        }
        for region in REGIONS.values()
    ]


@dataclass(frozen=True)
class HistoryRequest:
    """What to run. Validation happens at construction time."""

    datasets: tuple[str, ...]
    start: date
    end: date
    region: str | None = None
    bbox: str | None = None
    harmonize: bool = False
    refresh_every: int = 100
    resume: bool = True

    def __post_init__(self) -> None:
        if not self.datasets:
            raise ValueError("Choose at least one dataset.")
        unknown = [key for key in self.datasets if key not in DATASETS]
        if unknown:
            raise ValueError(
                f"Unknown dataset(s): {', '.join(unknown)}. "
                f"Choose from {', '.join(sorted(DATASETS))}."
            )
        if self.start > self.end:
            raise ValueError("start must be on or before end.")
        if self.region and self.bbox:
            raise ValueError("Choose either a region or a bbox, not both.")
        if self.refresh_every < 0:
            raise ValueError("refresh_every must be zero or positive.")

    @property
    def source_codes(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for key in self.datasets:
            for code in DATASETS[key].sources:
                seen.setdefault(code, None)
        return tuple(seen)

    def as_dict(self) -> dict[str, Any]:
        return {
            "datasets": list(self.datasets),
            "start_date": self.start.isoformat(),
            "end_date": self.end.isoformat(),
            "region": self.region,
            "bbox": self.bbox,
            "harmonize": self.harmonize,
            "refresh_every": self.refresh_every,
            "resume": self.resume,
        }


@dataclass
class SourcePlan:
    source_code: str
    requested_start: date
    requested_end: date
    coverage_start: date | None
    coverage_end: date | None
    coverage_known: bool
    windows: list[tuple[date, date]] = field(default_factory=list)
    note: str | None = None

    @property
    def days(self) -> int:
        return sum((end - start).days + 1 for start, end in self.windows)


@dataclass
class HistoryPlan:
    request: HistoryRequest
    tile: Tile
    bbox: BBox | None
    sources: list[SourcePlan]
    warnings: list[str] = field(default_factory=list)

    @property
    def total_requests(self) -> int:
        return sum(len(source.windows) for source in self.sources)

    @property
    def total_days(self) -> int:
        return sum(source.days for source in self.sources)

    @property
    def both_sensors(self) -> bool:
        sensors = {get_source(source.source_code).sensor for source in self.sources}  # type: ignore[union-attr]
        return {"MODIS", "VIIRS"} <= sensors

    @property
    def span(self) -> tuple[date, date] | None:
        starts = [source.windows[0][0] for source in self.sources if source.windows]
        ends = [source.windows[-1][1] for source in self.sources if source.windows]
        if not starts or not ends:
            return None
        return min(starts), max(ends)

    def as_dict(self) -> dict[str, Any]:
        span = self.span
        return {
            "request": self.request.as_dict(),
            "tile": {"key": self.tile.key, "bbox": self.tile.bbox},
            "total_requests": self.total_requests,
            "total_days": self.total_days,
            "both_sensors": self.both_sensors,
            "harmonization_span": (
                {"start_date": span[0].isoformat(), "end_date": span[1].isoformat()}
                if span
                else None
            ),
            "sources": [
                {
                    "source_code": source.source_code,
                    "requested_start": source.requested_start.isoformat(),
                    "requested_end": source.requested_end.isoformat(),
                    "coverage_start": (
                        source.coverage_start.isoformat() if source.coverage_start else None
                    ),
                    "coverage_end": (
                        source.coverage_end.isoformat() if source.coverage_end else None
                    ),
                    "coverage_known": source.coverage_known,
                    "windows": [
                        {"start_date": start.isoformat(), "end_date": end.isoformat()}
                        for start, end in source.windows
                    ],
                    "days": source.days,
                    "note": source.note,
                }
                for source in self.sources
            ],
            "warnings": list(self.warnings),
        }


def _clamp(
    window: AvailabilityWindow,
    start: date,
    end: date,
    *,
    clamp_start: bool,
) -> tuple[date, date] | None:
    """Intersect a request with reported coverage.

    The coverage *end* is always respected: requesting past it is what used to
    record unprocessed days as ``empty``. The coverage *start* is only applied to
    standard-processing products, whose earliest date is definitive; a near-real-
    time window is rolling and its reported minimum is not a reliable floor.
    """
    if window.max_date is None:
        return (start, end)
    first = max(start, window.min_date) if clamp_start and window.min_date else start
    last = min(end, window.max_date)
    if first > last:
        return None
    return first, last


def plan_history(
    request: HistoryRequest, *, client: FirmsClient | None = None
) -> HistoryPlan:
    """Resolve datasets, read coverage and split into bounded windows.

    Coverage lookup failure is not fatal: the plan says ``coverage_known: false``
    and leaves the windows unclamped, so a caller can see the request that would
    be made. The ingestion layer still refuses to mark uncovered SP days empty.
    """
    client = client or build_client()
    if not getattr(client, "configured", True):
        raise FirmsAuthError(
            "FIRMS_MAP_KEY is not configured; history cannot be planned or run."
        )

    if request.region or request.bbox:
        tile = resolve_tile(region=request.region, bbox=request.bbox, name="custom")
        bbox = BBox(west=tile.west, south=tile.south, east=tile.east, north=tile.north)
    else:
        tile = WORLD
        bbox = None

    sources: list[SourcePlan] = []
    warnings: list[str] = []

    for code in request.source_codes:
        registry = get_source(code)
        if registry is None:
            raise ValueError(f"Source {code!r} is not registered.")

        try:
            coverage = client.fetch_availability(code)
            known = coverage.min_date is not None and coverage.max_date is not None
        except FirmsError as error:
            coverage = AvailabilityWindow(source_code=code, min_date=None, max_date=None)
            known = False
            warnings.append(
                f"{code}: coverage could not be read ({type(error).__name__}); "
                "the plan is not clamped and uncovered days may return no rows."
            )

        clamped = _clamp(
            coverage,
            request.start,
            request.end,
            clamp_start=registry.is_standard_processing,
        )
        source_plan = SourcePlan(
            source_code=code,
            requested_start=request.start,
            requested_end=request.end,
            coverage_start=coverage.min_date,
            coverage_end=coverage.max_date,
            coverage_known=known,
        )
        if clamped is None:
            source_plan.note = (
                f"The requested range is outside the coverage "
                f"({coverage.min_date} .. {coverage.max_date}); nothing to fetch."
            )
        else:
            source_plan.windows = plan_windows(clamped[0], clamped[1], WINDOW_DAYS)
            if clamped != (request.start, request.end):
                source_plan.note = (
                    f"Clamped to reported coverage: {clamped[0]} .. {clamped[1]}."
                )
        sources.append(source_plan)

    if request.harmonize and not any(source.windows for source in sources):
        warnings.append("No windows to ingest, so harmonization was not planned.")

    plan = HistoryPlan(request=request, tile=tile, bbox=bbox, sources=sources, warnings=warnings)
    if request.harmonize and not plan.both_sensors:
        warnings.append(
            "Harmonization needs both sensor families; the selected datasets only "
            "contain one, so the pass would find no pairs."
        )
    return plan


def _emit(progress: Callable[[dict[str, Any]], None] | None, state: dict[str, Any]) -> None:
    if progress is not None:
        progress(state)


def _refresh(since: date | None) -> bool:
    with session_scope() as session:
        return refresh_rollup(session, since=since)


def run_history(
    request: HistoryRequest,
    *,
    client: FirmsClient | None = None,
    plan: HistoryPlan | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Ingest (and optionally harmonize) a date range, resumably.

    Synchronous and side-effect-only on the database. A failing window is
    recorded and the run continues, except for an authentication failure, which
    would simply fail every remaining window.
    """
    started = time.perf_counter()
    client = client or build_client()
    _emit(progress, {"phase": "planning", "done": 0, "total": 0})

    plan = plan or plan_history(request, client=client)
    total_windows = plan.total_requests
    span = plan.span

    summary: dict[str, Any] = {
        "request": request.as_dict(),
        "plan": plan.as_dict(),
        "cancelled": False,
        "total_requests": total_windows,
        "requests_completed": 0,
        "records_received": 0,
        "records_inserted": 0,
        "records_rejected": 0,
        "partitions_completed": 0,
        "partitions_skipped": 0,
        "windows_failed": 0,
        "failures": [],
        "per_source": {code: 0 for code in request.source_codes},
        "harmonization": None,
        "rollup_refreshed": False,
    }

    inserted_since_refresh = 0
    done = 0
    abort = False

    for source in plan.sources:
        if abort:
            break
        for window_start, window_end in source.windows:
            if should_stop is not None and should_stop():
                summary["cancelled"] = True
                abort = True
                break

            try:
                result = ingest_range(
                    source.source_code,
                    start_date=window_start,
                    end_date=window_end,
                    tile=plan.tile,
                    client=client,
                    resume=request.resume,
                )
            except FirmsAuthError:
                raise
            except Exception as error:  # noqa: BLE001 - one window must not abort the run
                summary["windows_failed"] += 1
                if len(summary["failures"]) < 50:
                    summary["failures"].append(
                        {
                            "source_code": source.source_code,
                            "start_date": window_start.isoformat(),
                            "end_date": window_end.isoformat(),
                            "error": str(error)[:300],
                        }
                    )
                logger.warning(
                    "history_window_failed",
                    source=source.source_code,
                    start=window_start.isoformat(),
                    error=str(error)[:200],
                )
                done += 1
                continue

            done += 1
            summary["requests_completed"] += 1
            summary["records_received"] += result.records_received
            summary["records_inserted"] += result.records_inserted
            summary["records_rejected"] += result.records_rejected
            summary["partitions_completed"] += result.partitions_completed
            summary["partitions_skipped"] += result.partitions_skipped
            summary["per_source"][source.source_code] = (
                summary["per_source"].get(source.source_code, 0) + result.records_inserted
            )
            inserted_since_refresh += result.records_inserted

            elapsed = time.perf_counter() - started
            rate = done / elapsed if elapsed else 0.0
            _emit(
                progress,
                {
                    "phase": "ingesting",
                    "source_code": source.source_code,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "done": done,
                    "total": total_windows,
                    "inserted": summary["records_inserted"],
                    "elapsed_seconds": round(elapsed, 1),
                    "eta_seconds": round((total_windows - done) / rate, 1) if rate else None,
                },
            )

            if (
                request.refresh_every
                and inserted_since_refresh
                and done % request.refresh_every == 0
            ):
                summary["rollup_refreshed"] = _refresh(span[0] if span else None) or (
                    summary["rollup_refreshed"]
                )
                inserted_since_refresh = 0

    if summary["records_inserted"]:
        refreshed = _refresh(span[0] if span else None)
        summary["rollup_refreshed"] = summary["rollup_refreshed"] or refreshed

    if (
        request.harmonize
        and not summary["cancelled"]
        and plan.both_sensors
        and span is not None
    ):
        def harmonize_progress(state: dict[str, Any]) -> None:
            _emit(
                progress,
                {
                    "phase": "harmonizing",
                    "day": state.get("day"),
                    "processed": state.get("processed"),
                    "days": state.get("days"),
                    "pairs": state.get("pairs"),
                    "observations": state.get("observations"),
                    "inserted": summary["records_inserted"],
                },
            )

        summary["harmonization"] = run_harmonization_range(
            start=span[0],
            end=span[1],
            bbox=plan.bbox,
            is_synthetic=False,
            force=False,
            progress=harmonize_progress,
            should_stop=should_stop,
        )
        if summary["harmonization"].get("cancelled"):
            summary["cancelled"] = True

    summary["duration_seconds"] = round(time.perf_counter() - started, 1)
    _emit(
        progress,
        {
            "phase": "done",
            "done": summary["requests_completed"],
            "total": total_windows,
            "inserted": summary["records_inserted"],
            "cancelled": summary["cancelled"],
            "elapsed_seconds": summary["duration_seconds"],
        },
    )
    logger.info(
        "history_run_complete",
        datasets=list(request.datasets),
        inserted=summary["records_inserted"],
        requests=summary["requests_completed"],
        cancelled=summary["cancelled"],
        duration_seconds=summary["duration_seconds"],
    )
    return summary


# ---------------------------------------------------------------------------
# Durable jobs
# ---------------------------------------------------------------------------


def create_job(request: HistoryRequest) -> uuid.UUID:
    """Persist a queued job and return its id."""
    with session_scope() as session:
        job = HistoryJob(
            kind="history",
            status="queued",
            datasets=list(request.datasets),
            region=request.region,
            bbox=request.bbox,
            start_date=request.start,
            end_date=request.end,
            harmonize=request.harmonize,
            progress={},
            summary={},
        )
        session.add(job)
        session.flush()
        return job.id


def request_from_job(job: HistoryJob) -> HistoryRequest:
    return HistoryRequest(
        datasets=tuple(job.datasets or ()),
        start=job.start_date,
        end=job.end_date,
        region=job.region,
        bbox=job.bbox,
        harmonize=job.harmonize,
    )


def execute_history_job(
    job_id: uuid.UUID | str,
    *,
    client: FirmsClient | None = None,
) -> dict[str, Any]:
    """Run a persisted job, writing progress and the final summary to its row.

    Safe to call again on a failed, cancelled or succeeded job: ingestion
    partitions and harmonization coverage make the rerun a resume, not a repeat.
    """
    uid = job_id if isinstance(job_id, uuid.UUID) else uuid.UUID(str(job_id))
    client = client or build_client()

    with session_scope() as session:
        job = session.get(HistoryJob, uid)
        if job is None:
            raise KeyError(f"History job {uid} does not exist.")
        if job.status == "running":
            raise RuntimeError(f"History job {uid} is already running.")
        request = request_from_job(job)
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        job.error_message = None
        job.cancel_requested = False
        job.progress = {"phase": "planning"}
        job.summary = {}

    stop_checks = 0
    cached_stop = False

    def should_stop() -> bool:
        nonlocal stop_checks, cached_stop
        # The check runs between every window and every harmonized day; hitting
        # the database on each one would be pure overhead, so it is cached for a
        # handful of calls.
        stop_checks += 1
        if stop_checks % 10 != 1 and stop_checks > 1:
            return cached_stop
        with session_scope() as session:
            row = session.get(HistoryJob, uid)
            cached_stop = bool(row.cancel_requested) if row is not None else False
        return cached_stop

    def write_progress(state: dict[str, Any]) -> None:
        with session_scope() as session:
            row = session.get(HistoryJob, uid)
            if row is not None:
                row.progress = state

    status = "succeeded"
    summary: dict[str, Any] = {}
    error_message: str | None = None
    try:
        summary = run_history(
            request,
            client=client,
            progress=write_progress,
            should_stop=should_stop,
        )
        if summary.get("cancelled"):
            status = "cancelled"
    except Exception as error:  # noqa: BLE001 - persisted, then re-raised to the caller
        status = "failed"
        error_message = str(error)[:1000]
        logger.exception("history_job_failed", job=str(uid))
    finally:
        with session_scope() as session:
            row = session.get(HistoryJob, uid)
            if row is not None:
                row.status = status
                row.summary = summary
                row.error_message = error_message
                row.completed_at = datetime.now(UTC)
                if summary:
                    row.progress = {
                        "phase": "done",
                        "done": summary.get("requests_completed", 0),
                        "total": summary.get("total_requests", 0),
                        "inserted": summary.get("records_inserted", 0),
                        "cancelled": summary.get("cancelled", False),
                        "elapsed_seconds": summary.get("duration_seconds", 0),
                    }
                else:
                    row.progress = {**(row.progress or {}), "phase": "failed"}

    if status == "failed":
        raise RuntimeError(error_message)
    return summary


def job_as_dict(job: HistoryJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "datasets": list(job.datasets or []),
        "region": job.region,
        "bbox": job.bbox,
        "start_date": job.start_date.isoformat(),
        "end_date": job.end_date.isoformat(),
        "harmonize": job.harmonize,
        "progress": job.progress or {},
        "summary": job.summary or {},
        "error_message": job.error_message,
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def iter_windows(plan: HistoryPlan) -> Iterable[tuple[str, date, date]]:
    for source in plan.sources:
        for window in source.windows:
            yield source.source_code, window[0], window[1]


__all__ = [
    "DATASETS",
    "Dataset",
    "HistoryPlan",
    "HistoryRequest",
    "SourcePlan",
    "WINDOW_DAYS",
    "create_job",
    "dataset_catalogue",
    "execute_history_job",
    "iter_windows",
    "job_as_dict",
    "plan_history",
    "region_catalogue",
    "request_from_job",
    "run_history",
]
