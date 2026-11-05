"""Argon2id accounts, sessions and role checks."""

from __future__ import annotations

from app.core.config import get_settings
from app.db.session import session_scope
from app.services import auth as auth_service


def _make_user(email: str, role: str) -> None:
    with session_scope() as session:
        auth_service.create_user(
            session,
            email=email,
            password="correct-horse-battery",
            display_name=email.split("@")[0],
            role=role,
        )


def _login(client, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 200, response.text


def test_argon2id_hash_and_login_session(client) -> None:
    client.cookies.clear()
    _make_user("admin@example.com", "admin")

    with session_scope() as session:
        from sqlalchemy import select

        from app.db.models import User

        user = session.scalars(select(User).where(User.email == "admin@example.com")).one()
        assert user.password_hash.startswith("$argon2id$")
        assert auth_service.verify_password(user.password_hash, "correct-horse-battery")
        assert not auth_service.verify_password(user.password_hash, "wrong")

    _login(client, "admin@example.com")
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    status = client.get("/api/v1/auth/status")
    assert status.json()["authenticated"] is True

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_analyst_cannot_use_admin_endpoints(client) -> None:
    client.cookies.clear()
    settings = get_settings()
    original = settings.admin_token
    settings.admin_token = "break-glass-token"
    _make_user("analyst@example.com", "analyst")
    _make_user("admin2@example.com", "admin")
    try:
        _login(client, "analyst@example.com")
        assert client.get("/api/v1/admin/raw/inventory").status_code == 401

        client.post("/api/v1/auth/logout")
        _login(client, "admin2@example.com")
        assert client.get("/api/v1/admin/raw/inventory").status_code == 200

        users = client.get("/api/v1/auth/users")
        assert users.status_code == 200
        assert {row["email"] for row in users.json()} >= {"admin2@example.com"}
    finally:
        settings.admin_token = original


def test_break_glass_token_still_works(client) -> None:
    client.cookies.clear()
    settings = get_settings()
    original = settings.admin_token
    settings.admin_token = "break-glass-token"
    try:
        without = client.get("/api/v1/admin/raw/inventory")
        assert without.status_code == 401
        with_token = client.get(
            "/api/v1/admin/raw/inventory",
            headers={"X-Admin-Token": "break-glass-token"},
        )
        assert with_token.status_code == 200
    finally:
        settings.admin_token = original
