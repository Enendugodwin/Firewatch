"""Day-by-day harmonization: coverage checkpoints, resumption and correctness."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import HarmonizationCoverage, ObservationMatch
from app.db.session import session_scope
from app.services import harmonization as service

FIXTURE_START = date(2026, 10, 26)
FIXTURE_END = date(2026, 10, 30)


def _obs(obs_id: str, sensor: str, lat: float, lon: float, hour: int) -> service._Obs:
    return service._Obs(
        id=obs_id,
        sensor=sensor,
        latitude=lat,
        longitude=lon,
        acquired_at=datetime(2026, 10, 29, hour, 0, tzinfo=UTC),
        scan_km=1.0,
        track_km=1.0,
    )


def test_range_pass_records_every_scanned_day(loaded_fixture: dict) -> None:
    summary = service.run_harmonization_range(
        start=FIXTURE_START, end=FIXTURE_END, is_synthetic=True
    )

    assert summary["scope"] == "world"
    assert summary["processed"] == summary["days"]
    assert summary["skipped"] == 0
    assert summary["truncated_days"] == 0
    assert summary["pairs"] > 0

    with session_scope() as session:
        covered = session.scalar(
            select(func.count()).select_from(HarmonizationCoverage).where(
                HarmonizationCoverage.is_synthetic.is_(True)
            )
        )
        assert covered == summary["days"]


def test_range_pass_is_resumable_and_force_safe(loaded_fixture: dict) -> None:
    first = service.run_harmonization_range(
        start=FIXTURE_START, end=FIXTURE_END, is_synthetic=True
    )
    with session_scope() as session:
        matches_after_first = session.scalar(
            select(func.count()).select_from(ObservationMatch)
        )

    second = service.run_harmonization_range(
        start=FIXTURE_START, end=FIXTURE_END, is_synthetic=True
    )
    assert second["processed"] == 0
    assert second["skipped"] == second["days"]

    forced = service.run_harmonization_range(
        start=FIXTURE_START, end=FIXTURE_END, is_synthetic=True, force=True
    )
    assert forced["processed"] == forced["days"]
    with session_scope() as session:
        matches_after_force = session.scalar(
            select(func.count()).select_from(ObservationMatch)
        )
    # A forced recompute replaces pairs for the day; it never accumulates them.
    assert matches_after_force == matches_after_first
    assert first["pairs"] == forced["pairs"]


def test_latitude_prefilter_keeps_the_exact_distance_rule() -> None:
    anchor = _obs("modis", "MODIS", 0.0, 0.0, 12)
    near = _obs("near", "VIIRS", 0.001, 0.001, 12)  # ~150 m away
    far = _obs("far", "VIIRS", 0.05, 0.05, 12)  # ~7 km away, outside 2 km
    late = _obs("late", "VIIRS", 0.001, 0.001, 20)  # same place, outside 180 min

    pairs = service.compute_matches(
        [anchor, near, far, late], service.MatchParameters()
    )

    assert [pair[1].id for pair in pairs] == ["near"]


def test_coverage_endpoint_reports_scanned_days(
    client: TestClient, loaded_fixture: dict
) -> None:
    service.run_harmonization_range(
        start=FIXTURE_START, end=FIXTURE_END, is_synthetic=True
    )

    body = client.get(
        "/api/v1/harmonization/coverage", params={"synthetic": "true"}
    ).json()

    assert body["scopes"], body
    world = next(scope for scope in body["scopes"] if scope["scope"] == "world")
    assert world["days"] == 5
    assert world["first_day"] == FIXTURE_START.isoformat()
    assert world["last_day"] == FIXTURE_END.isoformat()
    assert world["pairs"] > 0
    assert body["last_computed_at"] is not None
