"""Reports, regions, exposure screening and the deterministic assistant."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_report_reconciles_with_the_analytics_summary(
    client: TestClient, loaded_fixture: dict
) -> None:
    report = client.get(
        "/api/v1/reports/summary",
        params={"start_date": "2026-10-27", "end_date": "2026-10-31", "synthetic": "true"},
    ).json()

    assert report["headline"]["detections"] > 0
    assert report["headline"]["detections"] == sum(
        point["detections"] for point in report["series"]
    )
    assert report["coverage"]["range_days"] == 5
    assert report["anomalies"]["status"] in {"ok", "insufficient_history"}
    assert any("detections, not confirmed fires" in note for note in report["notes"])


def test_report_exports_markdown_and_json(client: TestClient, loaded_fixture: dict) -> None:
    markdown = client.get(
        "/api/v1/reports/export",
        params={
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "format": "markdown",
        },
    )
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert "attachment" in markdown.headers["content-disposition"]
    assert markdown.text.startswith("# FIREWATCH X report")
    assert "## Daily detections" in markdown.text

    as_json = client.get(
        "/api/v1/reports/export",
        params={
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "format": "json",
        },
    )
    assert as_json.headers["content-type"].startswith("application/json")
    assert as_json.json()["version"] == "report-v1"


def test_report_rejects_inverted_ranges(client: TestClient) -> None:
    response = client.get(
        "/api/v1/reports/summary",
        params={"start_date": "2026-10-31", "end_date": "2026-10-01"},
    )
    assert response.status_code == 400


def test_regions_are_labelled_as_approximate_boxes(
    client: TestClient, loaded_fixture: dict
) -> None:
    body = client.get(
        "/api/v1/regions",
        params={
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "limit": 5,
        },
    ).json()

    assert "approximate centroid boxes" in body["note"]
    assert len(body["regions"]) <= 5
    counts = [region["detections"] for region in body["regions"]]
    assert counts == sorted(counts, reverse=True)
    # The fixture sits over northern Nigeria.
    nigeria = next(region for region in body["regions"] if region["name"] == "Nigeria")
    assert nigeria["detections"] == loaded_fixture["inserted"]


def test_exposure_screens_registered_assets(client: TestClient, loaded_fixture: dict) -> None:
    created = client.post(
        "/api/v1/exposure/assets",
        json={"name": "Test depot", "latitude": 8.5, "longitude": 9.1, "category": "facility"},
    )
    assert created.status_code == 201
    asset = created.json()
    assert asset["category"] == "facility"

    screening = client.get(
        "/api/v1/exposure/screen",
        params={
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": "true",
            "radius_km": 50,
        },
    ).json()
    assert screening["asset_count"] == 1
    within = screening["assets"][0]["detections_within_radius"]
    assert 0 < within <= loaded_fixture["inserted"]
    assert screening["assets"][0]["nearest"] is not None
    assert "not a risk score" in screening["note"].lower()

    removed = client.delete(f"/api/v1/exposure/assets/{asset['id']}")
    assert removed.status_code == 204
    assert client.get("/api/v1/exposure/assets").json() == []


def test_exposure_rejects_bad_assets(client: TestClient) -> None:
    assert (
        client.post(
            "/api/v1/exposure/assets", json={"name": "x", "latitude": 120, "longitude": 0}
        ).status_code
        == 422
    )
    assert client.delete("/api/v1/exposure/assets/not-a-uuid").status_code == 404


def test_assistant_answers_from_data(client: TestClient, loaded_fixture: dict) -> None:
    response = client.post(
        "/api/v1/assistant/chat",
        json={
            "question": "how many detections?",
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": True,
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["intent"] == "totals"
    assert body["method"] == "deterministic"
    assert str(loaded_fixture["inserted"]) in body["answer"]
    assert body["data"]["totals"]["detections"] == loaded_fixture["inserted"]


def test_assistant_handles_places_and_unknown_questions(
    client: TestClient, loaded_fixture: dict
) -> None:
    place = client.post(
        "/api/v1/assistant/chat",
        json={
            "question": "how many detections in Nigeria?",
            "start_date": "2026-10-27",
            "end_date": "2026-10-31",
            "synthetic": True,
        },
    ).json()
    assert place["scope"]["place"] == "Nigeria"
    assert place["scope"]["bbox"] is not None

    unknown = client.post("/api/v1/assistant/chat", json={"question": "write me a poem"}).json()
    assert unknown["intent"] == "help"
    assert unknown["capabilities"]
