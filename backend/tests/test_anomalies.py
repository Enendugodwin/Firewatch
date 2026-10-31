"""Anomaly detection: baselines, gaps and the insufficient-history guard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import DataSource, FireObservation, SourceAvailability
from app.db.session import session_scope
from app.services.anomalies import robust_baseline, severity_for


def _seed(sensor: str, source_code: str, satellite: str, days: list[tuple[date, int]]) -> None:
    """Insert ``count`` detections per day plus availability, as ingestion would."""
    with session_scope() as session:
        source = session.scalar(select(DataSource).where(DataSource.source_code == source_code))
        assert source is not None
        for day, count in days:
            acquired = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=12)
            for index in range(count):
                session.add(
                    FireObservation(
                        source_id=source.id,
                        source_code=source_code,
                        source_record_id=f"{source_code}-{day.isoformat()}-{index}",
                        sensor=sensor,
                        satellite=satellite,
                        latitude=9.0 + index * 0.001,
                        longitude=8.0 + index * 0.001,
                        acquired_at=acquired,
                        confidence_category="nominal",
                        frp_mw=10.0,
                        daynight="D",
                        processing_version="2.0NRT",
                        source_product=source_code,
                        source_payload={"seed": True},
                        quality_flags={"seeded": True},
                        is_synthetic=False,
                    )
                )
            existing = session.scalar(
                select(SourceAvailability).where(
                    SourceAvailability.source_id == source.id,
                    SourceAvailability.observation_date == day,
                )
            )
            if existing:
                existing.status = "available"
            else:
                session.add(
                    SourceAvailability(
                        source_id=source.id, observation_date=day, status="available"
                    )
                )


def _history(day: date, count: int) -> list[tuple[date, int]]:
    """
    Forty baseline days (leaving ``day - 1`` free) with a small natural spread,
    so the robust scale is non-zero and a z-score is meaningful.
    """
    return [(day - timedelta(days=offset), count + offset % 3) for offset in range(2, 42)]


def test_insufficient_history_is_reported_not_faked(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/anomalies",
        params={
            "start_date": "2026-10-28",
            "end_date": "2026-10-31",
            "synthetic": "true",
        },
    ).json()

    assert body["status"] == "insufficient_history"
    assert body["anomalies"] == []
    assert body["points"] == []
    assert body["baseline"] is None
    assert body["requirements"]["available_days"] < body["requirements"]["needed_days"]
    assert "will not score" in body["requirements"]["note"]


def test_spike_is_flagged_against_its_own_history(client: TestClient) -> None:
    start = date(2026, 11, 1)
    seed = _history(start, 5)
    spike_day = start - timedelta(days=1)
    _seed("VIIRS", "VIIRS_SNPP_NRT", "N", seed + [(spike_day, 60)])

    body = client.get(
        "/api/v1/anomalies",
        params={"start_date": spike_day.isoformat(), "end_date": spike_day.isoformat()},
    ).json()

    assert body["status"] == "ok"
    assert body["evaluated_days"] == 1
    assert body["baseline"]["median"] == 6.0
    assert body["baseline"]["mad"] > 0
    flagged = body["anomalies"]
    assert len(flagged) == 1
    assert flagged[0]["date"] == spike_day.isoformat()
    assert flagged[0]["observed"] == 60
    assert flagged[0]["severity"] in {"critical", "high", "moderate"}
    assert flagged[0]["robust_z"] is not None and flagged[0]["robust_z"] >= 3
    assert "baseline median" in (flagged[0]["explanation"] or "")


def test_normal_days_are_not_flagged(client: TestClient) -> None:
    start = date(2026, 12, 1)
    seed = _history(start, 5)
    _seed("VIIRS", "VIIRS_SNPP_NRT", "N", seed + [(start - timedelta(days=1), 6)])

    body = client.get(
        "/api/v1/anomalies",
        params={
            "start_date": (start - timedelta(days=1)).isoformat(),
            "end_date": (start - timedelta(days=1)).isoformat(),
        },
    ).json()

    assert body["status"] == "ok"
    assert body["anomalies"] == []
    assert body["points"][0]["severity"] == "normal"


def test_days_without_availability_are_excluded_from_the_baseline(
    client: TestClient,
) -> None:
    """A missing day must not enter the baseline as a zero."""
    start = date(2027, 1, 1)
    seed = _history(start, 5)
    _seed("VIIRS", "VIIRS_SNPP_NRT", "N", seed + [(start - timedelta(days=1), 6)])

    # Remove availability (but keep the observations) for ten baseline days: they
    # are gaps, so they must be excluded rather than counted as zero detections.
    with session_scope() as session:
        dropped = [start - timedelta(days=offset) for offset in range(2, 12)]
        for day in dropped:
            row = session.scalar(
                select(SourceAvailability).where(
                    SourceAvailability.observation_date == day,
                )
            )
            if row:
                session.delete(row)

    body = client.get(
        "/api/v1/anomalies",
        params={
            "start_date": (start - timedelta(days=1)).isoformat(),
            "end_date": (start - timedelta(days=1)).isoformat(),
        },
    ).json()

    assert body["status"] == "ok"
    assert body["baseline"]["days"] < 40
    assert body["baseline"]["median"] == 6.0


def test_robust_baseline_ignores_a_single_outlier() -> None:
    values = [5.0] * 20 + [500.0]
    baseline = robust_baseline(values)

    assert baseline.median == 5.0
    assert baseline.mad == 0.0
    assert baseline.scale == 0.0
    assert severity_for(3.2) == "moderate"
    assert severity_for(4.1) == "high"
    assert severity_for(5.5) == "critical"


def test_bad_parameters_are_rejected(client: TestClient) -> None:
    assert (
        client.get(
            "/api/v1/anomalies",
            params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
        ).status_code
        == 400
    )
    assert client.get("/api/v1/anomalies").status_code == 422
    assert (
        client.get(
            "/api/v1/anomalies",
            params={
                "start_date": "2026-10-01",
                "end_date": "2026-10-02",
                "z_threshold": 0.1,
            },
        ).status_code
        == 422
    )
