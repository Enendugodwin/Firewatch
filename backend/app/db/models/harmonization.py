"""Cross-sensor associations, estimated events and algorithm runs."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JsonType, TimestampMixin, UUIDPrimaryKeyMixin


class ObservationMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A scored association between two observations from different sensor families.

    The score is an association score, not the probability that the detections
    are the same physical fire. All components are stored so a user can inspect
    why the match was produced.
    """

    __tablename__ = "observation_matches"

    observation_a_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fire_observations.id", ondelete="CASCADE"), nullable=False
    )
    observation_b_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fire_observations.id", ondelete="CASCADE"), nullable=False
    )
    temporal_delta_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    spatial_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    footprint_overlap: Mapped[float | None] = mapped_column(Float)
    association_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_status: Mapped[str] = mapped_column(String(16), nullable=False)
    #: UTC day of the MODIS (observation A) side; denormalised for period queries.
    match_day: Mapped[date] = mapped_column(Date, nullable=False)
    components: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)

    observation_a = relationship("FireObservation", foreign_keys=[observation_a_id], lazy="joined")
    observation_b = relationship("FireObservation", foreign_keys=[observation_b_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "observation_a_id", "observation_b_id", name="uq_observation_matches_pair"
        ),
        Index("ix_observation_matches_status", "match_status"),
        Index("ix_observation_matches_score", "association_score"),
        Index("ix_observation_matches_day", "match_day", "match_status"),
    )


class HarmonizationCoverage(Base):
    """Which UTC days a harmonisation scope has actually processed.

    The association engine can run over decades of observations in bounded,
    resumable daily chunks. This table is the checkpoint: a day present here was
    scanned for that scope, so ``harmonized == raw`` on a missing day means "not
    processed", not "no duplicates found".
    """

    __tablename__ = "harmonization_coverage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    observations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pairs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    probable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    possible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_harmonization_coverage_scope_day", "scope", "day"),
    )


class FireEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An estimated event from spatiotemporal clustering — never a confirmed fire."""

    __tablename__ = "fire_events"

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    centroid_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    min_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    max_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    min_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    max_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sensor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_frp_mw: Mapped[float | None] = mapped_column(Float)
    aggregate_frp_mw: Mapped[float | None] = mapped_column(Float)
    clustering_method: Mapped[str] = mapped_column(String(32), nullable=False)
    clustering_parameters: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("algorithm_runs.id", ondelete="SET NULL")
    )

    observations = relationship(
        "FireObservation", secondary="event_observations", lazy="selectin", viewonly=True
    )


class EventObservation(Base):
    """Many-to-many: which observations make up an estimated event."""

    __tablename__ = "event_observations"

    event_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fire_events.id", ondelete="CASCADE"), primary_key=True
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fire_observations.id", ondelete="CASCADE"), primary_key=True
    )


class AlgorithmRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit trail for harmonization and event-grouping passes."""

    __tablename__ = "algorithm_runs"

    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    stats: Mapped[dict] = mapped_column(JsonType, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_algorithm_runs_kind_started", "kind", "started_at"),)
