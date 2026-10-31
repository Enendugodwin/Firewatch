"""Phase 2/3 API surface: observations, harmonization, ingestion administration."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_status_reports_stored_observations_and_provenance(
    client: TestClient, loaded_fixture: dict
) -> None:
    data = client.get("/api/v1/system/status").json()["data"]

    assert data["observations_stored"] == loaded_fixture["inserted"]
    assert data["synthetic_observations"] == loaded_fixture["inserted"]
    assert "synthetic fixture" in data["freshness_reason"]
    assert data["freshness"] in {"current", "delayed", "stale"}
    assert data["last_ingested_at"] is not None
    assert data["last_observation_at"] is not None


def test_observation_search_and_filters(client: TestClient, loaded_fixture: dict) -> None:
    page = client.get("/api/v1/fires").json()
    assert page["total"] == loaded_fixture["inserted"]
    assert len(page["items"]) == loaded_fixture["inserted"]

    first = page["items"][0]
    assert first["sensor"] in {"MODIS", "VIIRS"}
    assert first["is_synthetic"] is True
    assert first["source_record_id"]
    assert first["brightness_channel"]

    modis = client.get("/api/v1/fires", params={"sensor": "MODIS"}).json()
    assert all(item["sensor"] == "MODIS" for item in modis["items"])
    assert modis["total"] == 5

    bbox = client.get("/api/v1/fires", params={"bbox": "9,8,10,9"}).json()
    assert bbox["total"] >= 4
    assert all(9 <= item["longitude"] <= 10 for item in bbox["items"])
    assert all(8 <= item["latitude"] <= 9 for item in bbox["items"])


def test_observation_detail_and_missing_id(client: TestClient, loaded_fixture: dict) -> None:
    item = client.get("/api/v1/fires").json()["items"][0]

    detail = client.get(f"/api/v1/fires/{item['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == item["id"]

    assert client.get("/api/v1/fires/not-a-uuid").status_code == 404
    assert client.get("/api/v1/fires/00000000-0000-0000-0000-000000000000").status_code == 404


def test_geojson_feed_is_bounded_and_labelled(client: TestClient, loaded_fixture: dict) -> None:
    collection = client.get("/api/v1/fires/geojson").json()

    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == loaded_fixture["inserted"]
    assert collection["properties"]["truncated"] is False
    feature = collection["features"][0]
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["synthetic"] is True


def test_sources_report_real_counts(client: TestClient, loaded_fixture: dict) -> None:
    sources = client.get("/api/v1/system/sources").json()
    ingested = [source for source in sources if source["observations"] > 0]

    assert len(sources) == 8
    assert {source["code"] for source in ingested} == {"MODIS_SP", "VIIRS_SNPP_SP"}
    assert all(source["status"] == "ok" for source in ingested)


def test_harmonization_summary_reconciles(client: TestClient, loaded_fixture: dict) -> None:
    summary = client.get("/api/v1/harmonization/summary").json()

    assert summary["observations"] == loaded_fixture["inserted"]
    assert summary["modis_observations"] == 5
    assert summary["viirs_observations"] == 4
    assert summary["matches_probable"] >= 1
    assert summary["matches_probable"] + summary["matches_possible"] >= 3
    assert summary["events"] >= 2
    assert summary["multi_sensor_events"] >= 1
    assert summary["algorithm_version"] == "assoc-v1"
    assert summary["last_run_status"] == "succeeded"


def test_matches_are_inspectable(client: TestClient, loaded_fixture: dict) -> None:
    page = client.get("/api/v1/harmonization/matches", params={"limit": 10}).json()
    assert page["total"] > 0

    match = page["items"][0]
    assert match["observation_a"]["sensor"] != match["observation_b"]["sensor"]
    assert match["association_score"] > 0
    assert match["components"]["temporal_similarity"] is not None
    assert match["components"]["weights"]
    assert match["match_status"] in {"probable", "possible", "rejected"}

    detail = client.get(f"/api/v1/harmonization/matches/{match['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == match["id"]

    probable = client.get("/api/v1/harmonization/matches", params={"status": "probable"}).json()
    assert all(item["match_status"] == "probable" for item in probable["items"])


def test_events_are_listed_with_extent(client: TestClient, loaded_fixture: dict) -> None:
    events = client.get("/api/v1/harmonization/events").json()

    assert events
    event = events[0]
    assert event["observation_count"] >= 2
    assert event["methodology_version"] == "events-v1"
    assert event["maximum_frp_mw"] is not None
    assert event["aggregate_frp_mw"] >= event["maximum_frp_mw"]


def test_ingestion_history_includes_the_fixture_run(
    client: TestClient, loaded_fixture: dict
) -> None:
    jobs = client.get("/api/v1/admin/ingestion/jobs").json()

    assert jobs
    assert all(job["is_synthetic"] for job in jobs)
    assert jobs[0]["status"] == "succeeded"


def test_ingestion_without_key_fails_honestly(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/ingestion/run",
        json={
            "source_code": "MODIS_SP",
            "start_date": "2026-10-28",
            "end_date": "2026-10-28",
        },
    )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "unavailable"
    assert "FIRMS_MAP_KEY" in error["message"]
    assert "hint" in error["details"]


def test_ingestion_rejects_windows_over_five_days(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/ingestion/run",
        json={
            "source_code": "MODIS_SP",
            "start_date": "2026-10-01",
            "end_date": "2026-10-10",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unprocessable"


def test_harmonization_run_endpoint_recomputes(client: TestClient, loaded_fixture: dict) -> None:
    response = client.post("/api/v1/harmonization/run", json={"synthetic": True})
    assert response.status_code == 200

    body = response.json()
    assert body["scopes"][0]["probable"] >= 1
    assert body["events"][0]["events"] >= 2


def test_run_requires_observations(client: TestClient) -> None:
    response = client.post("/api/v1/harmonization/run", json={})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_dashboard_aggregates_come_from_stored_rows(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get("/api/v1/dashboard").json()

    assert body["detections"]["total"] == loaded_fixture["inserted"]
    assert body["detections"]["modis"] == 5
    assert body["detections"]["viirs"] == 4
    assert body["detections"]["frp_mw"] > 0
    assert body["matches"]["total"] >= body["matches"]["probable"]
    assert body["events"] >= 2
    assert "not the number of fires" in body["note"]


def test_tiles_and_availability_endpoints(client: TestClient) -> None:
    tiles = client.get("/api/v1/admin/ingestion/tiles").json()
    assert tiles[0]["key"] == "world"
    assert len(tiles) == 1 + 12 * 9

    response = client.post(
        "/api/v1/admin/ingestion/availability",
        json={
            "source_code": "MODIS_SP",
            "start_date": date(2026, 10, 28).isoformat(),
            "end_date": date(2026, 10, 29).isoformat(),
        },
    )
    assert response.status_code == 503
    assert "availability cannot be verified" in response.json()["error"]["message"]
