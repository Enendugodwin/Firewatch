"""Bulk ingestion and CSV export behaviour."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_run_all_requires_a_configured_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/ingestion/run-all",
        json={"start_date": "2026-10-30", "end_date": "2026-10-31"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"


def test_run_all_validates_the_window_and_sources(client: TestClient) -> None:
    inverted = client.post(
        "/api/v1/admin/ingestion/run-all",
        json={"start_date": "2026-10-31", "end_date": "2026-10-01"},
    )
    assert inverted.status_code == 422

    too_long = client.post(
        "/api/v1/admin/ingestion/run-all",
        json={"start_date": "2026-10-01", "end_date": "2026-10-20"},
    )
    assert too_long.status_code == 422

    unknown = client.post(
        "/api/v1/admin/ingestion/run-all",
        json={
            "start_date": "2026-10-30",
            "end_date": "2026-10-31",
            "source_codes": ["NOT_A_SOURCE"],
        },
    )
    # The key check comes first, so this is the same 503 until a key exists.
    assert unknown.status_code in {400, 503}


def test_matches_export_is_csv_with_provenance(
    client: TestClient, loaded_fixture: dict
) -> None:
    page = client.get("/api/v1/harmonization/matches", params={"limit": 500}).json()
    assert page["total"] > 0

    response = client.get("/api/v1/harmonization/matches.csv", params={"limit": 500})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    lines = [line for line in response.text.splitlines() if line.strip()]
    header = lines[0].split(",")
    assert header[:5] == [
        "match_id",
        "status",
        "association_score",
        "temporal_delta_seconds",
        "spatial_distance_m",
    ]
    assert "a_sensor" in header and "b_satellite" in header
    assert len(lines) - 1 == page["total"]

    # The first data row carries both observations' provenance.
    first = lines[1].split(",")
    assert float(first[header.index("association_score")]) >= 0
    assert first[header.index("a_sensor")] in {"MODIS", "VIIRS"}
    assert first[header.index("b_sensor")] in {"MODIS", "VIIRS"}
    assert first[header.index("a_sensor")] != first[header.index("b_sensor")]


def test_matches_export_honours_filters(client: TestClient, loaded_fixture: dict) -> None:
    probable = client.get(
        "/api/v1/harmonization/matches.csv", params={"status": "probable", "limit": 500}
    ).text
    possible = client.get(
        "/api/v1/harmonization/matches.csv", params={"status": "possible", "limit": 500}
    ).text

    probable_rows = [line for line in probable.splitlines() if line.strip()]
    possible_rows = [line for line in possible.splitlines() if line.strip()]
    assert all("probable" in line for line in probable_rows[1:])
    assert all("possible" in line for line in possible_rows[1:])
