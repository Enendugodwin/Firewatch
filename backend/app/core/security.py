"""Write-access guard for administration endpoints.

Local development stays frictionless: with no ``ADMIN_TOKEN`` configured the
dependency allows the request. A cloud deployment **must** set the token; in
``ENVIRONMENT=production`` an unset token disables writes rather than exposing
ingestion and deletion endpoints to the internet.
"""

from __future__ import annotations

import hmac

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import AppError


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings = get_settings()
    expected = settings.admin_token
    if not expected:
        if settings.environment == "production":
            raise AppError(
                "unavailable",
                "ADMIN_TOKEN is not configured; administrative writes are disabled.",
            )
        return
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise AppError("unauthorized", "A valid X-Admin-Token header is required.")
