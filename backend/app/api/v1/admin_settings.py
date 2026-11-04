"""Admin-portal settings: the NASA FIRMS MAP_KEY.

The key is write-only from the browser's point of view: it is accepted, stored
server-side and applied immediately, but reads only return a masked fingerprint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import require_admin
from app.db.session import get_session
from app.services import app_settings
from app.services.firms.client import FirmsError
from app.services.ingestion import build_client

router = APIRouter(
    prefix="/admin/settings", tags=["admin"], dependencies=[Depends(require_admin)]
)


class FirmsKeyIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=128)


@router.get("/firms", summary="FIRMS key status (masked)")
def firms_status(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return app_settings.firms_key_state(session, settings)


@router.put("/firms", summary="Store a FIRMS MAP_KEY")
def save_firms_key(
    payload: FirmsKeyIn,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return app_settings.save_firms_key(session, settings, payload.api_key)
    except ValueError as exc:
        raise AppError("unprocessable", str(exc)) from exc


@router.delete("/firms", summary="Remove the stored key and fall back to the environment")
def clear_firms_key(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return app_settings.clear_firms_key(session, settings)


@router.post("/firms/test", summary="Ask FIRMS whether the active key works")
def test_firms_key(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not settings.firms_configured:
        raise AppError("unprocessable", "No FIRMS key is configured.")
    client = build_client()
    try:
        window = client.fetch_availability("MODIS_NRT")
    except FirmsError as exc:
        raise AppError("unavailable", f"FIRMS rejected the key or is unreachable: {exc}") from exc
    return {
        "ok": True,
        "source_code": window.source_code,
        "min_date": window.min_date.isoformat() if window.min_date else None,
        "max_date": window.max_date.isoformat() if window.max_date else None,
    }
