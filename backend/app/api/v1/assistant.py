"""Deterministic intelligence assistant."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_session
from app.services.assistant import CAPABILITIES, answer, default_window

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    synthetic: bool | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    scope: dict[str, object]
    data: dict[str, object]
    method: str
    capabilities: list[str]
    notes: list[str]


@router.post("/chat", response_model=ChatResponse, summary="Ask an analytical question")
def assistant_chat(payload: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    start, end = default_window(payload.start_date, payload.end_date)
    if start > end:
        raise AppError(
            "bad_request",
            "start_date must be on or before end_date.",
            details={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
    return ChatResponse(
        **answer(
            session,
            question=payload.question,
            start=start,
            end=end,
            synthetic=payload.synthetic,
        )
    )


@router.get("/capabilities", summary="Questions this assistant can answer")
def capabilities() -> dict[str, object]:
    return {
        "method": "deterministic",
        "capabilities": CAPABILITIES,
        "note": "No language model is used; answers are computed from the database.",
    }
