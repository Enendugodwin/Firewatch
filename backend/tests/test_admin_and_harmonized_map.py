"""Admin FIRMS key management and the harmonized map view."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import DataSource, FireObservation, ObservationMatch
from app.db.session import session_scope


def _source(session, code: str) -> DataSource:
    source = session.scalars(
        select(DataSource).where(DataSource.source_code == code)
    ).first()
    assert source is not None, code
    return source


def _observation(session, *, code: str, record: str, sensor: str, lon: float) -> FireObservation:
    source = _source(session, code)
    row = FireObservation(
        source_id=source.id,
        source_code=source.source_code,
        source_record_id=record,
        sensor=sensor,
        satellite="Terra" if sensor == "MODIS" else "SNPP",
        latitude=-3.1,
        longitude=lon,
        acquired_at=datetime(2024, 6, 1, 13, 45, tzinfo=UTC),
        source_product=code,
        source_payload={},
        quality_flags={},
    )
    session.add(row)
    session.flush()
    return row


def _link(session, modis: FireObservation, viirs: FireObservation, status: str) -> None:
    session.add(
        ObservationMatch(
            observation_a_id=modis.id,
            observation_b_id=viirs.id,
            temporal_delta_seconds=120,
            spatial_distance_m=800.0,
            association_score=0.9 if status == "probable" else 0.6,
            match_status=status,
            components={},
            algorithm_version="test",
        )
    )
    session.flush()


def test_firms_key_is_write_only(client) -> None:
    key = "abcdef0123456789abcdef0123456789"
    saved = client.put("/api/v1/admin/settings/firms", json={"api_key": key})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["configured"] is True
    assert body["source"] == "database"
    assert body["masked"].endswith(key[-4:])
    assert key not in saved.text

    status = client.get("/api/v1/admin/settings/firms")
    assert status.status_code == 200
    assert key not in status.text
    assert status.json()["configured"] is True

    removed = client.delete("/api/v1/admin/settings/firms")
    assert removed.status_code == 200
    assert removed.json()["configured"] is False

    invalid = client.put("/api/v1/admin/settings/firms", json={"api_key": "bad key!"})
    assert invalid.status_code == 422

    # Leave the process back in its unconfigured test state.
    client.delete("/api/v1/admin/settings/firms")


def test_harmonized_map_drops_associated_viirs(client) -> None:
    with session_scope() as session:
        modis = _observation(session, code="MODIS_NRT", record="h-modis", sensor="MODIS", lon=-60.2)
        matched = _observation(
            session, code="VIIRS_SNPP_NRT", record="h-viirs-a", sensor="VIIRS", lon=-60.21
        )
        _observation(
            session, code="VIIRS_SNPP_NRT", record="h-viirs-b", sensor="VIIRS", lon=-60.19
        )
        _link(session, modis, matched, "probable")
        session.commit()

    query = {
        "bbox": "-61,-4,-59,-2",
        "start_date": "2024-06-01",
        "end_date": "2024-06-01",
        "synthetic": "false",
    }
    raw = client.get("/api/v1/fires/geojson", params={**query, "limit": 100})
    assert raw.status_code == 200, raw.text
    assert raw.json()["properties"]["total"] == 3

    harmonized = client.get(
        "/api/v1/fires/geojson", params={**query, "harmonized": "true", "limit": 100}
    )
    assert harmonized.status_code == 200, harmonized.text
    payload = harmonized.json()
    assert payload["properties"]["total"] == 2
    sensors = {feature["properties"]["sensor"] for feature in payload["features"]}
    assert sensors == {"MODIS", "VIIRS"}

    aggregate = client.get(
        "/api/v1/fires/aggregate",
        params={**query, "zoom": 6, "harmonized": "true"},
    )
    assert aggregate.status_code == 200, aggregate.text
    body = aggregate.json()
    assert body["harmonized"] is True
    assert body["source"] == "live"
    assert body["total_detections"] == 2
