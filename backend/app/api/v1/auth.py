"""Authentication and role-based access control."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import current_user, require_admin, session_token
from app.db.models import User
from app.db.session import get_session
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=256)
    display_name: str = Field(default="", max_length=120)
    role: str = Field(default="viewer", pattern="^(admin|analyst|viewer)$")


class UserPatch(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|analyst|viewer)$")
    is_active: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=10, max_length=256)


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        auth_service.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


@router.get("/status", summary="Whether sign-in is available and who is signed in")
def auth_status(
    request: Request, session: Session = Depends(get_session)
) -> dict[str, Any]:
    user = auth_service.resolve_session(session, session_token(request))
    settings = get_settings()
    return {
        "authentication": True,
        "authenticated": user is not None,
        "required": bool(settings.is_production and not settings.admin_token),
        "open_access": bool(not settings.admin_token and not settings.is_production),
        "user": auth_service.user_out(user) if user else None,
        "roles": list(auth_service.ROLES),
        "method": "argon2id + server-side session cookie",
    }


@router.post("/login", summary="Sign in with an operator account")
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    user = auth_service.authenticate(
        session, email=payload.email, password=payload.password
    )
    if user is None:
        raise AppError("unauthorized", "Email or password is incorrect.")
    token, record = auth_service.create_session(
        session, user, ttl_hours=get_settings().session_ttl_hours
    )
    _set_cookie(response, token)
    return {
        "user": auth_service.user_out(user),
        "expires_at": record.expires_at.isoformat(),
    }


@router.post("/logout", summary="Revoke the current session")
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
) -> dict[str, bool]:
    auth_service.revoke_session(session, session_token(request))
    response.delete_cookie(auth_service.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me", summary="Current operator")
def me(user: User | None = Depends(current_user)) -> dict[str, Any]:
    if user is None:
        raise AppError("unauthorized", "Not signed in.")
    return auth_service.user_out(user)


@router.get("/users", summary="List operator accounts")
def list_users(
    session: Session = Depends(get_session),
    _: User | None = Depends(require_admin),
) -> list[dict[str, Any]]:
    users = session.scalars(select(User).order_by(User.email)).all()
    return [auth_service.user_out(user) for user in users]


@router.post("/users", status_code=201, summary="Create an operator account")
def add_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _: User | None = Depends(require_admin),
) -> dict[str, Any]:
    try:
        user = auth_service.create_user(
            session,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
        )
    except ValueError as exc:
        raise AppError("unprocessable", str(exc)) from exc
    return auth_service.user_out(user)


@router.patch("/users/{user_id}", summary="Change a role or deactivate an account")
def patch_user(
    user_id: uuid.UUID,
    payload: UserPatch,
    session: Session = Depends(get_session),
    actor: User | None = Depends(require_admin),
) -> dict[str, Any]:
    user = session.get(User, user_id)
    if user is None:
        raise AppError("not_found", "No user with that identifier.")
    if user.role == "admin" and payload.role and payload.role != "admin":
        admins = session.scalars(select(User).where(User.role == "admin", User.is_active)).all()
        if len(admins) <= 1:
            raise AppError("conflict", "At least one active administrator must remain.")
    if actor is not None and actor.id == user.id and payload.is_active is False:
        raise AppError("conflict", "You cannot deactivate your own account.")
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            auth_service.revoke_all_for_user(session, user.id)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.password is not None:
        user.password_hash = auth_service.hash_password(payload.password)
        auth_service.revoke_all_for_user(session, user.id)
    session.commit()
    session.refresh(user)
    return auth_service.user_out(user)
