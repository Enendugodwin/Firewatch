"""Cross-sensor association: scoring, classification and persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.db.models import DataSource, FireObservation, ObservationMatch
from app.db.session import session_scope
from app.services import harmonization as harmonization_service
from app.services.harmonization import (
    HarmonizationBusy,
    MatchParameters,
    classify,
    run_harmonization,
    score_pair,
)
from app.services.ingestion import ingest_csv_text

MOD = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight,type\n"
    "8.500,9.100,340.2,1.0,1.0,2026-10-28,1020,Terra,MODIS,85,6.1NRT,301.4,12.4,D,0\n"
)
VIIRS = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight,type\n"
    "8.503,9.104,341.9,0.375,0.375,2026-10-28,1035,Suomi-NPP,VIIRS,h,2.0NRT,295.2,9.8,D,0\n"
)


def test_score_is_maximal_for_identical_time_and_place() -> None:
    params = MatchParameters()
    scored = score_pair(
        delta_seconds=0,
        distance_m=0,
        scan_a=1.0,
        track_a=1.0,
        scan_b=0.375,
        track_b=0.375,
        params=params,
    )

    assert scored.score == pytest.approx(1.0)
    assert scored.status == "probable"
    assert scored.footprint_overlap == pytest.approx(1.0)


def test_score_decays_with_time_and_distance() -> None:
    params = MatchParameters()
    near = score_pair(
        delta_seconds=60,
        distance_m=100,
        scan_a=1.0,
        track_a=1.0,
        scan_b=0.375,
        track_b=0.375,
        params=params,
    )
    far = score_pair(
        delta_seconds=5_000,
        distance_m=1_800,
        scan_a=1.0,
        track_a=1.0,
        scan_b=0.375,
        track_b=0.375,
        params=params,
    )

    assert near.score > far.score
    assert near.status == "probable"
    assert far.status != "probable"


def test_missing_footprint_renormalises_weights_instead_of_guessing() -> None:
    params = MatchParameters()
    scored = score_pair(
        delta_seconds=0,
        distance_m=0,
        scan_a=None,
        track_a=None,
        scan_b=None,
        track_b=None,
        params=params,
    )

    assert scored.footprint_overlap is None
    assert scored.components["weights"]["footprint"] == 0.0
    assert "renormalised" in scored.components["weight_note"]
    assert scored.score == pytest.approx(1.0)  # temporal and spatial are perfect


def test_classification_thresholds_are_ordered() -> None:
    params = MatchParameters(probable_threshold=0.8, possible_threshold=0.6, store_threshold=0.4)

    assert classify(0.95, params) == "probable"
    assert classify(0.7, params) == "possible"
    assert classify(0.5, params) == "rejected"
    assert classify(0.1, params) == "rejected"


def test_scoring_is_an_association_score_not_a_probability() -> None:
    scored = score_pair(
        delta_seconds=900,
        distance_m=800,
        scan_a=1.0,
        track_a=1.0,
        scan_b=None,
        track_b=None,
        params=MatchParameters(),
    )

    assert 0.0 <= scored.score <= 1.0
    assert scored.components["temporal_similarity"] < 1.0
    assert scored.components["spatial_proximity"] < 1.0


def test_harmonization_persists_cross_sensor_only(loaded_fixture: dict) -> None:
    with session_scope() as session:
        matches = session.scalars(select(ObservationMatch)).all()
        assert matches, "fixture should produce candidate associations"

        for match in matches:
            a = session.get(FireObservation, match.observation_a_id)
            b = session.get(FireObservation, match.observation_b_id)
            assert a is not None and b is not None
            assert a.sensor != b.sensor, "same-sensor pairs must never be matched"
            assert match.temporal_delta_seconds <= 180 * 60
            assert match.spatial_distance_m <= 2000
            assert 0.0 <= match.association_score <= 1.0
            assert match.match_status in {"probable", "possible", "rejected"}
            assert match.algorithm_version
            assert match.components["weights"]


def test_rerun_is_idempotent_and_does_not_duplicate_pairs(loaded_fixture: dict) -> None:
    with session_scope() as session:
        before = session.scalar(select(func.count()).select_from(ObservationMatch))

    run_harmonization(is_synthetic=True)

    with session_scope() as session:
        after = session.scalar(select(func.count()).select_from(ObservationMatch))

    assert after == before


def test_weak_pairs_are_not_stored() -> None:
    # A pair far below the inspection floor must be dropped, not labelled.
    ingest_csv_text(
        "MODIS_SP",
        "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
        "confidence,version,bright_t31,frp,daynight,type\n"
        "8.500,9.100,340.2,1.0,1.0,2026-10-28,1020,Terra,MODIS,85,6.1NRT,301.4,12.4,D,0\n",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
    )
    ingest_csv_text(
        "VIIRS_SNPP_SP",
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
        "confidence,version,bright_ti5,frp,daynight,type\n"
        "8.518,9.119,341.9,0.375,0.375,2026-10-28,1310,Suomi-NPP,VIIRS,h,2.0NRT,295.2,9.8,D,0\n",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
    )

    result = run_harmonization(is_synthetic=True)

    with session_scope() as session:
        stored = session.scalar(select(func.count()).select_from(ObservationMatch))

    assert stored == 0
    assert result["candidate_pairs"] == 0


def test_runs_are_recorded_with_parameters(loaded_fixture: dict) -> None:
    from app.db.models import AlgorithmRun

    with session_scope() as session:
        run = session.scalars(
            select(AlgorithmRun).where(AlgorithmRun.kind == "harmonization")
        ).first()

    assert run is not None
    assert run.status == "succeeded"
    assert run.parameters["time_window_minutes"] == 180
    assert run.stats["observations"] >= 9
    assert run.stats["matched_sensor_families"] is True


def test_overlapping_runs_are_rejected_instead_of_colliding(client, loaded_fixture) -> None:
    """Two passes over the match table must not surface as a 500."""
    assert harmonization_service._RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(HarmonizationBusy):
            run_harmonization(start_date=date(2026, 1, 1), end_date=date(2026, 1, 2))

        response = client.post(
            "/api/v1/harmonization/run",
            json={"start_date": "2026-01-01", "end_date": "2026-01-02"},
        )
        assert response.status_code == 409
        assert "already in progress" in response.json()["error"]["message"]
    finally:
        harmonization_service._RUN_LOCK.release()


def test_summary_and_matches_are_scoped_to_the_requested_period(client) -> None:
    """The Sensor Intelligence page asks for its header period, not the store."""

    def add_observation(session, code: str, record: str, sensor: str, day: date):
        source = session.scalars(
            select(DataSource).where(DataSource.source_code == code)
        ).first()
        assert source is not None
        row = FireObservation(
            source_id=source.id,
            source_code=source.source_code,
            source_record_id=record,
            sensor=sensor,
            satellite="Terra" if sensor == "MODIS" else "SNPP",
            latitude=-3.1,
            longitude=-60.2,
            acquired_at=datetime(day.year, day.month, day.day, 13, 45, tzinfo=UTC),
            source_product=code,
            source_payload={},
            quality_flags={},
        )
        session.add(row)
        session.flush()
        return row

    with session_scope() as session:
        modis_a = add_observation(session, "MODIS_NRT", "period-modis-a", "MODIS", date(2026, 5, 1))
        viirs_a = add_observation(
            session, "VIIRS_SNPP_NRT", "period-viirs-a", "VIIRS", date(2026, 5, 1)
        )
        add_observation(session, "MODIS_NRT", "period-modis-b", "MODIS", date(2026, 5, 2))
        add_observation(session, "VIIRS_SNPP_NRT", "period-viirs-b", "VIIRS", date(2026, 5, 2))
        session.add(
            ObservationMatch(
                observation_a_id=modis_a.id,
                observation_b_id=viirs_a.id,
                temporal_delta_seconds=120,
                spatial_distance_m=900.0,
                association_score=0.91,
                match_status="probable",
                match_day=date(2026, 5, 1),
                components={},
                algorithm_version="test",
            )
        )
        session.commit()

    scoped = client.get(
        "/api/v1/harmonization/summary",
        params={"start_date": "2026-05-01", "end_date": "2026-05-01"},
    )
    assert scoped.status_code == 200, scoped.text
    body = scoped.json()
    assert body["observations"] == 2
    assert body["matches_total"] == 1
    assert body["period_start"] == "2026-05-01"

    whole = client.get("/api/v1/harmonization/summary")
    assert whole.status_code == 200
    assert whole.json()["observations"] == 4
    assert whole.json()["period_start"] is None

    empty_day = client.get(
        "/api/v1/harmonization/matches",
        params={"start_date": "2026-05-02", "end_date": "2026-05-02"},
    )
    assert empty_day.status_code == 200
    assert empty_day.json()["total"] == 0

    scoped_matches = client.get(
        "/api/v1/harmonization/matches",
        params={"start_date": "2026-05-01", "end_date": "2026-05-01"},
    )
    assert scoped_matches.json()["total"] == 1

    reversed_period = client.get(
        "/api/v1/harmonization/summary",
        params={"start_date": "2026-05-02", "end_date": "2026-05-01"},
    )
    assert reversed_period.status_code == 422


def test_every_match_records_its_utc_day(client, loaded_fixture) -> None:
    """The denormalised match_day is required by the period-scoped queries."""
    with session_scope() as session:
        rows = session.scalars(select(ObservationMatch)).all()
    assert rows
    assert all(row.match_day is not None for row in rows)
