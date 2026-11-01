"""The API must fail loudly rather than serve plausible-looking placeholders.

Every module is delivered now, so this file guards the opposite contract: the
endpoints answer with real shapes, and nothing returns a fabricated row.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_every_module_endpoint_answers(client: TestClient) -> None:
    for path in (
        "/api/v1/regions?start_date=2026-10-27&end_date=2026-10-31",
        "/api/v1/exposure",
        "/api/v1/reports",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.json()
        assert "error" not in body, path


def test_assistant_is_deterministic_and_says_so(client: TestClient) -> None:
    response = client.post("/api/v1/assistant/chat", json={"question": "how many detections"})

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "deterministic"
    assert body["intent"] == "totals"
    assert body["capabilities"]


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_empty_database_is_reported_not_invented(client: TestClient) -> None:
    body = client.get("/api/v1/regions?start_date=2026-10-27&end_date=2026-10-31").json()

    assert all(region["detections"] == 0 for region in body["regions"])
    assert body["note"]


def test_observation_routes_are_live_and_empty_not_faked(client: TestClient) -> None:
    response = client.get("/api/v1/fires")

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "limit": 200, "offset": 0}
