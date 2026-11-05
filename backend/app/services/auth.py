"""Argon2id passwords, roles and opaque server-side sessions.

The raw session token is returned to the client once and stored in an HttpOnly
cookie. Only its SHA-256 hash is persisted, so a database read cannot impersonate
a signed-in operator. Sessions expire and can be revoked individually.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, User

SESSION_COOKIE = "firewatch_session"
ROLES = ("admin", "analyst", "viewer")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

#: Argon2id with the library defaults (3 iterations, 64 MiB, 4 lanes).
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Passwords must be at least 10 characters.")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def create_user(
    session: Session, *, email: str, password: str, display_name: str, role: str = "viewer"
) -> User:
    email = normalize_email(email)
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    existing = session.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise ValueError("A user with that email already exists.")
    user = User(
        email=email,
        display_name=display_name.strip() or email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, *, email: str, password: str) -> User | None:
    user = session.scalars(
        select(User).where(User.email == email.strip().lower())
    ).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def create_session(session: Session, user: User, *, ttl_hours: int = 12) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    record = AuthSession(
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=max(1, ttl_hours)),
    )
    session.add(record)
    session.commit()
    return token, record


def resolve_session(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    record = session.scalars(
        select(AuthSession).where(AuthSession.token_hash == digest)
    ).first()
    if record is None:
        return None
    if record.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        session.delete(record)
        session.commit()
        return None
    user = record.user
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(session: Session, token: str | None) -> None:
    if not token:
        return
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    record = session.scalars(
        select(AuthSession).where(AuthSession.token_hash == digest)
    ).first()
    if record is not None:
        session.delete(record)
        session.commit()


def revoke_all_for_user(session: Session, user_id: Any) -> int:
    rows = session.scalars(select(AuthSession).where(AuthSession.user_id == user_id)).all()
    for row in rows:
        session.delete(row)
    session.commit()
    return len(rows)


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
