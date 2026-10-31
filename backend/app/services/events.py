"""Estimated fire-event grouping.

Spatiotemporal DBSCAN over observations, in metres and seconds, implemented with
numpy so results are deterministic and dependency-free. A cluster is an
*estimated event*, never a confirmed fire, and never implies continuous
monitoring between satellite overpasses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time, timedelta

import numpy as np
from sqlalchemy import delete, select

from app.core.logging import get_logger
from app.db.models import AlgorithmRun, EventObservation, FireEvent, FireObservation
from app.db.session import session_scope
from app.services.observation_queries import BBox  # noqa: TC001 - runtime type hints

logger = get_logger(__name__)

METHODOLOGY_VERSION = "events-v1"


def _day_start(day) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _day_end(day) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


@dataclass(frozen=True)
class ClusterParameters:
    eps_meters: float = 1500.0
    eps_hours: float = 24.0
    min_samples: int = 2
    max_observations: int = 20_000


def _project(
    lat: np.ndarray, lon: np.ndarray, ref_lat: float, ref_lon: float
) -> tuple[np.ndarray, np.ndarray]:
    """Local equirectangular projection to metres around the data centroid."""
    x = np.radians(lon - ref_lon) * 6_371_008.8 * np.cos(np.radians(ref_lat))
    y = np.radians(lat - ref_lat) * 6_371_008.8
    return x, y


def dbscan_labels(
    x: np.ndarray, y: np.ndarray, t: np.ndarray, params: ClusterParameters
) -> np.ndarray:
    """
    DBSCAN with an anisotropic metric: spatial distance in metres and temporal
    distance in seconds are normalised by their epsilon before combining, so one
    neighbourhood has exactly one definition in both dimensions.

    Neighbourhoods are computed in row chunks so a few thousand observations do
    not require an n×n distance matrix in memory at once.

    Returns a label per point; -1 marks noise.
    """
    n = len(x)
    labels = np.full(n, -1, dtype=int)
    if n == 0:
        return labels

    neighbours: list[np.ndarray] = [np.empty(0, dtype=int)] * n
    chunk = 512
    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        dx = x[start:stop, None] - x[None, :]
        dy = y[start:stop, None] - y[None, :]
        dt = (t[start:stop, None] - t[None, :]) / 3600.0
        spatial = np.sqrt(dx**2 + dy**2) / params.eps_meters
        temporal = np.abs(dt) / params.eps_hours
        mask = (spatial**2 + temporal**2) <= 1.0
        for offset in range(stop - start):
            neighbours[start + offset] = np.flatnonzero(mask[offset])

    visited = np.zeros(n, dtype=bool)
    cluster = 0
    for point in range(n):
        if visited[point]:
            continue
        visited[point] = True
        seeds = neighbours[point]
        if seeds.size < params.min_samples:
            continue
        labels[point] = cluster
        queue: list[int] = [int(value) for value in seeds]
        while queue:
            candidate = queue.pop()
            if not visited[candidate]:
                visited[candidate] = True
                candidate_neighbours = neighbours[candidate]
                if candidate_neighbours.size >= params.min_samples:
                    for extra in candidate_neighbours:
                        value = int(extra)
                        if not visited[value] and value not in queue:
                            queue.append(value)
            if labels[candidate] == -1:
                labels[candidate] = cluster
        cluster += 1

    return labels


def run_event_clustering(
    *,
    params: ClusterParameters | None = None,
    is_synthetic: bool = False,
    bbox: BBox | None = None,
    start_date=None,
    end_date=None,
) -> dict:
    params = params or ClusterParameters()

    with session_scope() as session:
        scope = {
            "bbox": bbox.as_list() if bbox is not None else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }
        run = AlgorithmRun(
            kind="event_clustering",
            status="running",
            parameters={**asdict(params), "scope": scope},
            stats={},
            algorithm_version=METHODOLOGY_VERSION,
            is_synthetic=is_synthetic,
        )
        session.add(run)
        session.flush()

        try:
            stmt = (
                select(
                    FireObservation.id,
                    FireObservation.latitude,
                    FireObservation.longitude,
                    FireObservation.acquired_at,
                    FireObservation.sensor,
                    FireObservation.frp_mw,
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
                stmt = stmt.where(FireObservation.acquired_at >= _day_start(start_date))
            if end_date is not None:
                stmt = stmt.where(FireObservation.acquired_at < _day_end(end_date))
            rows = session.execute(stmt).all()

            if len(rows) > params.max_observations:
                logger.warning(
                    "event_clustering_limit",
                    loaded=len(rows),
                    limit=params.max_observations,
                )
                rows = rows[-params.max_observations :]

            # Event grouping is a full recompute for this provenance scope.
            previous = session.scalars(
                select(FireEvent.id)
                .join(AlgorithmRun, FireEvent.run_id == AlgorithmRun.id)
                .where(AlgorithmRun.is_synthetic == is_synthetic)
            ).all()
            if previous:
                for start in range(0, len(previous), 400):
                    session.execute(
                        delete(EventObservation).where(
                            EventObservation.event_id.in_(previous[start : start + 400])
                        )
                    )
                session.execute(delete(FireEvent).where(FireEvent.id.in_(previous)))

            if not rows:
                stats = {"scope": scope, "observations": 0, "events": 0, "unclustered": 0}
                run.status = "succeeded"
                run.stats = stats
                run.completed_at = datetime.now(UTC)
                session.commit()
                return {"run_id": str(run.id), **stats}

            lats = np.array([r.latitude for r in rows], dtype=float)
            lons = np.array([r.longitude for r in rows], dtype=float)
            times = np.array(
                [
                    (
                        r.acquired_at if r.acquired_at.tzinfo else r.acquired_at.replace(tzinfo=UTC)
                    ).timestamp()
                    for r in rows
                ],
                dtype=float,
            )

            x, y = _project(lats, lons, float(lats.mean()), float(lons.mean()))
            labels = dbscan_labels(x, y, times, params)

            events_created = 0
            multi_sensor_events = 0
            for label in sorted({int(value) for value in labels if value >= 0}):
                mask = labels == label
                members = [rows[int(index)] for index in np.flatnonzero(mask)]
                frp_values = [m.frp_mw for m in members if m.frp_mw is not None]
                sensors = {m.sensor for m in members}
                event = FireEvent(
                    first_detected_at=min(m.acquired_at for m in members),
                    last_detected_at=max(m.acquired_at for m in members),
                    centroid_latitude=float(sum(m.latitude for m in members) / len(members)),
                    centroid_longitude=float(sum(m.longitude for m in members) / len(members)),
                    min_latitude=float(min(m.latitude for m in members)),
                    max_latitude=float(max(m.latitude for m in members)),
                    min_longitude=float(min(m.longitude for m in members)),
                    max_longitude=float(max(m.longitude for m in members)),
                    observation_count=len(members),
                    sensor_count=len(sensors),
                    maximum_frp_mw=max(frp_values) if frp_values else None,
                    aggregate_frp_mw=sum(frp_values) if frp_values else None,
                    clustering_method="dbscan_spatiotemporal",
                    clustering_parameters=asdict(params),
                    methodology_version=METHODOLOGY_VERSION,
                    run_id=run.id,
                )
                session.add(event)
                session.flush()
                for member in members:
                    session.add(EventObservation(event_id=event.id, observation_id=member.id))
                if len(sensors) > 1:
                    multi_sensor_events += 1
                events_created += 1

            stats = {
                "scope": scope,
                "observations": len(rows),
                "events": events_created,
                "unclustered": int((labels == -1).sum()),
                "multi_sensor_events": multi_sensor_events,
            }
            run.status = "succeeded"
            run.stats = stats
            run.completed_at = datetime.now(UTC)
            session.commit()

            logger.info("event_clustering_complete", synthetic=is_synthetic, **stats)
            return {"run_id": str(run.id), **stats}
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            failed = session.get(AlgorithmRun, run.id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = str(exc)[:1000]
                failed.completed_at = datetime.now(UTC)
                session.commit()
            raise
