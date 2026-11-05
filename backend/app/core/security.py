"""Write-access guard for administration endpoints.

Two credentials are accepted:

* a server-side session cookie (``firewatch_session``) for a user whose role
  permits the action, and
* the break-glass ``X-Admin-Token`` shared secret.

Local development stays frictionless: with no ``ADMIN_TOKEN`` configured and
``ENVIRONMENT`` not ``production``, writes are allowed so a fresh checkout can
ingest without bootstrapping an account. A production deployment must set either
``ADMIN_TOKEN`` or a real admin account; without ``ADMIN_TOKEN`` and without an
admin session the write is refused.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import User
from app.db.session import get_session
from app.services import auth as auth_service


def session_token(request: Request) -> str | None:
    cookie = request.cookies.get(auth_service.SESSION_COOKIE)
    if cookie:
        return cookie
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User | None:
    return auth_service.resolve_session(session, session_token(request))


def _break_glass(token: str | None) -> bool:
    expected = get_settings().admin_token
    return bool(expected and token and hmac.compare_digest(token, expected))


def _local_open() -> bool:
    settings = get_settings()
    return not settings.admin_token and not settings.is_production


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    session: Session = Depends(get_session),
) -> User | None:
    if _break_glass(x_admin_token):
        return None
    user = auth_service.resolve_session(session, session_token(request))
    if user is not None and user.role == "admin":
        return user
    if _local_open():
        return None
    settings = get_settings()
    if settings.is_production and not settings.admin_token:
        raise AppError(
            "unavailable",
            "Set ADMIN_TOKEN or create an administrator account; writes are disabled.",
        )
    raise AppError("unauthorized", "Sign in as an administrator or send X-Admin-Token.")


def require_role(*roles: str) -> Callable[..., User | None]:
    allowed = set(roles)

    def dependency(
        request: Request,
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
        session: Session = Depends(get_session),
    ) -> User | None:
        if _break_glass(x_admin_token):
            return None
        user = auth_service.resolve_session(session, session_token(request))
        if user is not None and user.role in allowed:
            return user
        if _local_open():
            return None
        if get_settings().is_production and not get_settings().admin_token:
            raise AppError(
                "unavailable",
                "No administrator credential is configured; writes are disabled.",
            )
        raise AppError("unauthorized", "Your role does not permit this action.")

    return dependency


#: Analyses: admin and analyst accounts may run them.
require_analyst = require_role("admin", "analyst")
