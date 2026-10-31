"""Cross-sensor association: scoring, classification and persistence."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.db.models import FireObservation, ObservationMatch
from app.db.session import session_scope
from app.services.harmonization import (
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
