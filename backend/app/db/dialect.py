"""Dialect-aware SQL helpers.

The same analytical queries run on SQLite (development) and PostgreSQL
(production). Two functions differ meaningfully between them and are isolated
here so call sites cannot drift:

* ``CAST(numeric AS integer)`` truncates in SQLite but **rounds** in PostgreSQL.
* ``date(timestamptz)`` is timezone-dependent in PostgreSQL, so UTC is applied
  explicitly to avoid a day boundary that depends on the server's time zone.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, cast, func, literal_column
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement


def dialect_name(session: Session) -> str:
    bind = session.get_bind()
    return bind.dialect.name if bind is not None else "sqlite"


def utc_day(column: Any, dialect: str) -> ColumnElement[Any]:
    """The UTC calendar day of a timestamp column, as a date in both dialects."""
    if dialect == "postgresql":
        # A literal, not a bind parameter: PostgreSQL requires GROUP BY
        # expressions to match the SELECT expression exactly.
        return func.date(func.timezone(literal_column("'UTC'"), column))
    return func.date(column)


def grid_index(column: Any, offset: float, cell: float, dialect: str) -> ColumnElement[Any]:
    """
    Truncated grid index of a coordinate. Inputs are shifted to be non-negative,
    so truncation and floor agree; PostgreSQL needs the explicit floor because a
    plain cast would round instead.
    """
    expression = (column + offset) / cell
    if dialect == "postgresql":
        return cast(func.floor(expression), Integer)
    return cast(expression, Integer)
