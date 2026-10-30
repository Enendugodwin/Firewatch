"""Registered satellite products (NASA FIRMS sources).

Phase 1 ships the registry only: no observations are stored yet, and the API
reports every source as ``not_ingested`` rather than implying live data.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_sources"

    source_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    sensor: Mapped[str] = mapped_column(String(16), nullable=False)
    satellite: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_level: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<DataSource {self.source_code}>"


__all__ = ["DataSource"]
