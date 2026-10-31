"""The API must fail loudly rather than serve plausible-looking placeholders."""

from __future__ import annotations

from fastapi.testclient import TestClient

#: Routes whose module has not been built yet. Delivered phases (2-5) are
#: exercised in their own test modules instead.
PENDING_ENDPOINTS = [
    "/api/v1/regions",
    "/api/v1/exposure",
    "/api/v1/reports",
]


def test_pending_modules_return_structured_not_implemented(client: TestClient) -> None:
    for path in PENDING_ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 501, path
        error = response.json()["error"]
        assert error["code"] == "not_implemented", path
        assert error["details"]["current_phase"] == "Phase 6", path
        assert error["details"]["planned_for_phase"].startswith("Phase "), path
        assert error["request_id"], path


def test_assistant_chat_is_not_implemented_yet(client: TestClient) -> None:
    response = client.post("/api/v1/assistant/chat")

    assert response.status_code == 501
    assert response.json()["error"]["details"]["module"] == "AI assistant"


def test_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_pending_endpoints_never_leak_sample_measurements(client: TestClient) -> None:
    body = client.get("/api/v1/regions").json()

    assert set(body) == {"error"}
    assert "items" not in body and "features" not in body


def test_observation_routes_are_live_and_empty_not_faked(client: TestClient) -> None:
    response = client.get("/api/v1/fires")

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "limit": 200, "offset": 0}
