"""Liveness and readiness behaviour."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_is_live_without_touching_the_database(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "FIREWATCH X"


def test_ready_reports_database_connectivity(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"]["connected"] is True
    assert body["database"]["dialect"] == "sqlite"


def test_requests_carry_correlation_and_security_headers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_incoming_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"
