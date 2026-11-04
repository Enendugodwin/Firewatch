"""MODIS–VIIRS cross-sensor association.

The engine never merges records. It produces scored candidate associations
between observations from *different sensor families*, stores every component of
the score, and classifies them as probable, possible, unmatched or rejected.

    S = wt·T + ws·G + wf·F

T is temporal similarity, G geographic proximity, F footprint overlap. The score
is an association score, not the probability that two detections are the same
physical fire, and it is never used to collapse observations.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import wraps
from typing import Any

import numpy as np
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.orm import Session, aliased

from app.core.logging import get_logger
from app.db.dialect import dialect_name
from app.db.models import (
    AlgorithmRun,
    FireObservation,
    HarmonizationCoverage,
    ObservationMatch,
)
from app.db.session import session_scope
from app.services.geo import footprint_overlap, haversine_m
from app.services.observation_queries import BBox  # noqa: TC001 - runtime type hints

logger = get_logger(__name__)

ALGORITHM_VERSION = "assoc-v1"

#: One harmonization pass mutates the match table for a scope. Two passes over
#: the same scope used to collide on ``uq_observation_matches_pair`` and return
#: a 500; they are now rejected with a clear conflict instead.
HARMONIZATION_LOCK_KEY = 0x46495748
_RUN_LOCK = threading.Lock()


class HarmonizationBusy(RuntimeError):
    """Another harmonization pass owns the match table right now."""


def _serialized(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Refuse overlapping passes instead of letting them collide on matches."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _RUN_LOCK.acquire(blocking=False):
            raise HarmonizationBusy(
                "A harmonization run is already in progress. Retry when it finishes."
            )
        try:
            return fn(*args, **kwargs)
        finally:
            _RUN_LOCK.release()

    return wrapper


def _lock_transaction(session: Session) -> None:
    """PostgreSQL cross-process guard, released automatically at commit."""
    if dialect_name(session) != "postgresql":
        return
    acquired = session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": HARMONIZATION_LOCK_KEY},
    )
    if not acquired:
        raise HarmonizationBusy(
            "A harmonization run is already in progress in another process."
        )


@dataclass(frozen=True)
class MatchParameters:
    """Tunable thresholds; stored with the run so results stay reproducible."""

    time_window_minutes: int = 180
    max_distance_m: float = 2000.0
    weight_temporal: float = 0.4
    weight_spatial: float = 0.45
    weight_footprint: float = 0.15
    probable_threshold: float = 0.75
    possible_threshold: float = 0.55
    store_threshold: float = 0.35
    max_observations: int = 20_000


@dataclass
class PairScore:
    temporal_delta_seconds: int
    spatial_distance_m: float
    footprint_overlap: float | None
    components: dict[str, object]
    score: float
    status: str


def classify(score: float, params: MatchParameters) -> str:
    if score >= params.probable_threshold:
        return "probable"
    if score >= params.possible_threshold:
        return "possible"
    if score >= params.store_threshold:
        return "rejected"
    return "rejected"


def score_pair(
    *,
    delta_seconds: float,
    distance_m: float,
    scan_a: float | None,
    track_a: float | None,
    scan_b: float | None,
    track_b: float | None,
    params: MatchParameters,
) -> PairScore:
    """
    Score one candidate pair. Weights are renormalised over the components that
    are actually available, so a missing footprint never silently deflates the
    score or fabricates geometry.
    """
    window_s = params.time_window_minutes * 60.0
    # Quadratic tolerance: satellites pass minutes to hours apart, so a linear
    # penalty would suppress genuine associations simply because MODIS and VIIRS
    # overpasses are not coincident. The window is still a hard cut-off.
    if window_s:
        ratio = min(1.0, abs(delta_seconds) / window_s)
        temporal = max(0.0, 1.0 - ratio**2)
    else:
        temporal = 0.0
    spatial = max(0.0, 1.0 - distance_m / params.max_distance_m)
    overlap = footprint_overlap(distance_m, scan_a, track_a, scan_b, track_b)

    components: list[tuple[float, float]] = [
        (params.weight_temporal, temporal),
        (params.weight_spatial, spatial),
    ]
    if overlap is not None:
        components.append((params.weight_footprint, overlap))

    total_weight = sum(weight for weight, _ in components)
    score = (
        sum(weight * value for weight, value in components) / total_weight if total_weight else 0.0
    )

    return PairScore(
        temporal_delta_seconds=int(round(abs(delta_seconds))),
        spatial_distance_m=round(distance_m, 2),
        footprint_overlap=round(overlap, 4) if overlap is not None else None,
        components=_component_payload(
            temporal=temporal,
            spatial=spatial,
            overlap=overlap,
            params=params,
        ),
        score=round(score, 4),
        status=classify(score, params),
    )


def _component_payload(
    *,
    temporal: float,
    spatial: float,
    overlap: float | None,
    params: MatchParameters,
) -> dict[str, object]:
    return {
        "temporal_similarity": round(temporal, 4),
        "spatial_proximity": round(spatial, 4),
        "footprint_overlap": round(overlap, 4) if overlap is not None else None,
        "weights": {
            "temporal": params.weight_temporal,
            "spatial": params.weight_spatial,
            "footprint": params.weight_footprint if overlap is not None else 0.0,
        },
        "weight_note": "weights renormalised over available components",
    }


@dataclass
class _Obs:
    id: str
    sensor: str
    latitude: float
    longitude: float
    acquired_at: datetime
    scan_km: float | None
    track_km: float | None


def _load_observations(
    session,
    is_synthetic: bool,
    params: MatchParameters,
    *,
    bbox: BBox | None = None,
    start_date=None,
    end_date=None,
) -> list[_Obs]:
    rows, _ = _load_scope_observations(
        session,
        is_synthetic,
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        cap=params.max_observations,
    )
    return rows


def _load_scope_observations(
    session: Session,
    is_synthetic: bool,
    *,
    bbox: BBox | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    cap: int | None,
) -> tuple[list[_Obs], bool]:
    """Load a scope; ``cap=None`` means no truncation.

    Returns ``(observations, truncated)`` so a caller can never mistake a
    truncated scope for a complete one.
    """
    stmt = (
        select(
            FireObservation.id,
            FireObservation.sensor,
            FireObservation.latitude,
            FireObservation.longitude,
            FireObservation.acquired_at,
            FireObservation.scan_km,
            FireObservation.track_km,
        )
        .where(FireObservation.is_synthetic == is_synthetic)
        .order_by(FireObservation.acquired_at)
    )
    if bbox is not None:
        stmt = stmt.where(
            FireObservation.longitude >= bbox.west,
            FireObservation.longitude <= bbox.east,
            FireObservation.latitude >= bbox.south,
            FireObservation.latitude <= bbox.north,
        )
    if start_date is not None:
        stmt = stmt.where(FireObservation.acquired_at >= _window_start(start_date))
    if end_date is not None:
        stmt = stmt.where(FireObservation.acquired_at < _window_end(end_date))

    rows = session.execute(stmt).all()

    truncated = False
    if cap is not None and len(rows) > cap:
        logger.warning("harmonization_limit", loaded=len(rows), limit=cap)
        rows = rows[-cap:]
        truncated = True

    observations = [
        _Obs(
            id=str(row.id),
            sensor=row.sensor,
            latitude=row.latitude,
            longitude=row.longitude,
            acquired_at=row.acquired_at
            if row.acquired_at.tzinfo
            else row.acquired_at.replace(tzinfo=UTC),
            scan_km=row.scan_km,
            track_km=row.track_km,
        )
        for row in rows
    ]
    return observations, truncated


def _bucket_by_day(observations: list[_Obs]) -> dict[str, list[_Obs]]:
    buckets: dict[str, list[_Obs]] = {}
    for obs in observations:
        buckets.setdefault(obs.acquired_at.date().isoformat(), []).append(obs)
    return buckets


def compute_matches(
    observations: list[_Obs], params: MatchParameters
) -> list[tuple[_Obs, _Obs, PairScore]]:
    """Cross-family candidates within the time and distance windows, per day bucket.

    Candidate selection is bounded twice: a latitude band of ``max_distance_m``
    (plus padding) is sliced with ``searchsorted``, then the exact time window and
    haversine distance are checked. Scanning the whole 3-hour time window on every
    MODIS detection is quadratic at global scale — a single VIIRS day holds over
    100,000 detections — so the latitude slice comes first.
    """
    window = timedelta(minutes=params.time_window_minutes)
    window_seconds = window.total_seconds()
    lat_band = (params.max_distance_m / 111_320.0) * 1.05 + 1e-6
    matches: list[tuple[_Obs, _Obs, PairScore]] = []

    for bucket in _bucket_by_day(observations).values():
        modis = [obs for obs in bucket if obs.sensor == "MODIS"]
        viirs = [obs for obs in bucket if obs.sensor == "VIIRS"]
        if not modis or not viirs:
            continue

        viirs_by_lat = sorted(viirs, key=lambda obs: obs.latitude)
        viirs_lats = np.array([obs.latitude for obs in viirs_by_lat])

        for a in sorted(modis, key=lambda o: o.acquired_at):
            low = int(np.searchsorted(viirs_lats, a.latitude - lat_band, side="left"))
            high = int(np.searchsorted(viirs_lats, a.latitude + lat_band, side="right"))
            for b in viirs_by_lat[low:high]:
                if abs((a.acquired_at - b.acquired_at).total_seconds()) > window_seconds:
                    continue
                distance = haversine_m(a.latitude, a.longitude, b.latitude, b.longitude)
                if distance > params.max_distance_m:
                    continue
                scored = score_pair(
                    delta_seconds=(a.acquired_at - b.acquired_at).total_seconds(),
                    distance_m=distance,
                    scan_a=a.scan_km,
                    track_a=a.track_km,
                    scan_b=b.scan_km,
                    track_b=b.track_km,
                    params=params,
                )
                if scored.status == "rejected" and scored.score < params.store_threshold:
                    # Below the inspection floor: not worth storing.
                    continue
                matches.append((a, b, scored))

    matches.sort(key=lambda item: item[2].score, reverse=True)
    return matches


def _window_start(day) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _window_end(day) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


#: Safety valve: one UTC day above this is almost certainly a data error. The
#: day is recorded as truncated rather than silently half-processed.
MAX_DAY_OBSERVATIONS = 1_000_000


def scope_key(bbox: BBox | None) -> str:
    """Stable coverage scope; regional runs are independent checkpoints."""
    if bbox is None:
        return "world"
    return f"bbox:{bbox.west:g},{bbox.south:g},{bbox.east:g},{bbox.north:g}"


def _delete_matches_for_day(session: Session, day: date, bbox: BBox | None) -> None:
    """Remove prior associations whose MODIS side falls on ``day`` in scope."""
    a = aliased(FireObservation)
    scope_ids = select(a.id).where(
        a.acquired_at >= _window_start(day),
        a.acquired_at < _window_end(day),
    )
    if bbox is not None:
        scope_ids = scope_ids.where(
            a.longitude >= bbox.west,
            a.longitude <= bbox.east,
            a.latitude >= bbox.south,
            a.latitude <= bbox.north,
        )
    session.execute(
        delete(ObservationMatch).where(ObservationMatch.observation_a_id.in_(scope_ids))
    )


def _insert_matches(
    session: Session,
    pairs: list[tuple[_Obs, _Obs, PairScore]],
    *,
    chunk: int = 500,
) -> dict[str, int]:
    counts = {"probable": 0, "possible": 0, "rejected": 0}
    rows: list[dict[str, Any]] = []
    import uuid as _uuid

    for a, b, scored in pairs:
        rows.append(
            {
                "id": _uuid.uuid4(),
                "observation_a_id": a.id,
                "observation_b_id": b.id,
                "temporal_delta_seconds": scored.temporal_delta_seconds,
                "spatial_distance_m": scored.spatial_distance_m,
                "footprint_overlap": scored.footprint_overlap,
                "association_score": scored.score,
                "match_status": scored.status,
                "components": scored.components,
                "algorithm_version": ALGORITHM_VERSION,
            }
        )
        counts[scored.status] = counts.get(scored.status, 0) + 1

    for start in range(0, len(rows), chunk):
        session.execute(insert(ObservationMatch), rows[start : start + chunk])
    return counts


@_serialized
def run_harmonization_range(
    *,
    start: date,
    end: date,
    params: MatchParameters | None = None,
    is_synthetic: bool = False,
    bbox: BBox | None = None,
    force: bool = False,
    limit_processed: int | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Recompute associations one UTC day per transaction, resumably.

    Each processed day is recorded in ``harmonization_coverage``. Re-running the
    same range skips covered days unless ``force`` is set, so a decades-long pass
    can be interrupted and resumed without repeating work or duplicating pairs.
    """
    if start > end:
        raise ValueError("start must be on or before end")

    params = params or MatchParameters()
    scope = scope_key(bbox)
    total_days = (end - start).days + 1
    summary: dict[str, Any] = {
        "scope": scope,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": total_days,
        "processed": 0,
        "skipped": 0,
        "truncated_days": 0,
        "cancelled": False,
        "observations": 0,
        "pairs": 0,
        "probable": 0,
        "possible": 0,
        "rejected": 0,
    }

    with session_scope() as session:
        run = AlgorithmRun(
            kind="harmonization",
            status="running",
            parameters={
                **asdict(params),
                "scope": {
                    "bbox": bbox.as_list() if bbox is not None else None,
                    "mode": "daily-range",
                },
            },
            stats={},
            algorithm_version=ALGORITHM_VERSION,
            is_synthetic=is_synthetic,
        )
        _lock_transaction(session)
        session.add(run)
        session.flush()

        cursor = start
        try:
            while cursor <= end:
                if should_stop is not None and should_stop():
                    summary["cancelled"] = True
                    break

                existing = session.get(
                    HarmonizationCoverage, (cursor, scope, is_synthetic)
                )
                if existing is not None and not force:
                    summary["skipped"] += 1
                    cursor += timedelta(days=1)
                    continue

                observations = _load_scope_observations(
                    session,
                    is_synthetic,
                    bbox=bbox,
                    start_date=cursor,
                    end_date=cursor,
                    cap=None,
                )[0]

                if len(observations) > MAX_DAY_OBSERVATIONS:
                    logger.error(
                        "harmonization_day_too_large",
                        day=cursor.isoformat(),
                        observations=len(observations),
                    )
                    coverage = existing or HarmonizationCoverage(
                        day=cursor, scope=scope, is_synthetic=is_synthetic
                    )
                    coverage.algorithm_version = ALGORITHM_VERSION
                    coverage.observations = len(observations)
                    coverage.truncated = True
                    coverage.computed_at = datetime.now(UTC)
                    session.add(coverage)
                    session.commit()
                    summary["truncated_days"] += 1
                    cursor += timedelta(days=1)
                    continue

                pairs = compute_matches(observations, params)
                _delete_matches_for_day(session, cursor, bbox)
                counts = _insert_matches(session, pairs)

                coverage = existing or HarmonizationCoverage(
                    day=cursor, scope=scope, is_synthetic=is_synthetic
                )
                coverage.algorithm_version = ALGORITHM_VERSION
                coverage.observations = len(observations)
                coverage.pairs = len(pairs)
                coverage.probable = counts["probable"]
                coverage.possible = counts["possible"]
                coverage.rejected = counts["rejected"]
                coverage.truncated = False
                coverage.computed_at = datetime.now(UTC)
                session.add(coverage)
                session.commit()

                summary["processed"] += 1
                summary["observations"] += len(observations)
                summary["pairs"] += len(pairs)
                summary["probable"] += counts["probable"]
                summary["possible"] += counts["possible"]
                summary["rejected"] += counts["rejected"]
                if progress is not None:
                    progress(
                        {
                            "day": cursor.isoformat(),
                            "observations": len(observations),
                            "pairs": len(pairs),
                            **summary,
                        }
                    )
                if limit_processed and summary["processed"] >= limit_processed:
                    break
                cursor += timedelta(days=1)

            run.status = "cancelled" if summary["cancelled"] else "succeeded"
            run.stats = {
                **summary,
                "matched_sensor_families": True,
                "algorithm": "day-by-day",
            }
            run.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            session.rollback()
            failed = session.get(AlgorithmRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = str(exc)[:1000]
                failed.completed_at = datetime.now(UTC)
                session.commit()
            raise

    summary["run_id"] = str(run.id)
    logger.info("harmonization_range_complete", **summary)
    return summary


def coverage_summary(session: Session, *, is_synthetic: bool = False) -> dict[str, Any]:
    """How much of the archive has been scored for associations."""
    scopes = session.execute(
        select(
            HarmonizationCoverage.scope,
            func.count(),
            func.min(HarmonizationCoverage.day),
            func.max(HarmonizationCoverage.day),
            func.sum(HarmonizationCoverage.observations),
            func.sum(HarmonizationCoverage.pairs),
            func.sum(HarmonizationCoverage.probable),
            func.sum(HarmonizationCoverage.possible),
        )
        .where(HarmonizationCoverage.is_synthetic == is_synthetic)
        .group_by(HarmonizationCoverage.scope)
    ).all()

    latest = session.execute(
        select(func.max(HarmonizationCoverage.computed_at)).where(
            HarmonizationCoverage.is_synthetic == is_synthetic
        )
    ).scalar()

    return {
        "scopes": [
            {
                "scope": row[0],
                "days": int(row[1]),
                "first_day": row[2].isoformat() if row[2] else None,
                "last_day": row[3].isoformat() if row[3] else None,
                "observations": int(row[4] or 0),
                "pairs": int(row[5] or 0),
                "probable": int(row[6] or 0),
                "possible": int(row[7] or 0),
            }
            for row in scopes
        ],
        "last_computed_at": latest.isoformat() if latest else None,
    }



@_serialized
def run_harmonization(
    *,
    params: MatchParameters | None = None,
    is_synthetic: bool = False,
    bbox: BBox | None = None,
    start_date=None,
    end_date=None,
) -> dict:
    """Recompute associations for one provenance scope and record an audit run."""
    params = params or MatchParameters()
    with session_scope() as session:
        scope = {
            "bbox": bbox.as_list() if bbox is not None else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
        run = AlgorithmRun(
            kind="harmonization",
            status="running",
            parameters={**asdict(params), "scope": scope},
            stats={},
            algorithm_version=ALGORITHM_VERSION,
            is_synthetic=is_synthetic,
        )
        _lock_transaction(session)
        session.add(run)
        session.flush()

        try:
            observations, truncated = _load_scope_observations(
                session,
                is_synthetic,
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
                cap=params.max_observations,
            )
            pairs = compute_matches(observations, params)

            # Harmonization is a full recompute for the scope: prior pairs from
            # this scope are replaced so results cannot accumulate stale scores.
            scope_ids = [obs.id for obs in observations]
            for start in range(0, len(scope_ids), 400):
                session.execute(
                    delete(ObservationMatch).where(
                        ObservationMatch.observation_a_id.in_(scope_ids[start : start + 400])
                    )
                )

            counts = {"probable": 0, "possible": 0, "rejected": 0}
            for a, b, scored in pairs:
                session.add(
                    ObservationMatch(
                        observation_a_id=a.id,
                        observation_b_id=b.id,
                        temporal_delta_seconds=scored.temporal_delta_seconds,
                        spatial_distance_m=scored.spatial_distance_m,
                        footprint_overlap=scored.footprint_overlap,
                        association_score=scored.score,
                        match_status=scored.status,
                        components=scored.components,
                        algorithm_version=ALGORITHM_VERSION,
                    )
                )
                counts[scored.status] = counts.get(scored.status, 0) + 1

            sensors = {obs.sensor for obs in observations}
            stats = {
                "scope": scope,
                "observations": len(observations),
                "sensors": sorted(sensors),
                "candidate_pairs": len(pairs),
                "probable": counts["probable"],
                "possible": counts["possible"],
                "rejected": counts["rejected"],
                "matched_sensor_families": len(sensors) > 1,
                "truncated": truncated,
            }
            run.status = "succeeded"
            run.stats = stats
            run.completed_at = datetime.now(UTC)
            session.commit()

            logger.info("harmonization_complete", synthetic=is_synthetic, **stats)
            return {"run_id": str(run.id), **stats}
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            session.rollback()
            failed = session.get(AlgorithmRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = str(exc)[:1000]
                failed.completed_at = datetime.now(UTC)
                session.commit()
            raise
