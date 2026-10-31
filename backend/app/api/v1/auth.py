"""Authentication (implemented in Phase 8 hardening)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", summary="Authenticate a user")
def login() -> None:
    raise not_implemented("Authentication", planned_for="Phase 8")
