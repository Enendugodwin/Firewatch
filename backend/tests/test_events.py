"""Estimated event grouping: clustering, provenance and idempotence."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import func, select

from app.db.models import EventObservation, FireEvent
from app.db.session import session_scope
from app.services.events import ClusterParameters, dbscan_labels, run_event_clustering


def test_dbscan_separates_distant_clusters() -> None:
    # Two tight groups ~50 km apart, well inside a 6-hour window.
    x = np.array([0, 50, 120, 5_000_000, 5_000_050, 5_000_120], dtype=float)
    y = np.zeros_like(x)
    t = np.array([0, 600, 1200, 0, 600, 1200], dtype=float)

    labels = dbscan_labels(x, y, t, ClusterParameters(eps_meters=500, min_samples=2))

    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]
    assert set(labels) == {0, 1}


def test_distant_in_time_does_not_cluster() -> None:
    t = np.array([0, 60 * 60 * 48], dtype=float)  # 48 hours apart
    x = np.zeros(2)
    y = np.zeros(2)

    labels = dbscan_labels(x, y, t, ClusterParameters(eps_hours=6, min_samples=1))

    assert labels.tolist() == [0, 1]


def test_min_samples_one_labels_singletons() -> None:
    labels = dbscan_labels(
        np.array([0.0, 1_000_000.0]),
        np.zeros(2),
        np.array([0.0, 0.0]),
        ClusterParameters(min_samples=1),
    )
    assert sorted(labels.tolist()) == [0, 1]


def test_fixture_produces_multi_sensor_events(loaded_fixture: dict) -> None:
    with session_scope() as session:
        events = session.scalars(select(FireEvent)).all()

    assert len(events) >= 2
    accounts = [event.observation_count for event in events]
    assert max(accounts) >= 3

    multi = [event for event in events if event.sensor_count > 1]
    assert multi, "the fixture contains a cross-sensor cluster"

    biggest = max(events, key=lambda event: event.observation_count)
    assert biggest.aggregate_frp_mw is not None
    assert biggest.maximum_frp_mw is not None
    assert biggest.aggregate_frp_mw >= biggest.maximum_frp_mw
    assert biggest.first_detected_at <= biggest.last_detected_at
    assert biggest.min_latitude <= biggest.centroid_latitude <= biggest.max_latitude
    assert biggest.clustering_method == "dbscan_spatiotemporal"
    assert biggest.methodology_version == "events-v1"


def test_events_keep_their_member_observations(loaded_fixture: dict) -> None:
    with session_scope() as session:
        event = session.scalars(
            select(FireEvent).order_by(FireEvent.observation_count.desc())
        ).first()
        assert event is not None
        links = session.scalar(
            select(func.count())
            .select_from(EventObservation)
            .where(EventObservation.event_id == event.id)
        )
        assert links == event.observation_count


def test_reclustering_is_idempotent(loaded_fixture: dict) -> None:
    with session_scope() as session:
        before = session.scalar(select(func.count()).select_from(FireEvent))

    run_event_clustering(is_synthetic=True)

    with session_scope() as session:
        after = session.scalar(select(func.count()).select_from(FireEvent))
        links = session.scalar(select(func.count()).select_from(EventObservation))

    assert after == before
    assert links >= before


def test_no_observations_is_not_an_error() -> None:
    result = run_event_clustering(is_synthetic=True)

    assert result["events"] == 0
    assert result["observations"] == 0


def test_clusters_never_claim_continuous_monitoring(loaded_fixture: dict) -> None:
    with session_scope() as session:
        event = session.scalars(select(FireEvent)).first()

    assert event is not None
    assert event.clustering_parameters["eps_hours"] > 0
    # Parameters are stored with every event so the estimate can be reproduced.
    assert set(event.clustering_parameters) == {
        "eps_meters",
        "eps_hours",
        "min_samples",
        "max_observations",
    }
    assert pytest.approx(event.clustering_parameters["eps_meters"]) == 1500.0
