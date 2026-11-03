"""Range refresh must be a safe no-op where no rollup table exists (SQLite)."""

from __future__ import annotations

from datetime import date

import pytest

from app.db.session import session_scope
from app.services.rollups import refresh_rollup_range


def test_range_refresh_is_a_noop_without_a_rollup() -> None:
    with session_scope() as session:
        assert refresh_rollup_range(session, date(2020, 1, 1), date(2020, 1, 5)) is False


def test_range_refresh_rejects_an_inverted_range() -> None:
    with session_scope() as session, pytest.raises(ValueError):
        refresh_rollup_range(session, date(2020, 1, 5), date(2020, 1, 1))
