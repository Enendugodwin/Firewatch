"""AI intelligence assistant (implemented in Phase 7)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import not_implemented

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", summary="Ask an analytical question")
def assistant_chat() -> None:
    raise not_implemented("AI assistant", "Phase 1", planned_for="Phase 7")
