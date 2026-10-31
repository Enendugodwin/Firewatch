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

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta

import numpy as np
from sqlalchemy import delete, select

from app.core.logging import get_logger
from app.db.models import AlgorithmRun, FireObservation, ObservationMatch
from app.db.session import session_scope
from app.services.geo import footprint_overlap, haversine_m
from app.services.observation_queries import BBox  # noqa: TC001 - runtime type hints

logger = get_logger(__name__)

ALGORITHM_VERSION = "assoc-v1"


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

    if len(rows) > params.max_observations:
        logger.warning("harmonization_limit", loaded=len(rows), limit=params.max_observations)
        rows = rows[-params.max_observations :]

    return [
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


def _bucket_by_day(observations: list[_Obs]) -> dict[str, list[_Obs]]:
    buckets: dict[str, list[_Obs]] = {}
    for obs in observations:
        buckets.setdefault(obs.acquired_at.date().isoformat(), []).append(obs)
    return buckets


def compute_matches(
    observations: list[_Obs], params: MatchParameters
) -> list[tuple[_Obs, _Obs, PairScore]]:
    """Cross-family candidates within the time window, per day bucket."""
    window = timedelta(minutes=params.time_window_minutes)
    matches: list[tuple[_Obs, _Obs, PairScore]] = []

    for bucket in _bucket_by_day(observations).values():
        modis = sorted(
            (obs for obs in bucket if obs.sensor == "MODIS"), key=lambda o: o.acquired_at
        )
        viirs = sorted(
            (obs for obs in bucket if obs.sensor == "VIIRS"), key=lambda o: o.acquired_at
        )
        if not modis or not viirs:
            continue

        viirs_times = np.array([o.acquired_at.timestamp() for o in viirs])

        for a in modis:
            start = a.acquired_at - window
            end = a.acquired_at + window
            low = np.searchsorted(viirs_times, start.timestamp(), side="left")
            high = np.searchsorted(viirs_times, end.timestamp(), side="right")
            for b in viirs[low:high]:
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
        session.add(run)
        session.flush()

        try:
            observations = _load_observations(
                session,
                is_synthetic,
                params,
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
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
