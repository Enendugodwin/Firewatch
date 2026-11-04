"""Administrative write guard: local open, cloud closed unless a token is set."""

from __future__ import annotations

from app.core.config import get_settings

TOKEN = "test-admin-token"


def test_admin_endpoints_require_the_configured_token(client) -> None:
    settings = get_settings()
    original = settings.admin_token
    settings.admin_token = TOKEN
    try:
        assert client.get("/api/v1/admin/raw/inventory").status_code == 401

        authorized = client.get(
            "/api/v1/admin/raw/inventory", headers={"X-Admin-Token": TOKEN}
        )
        assert authorized.status_code == 200

        assert client.put(
            "/api/v1/admin/settings/firms", json={"api_key": "abcdef0123456789"}
        ).status_code == 401
        assert client.post("/api/v1/harmonization/run", json={}).status_code == 401
    finally:
        settings.admin_token = original


def test_production_without_a_token_disables_writes(client) -> None:
    settings = get_settings()
    original_token, original_env = settings.admin_token, settings.environment
    settings.admin_token = None
    settings.environment = "production"
    try:
        response = client.get("/api/v1/admin/raw/inventory")
        assert response.status_code == 503
        assert "ADMIN_TOKEN" in response.json()["error"]["message"]
    finally:
        settings.admin_token = original_token
        settings.environment = original_env
