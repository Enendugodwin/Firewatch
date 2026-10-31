"""Ingestion records: runs, resumable partitions, raw payloads, availability."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JsonType, TimestampMixin, UUIDPrimaryKeyMixin


class IngestionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One retrieval job. Never deleted, so provenance survives re-ingestion."""

    __tablename__ = "ingestion_runs"

    source_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("data_sources.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_received: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    records_rejected: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    query_parameters: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source = relationship("DataSource", lazy="joined")

    __table_args__ = (Index("ix_ingestion_runs_started_at", "started_at"),)


class IngestionPartition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A (source, tile, date window) unit of work, so backfills resume safely."""

    __tablename__ = "ingestion_partitions"

    source_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("data_sources.id"))
    tile_key: Mapped[str] = mapped_column(String(64), nullable=False)
    bbox: Mapped[str] = mapped_column(String(64), nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    records_received: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "source_id", "tile_key", "date_start", name="uq_ingestion_partitions_window"
        ),
    )


class RawObservation(UUIDPrimaryKeyMixin, Base):
    """Immutable source payload, retained for provenance and reproducibility."""

    __tablename__ = "raw_observations"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("data_sources.id"))
    source_record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_raw_observations_source_record"),
    )


class SourceAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which dates a source actually observed, so gaps are never read as zero."""

    __tablename__ = "source_availability"

    source_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("data_sources.id"))
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="available")
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source_id", "observation_date", name="uq_source_availability_date"),
    )
