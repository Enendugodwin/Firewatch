"""Server-side configuration edited through the admin portal.

The NASA FIRMS MAP_KEY is the only credential today. It used to come from the
environment only, which meant a restart to change it. An operator can now set it
in the portal: the value is stored in ``app_settings``, applied to the running
settings object immediately and reloaded on the next start.

The key is never returned. Reads expose whether a key is configured, where it
came from, and a masked fingerprint.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppSetting

FIRMS_KEY = "firms_map_key"
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def get_value(session: Session, key: str) -> str | None:
    row = session.get(AppSetting, key)
    return row.value if row is not None else None


def set_value(session: Session, key: str, value: str) -> AppSetting:
    row = session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


def delete_value(session: Session, key: str) -> bool:
    row = session.get(AppSetting, key)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def mask(secret: str | None) -> str | None:
    if not secret:
        return None
    tail = secret[-4:] if len(secret) >= 4 else ""
    return f"••••••••{tail}"


def validate_firms_key(value: str) -> str:
    key = value.strip()
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError(
            "A FIRMS MAP_KEY is 8–128 letters, digits, dashes or underscores with no spaces."
        )
    return key


def firms_key_state(session: Session, settings: Settings) -> dict[str, Any]:
    stored = get_value(session, FIRMS_KEY)
    env_key = Settings().firms_map_key
    active = settings.firms_map_key
    if stored:
        source = "database"
    elif env_key:
        source = "environment"
    elif active:
        source = "runtime"
    else:
        source = "none"
    row = session.get(AppSetting, FIRMS_KEY)
    return {
        "configured": bool(active),
        "source": source,
        "masked": mask(active),
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
        "hint": (
            "Stored server-side. The browser never receives the key."
            if active
            else "Request a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        ),
    }


def apply_stored_firms_key(session: Session, settings: Settings) -> bool:
    """Load the database override into the process settings (startup)."""
    stored = get_value(session, FIRMS_KEY)
    if not stored:
        return False
    settings.firms_map_key = stored
    return True


def save_firms_key(session: Session, settings: Settings, value: str) -> dict[str, Any]:
    key = validate_firms_key(value)
    set_value(session, FIRMS_KEY, key)
    settings.firms_map_key = key
    return firms_key_state(session, settings)


def clear_firms_key(session: Session, settings: Settings) -> dict[str, Any]:
    delete_value(session, FIRMS_KEY)
    # Fall back to the environment value rather than keeping the old key alive.
    settings.firms_map_key = Settings().firms_map_key
    return firms_key_state(session, settings)
