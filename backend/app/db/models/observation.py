"""Canonical fire observations — the primary analytical table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JsonType, UUIDPrimaryKeyMixin


class FireObservation(UUIDPrimaryKeyMixin, Base):
    """
    One satellite thermal detection, normalised into a common shape while every
    original measurement is preserved.

    Raw values are never overwritten by derived fields: ``confidence_raw`` and
    ``confidence_category`` keep source semantics, and any harmonised quality
    class lives in ``quality_flags`` (clearly labelled as an interpretation).
    """

    __tablename__ = "fire_observations"

    source_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("data_sources.id"))
    source_code: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )

    sensor: Mapped[str] = mapped_column(String(16), nullable=False)
    satellite: Mapped[str] = mapped_column(String(32), nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    confidence_raw: Mapped[int | None] = mapped_column(Integer)
    confidence_category: Mapped[str | None] = mapped_column(String(16))
    brightness_temperature: Mapped[float | None] = mapped_column(Float)
    brightness_channel: Mapped[str | None] = mapped_column(String(24))
    frp_mw: Mapped[float | None] = mapped_column(Float)
    scan_km: Mapped[float | None] = mapped_column(Float)
    track_km: Mapped[float | None] = mapped_column(Float)
    daynight: Mapped[str | None] = mapped_column(String(1))

    processing_version: Mapped[str | None] = mapped_column(String(32))
    source_product: Mapped[str] = mapped_column(String(32), nullable=False)
    source_payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    quality_flags: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: True only for labelled fixtures loaded by scripts/ingest_fixture.py.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source = relationship("DataSource", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "source_id", "source_record_id", name="uq_fire_observations_source_record"
        ),
        Index("ix_fire_observations_acquired_at", "acquired_at"),
        Index("ix_fire_observations_sensor_acquired", "sensor", "acquired_at"),
        Index("ix_fire_observations_position", "latitude", "longitude"),
        Index("ix_fire_observations_synthetic", "is_synthetic"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<FireObservation {self.source_code} {self.acquired_at:%Y-%m-%d %H:%M}>"
