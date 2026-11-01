"""Watched assets for exposure screening."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class WatchedAsset(UUIDPrimaryKeyMixin, Base):
    """A place the operator cares about; screening measures detection proximity."""

    __tablename__ = "watched_assets"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="unspecified")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_watched_assets_position", "latitude", "longitude"),
        Index("ix_watched_assets_name", "name"),
    )
