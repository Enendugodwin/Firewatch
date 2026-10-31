"""Phase 2 + 3 schema: observations, ingestion provenance, harmonization.

Revision ID: 0002_observations
Revises: 0001_foundation
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import GUID, JsonType

revision = "0002_observations"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("source_id", GUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("records_received", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("query_parameters", JsonType, nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])

    op.create_table(
        "ingestion_partitions",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("source_id", GUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("tile_key", sa.String(length=64), nullable=False),
        sa.Column("bbox", sa.String(length=64), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("records_received", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_id", "tile_key", "date_start", name="uq_ingestion_partitions_window"
        ),
    )

    op.create_table(
        "raw_observations",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("run_id", GUID(), sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL")),
        sa.Column("source_id", GUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_record_id", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", JsonType, nullable=False),
        sa.Column(
            "retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint(
            "source_id", "source_record_id", name="uq_raw_observations_source_record"
        ),
    )

    op.create_table(
        "source_availability",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("source_id", GUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_id", "observation_date", name="uq_source_availability_date"),
    )

    op.create_table(
        "fire_observations",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("source_id", GUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_code", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", GUID(), sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL")),
        sa.Column("sensor", sa.String(length=16), nullable=False),
        sa.Column("satellite", sa.String(length=32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence_raw", sa.Integer()),
        sa.Column("confidence_category", sa.String(length=16)),
        sa.Column("brightness_temperature", sa.Float()),
        sa.Column("brightness_channel", sa.String(length=24)),
        sa.Column("frp_mw", sa.Float()),
        sa.Column("scan_km", sa.Float()),
        sa.Column("track_km", sa.Float()),
        sa.Column("daynight", sa.String(length=1)),
        sa.Column("processing_version", sa.String(length=32)),
        sa.Column("source_product", sa.String(length=32), nullable=False),
        sa.Column("source_payload", JsonType, nullable=False),
        sa.Column("quality_flags", JsonType, nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint(
            "source_id", "source_record_id", name="uq_fire_observations_source_record"
        ),
    )
    op.create_index("ix_fire_observations_acquired_at", "fire_observations", ["acquired_at"])
    op.create_index(
        "ix_fire_observations_sensor_acquired", "fire_observations", ["sensor", "acquired_at"]
    )
    op.create_index("ix_fire_observations_position", "fire_observations", ["latitude", "longitude"])
    op.create_index("ix_fire_observations_synthetic", "fire_observations", ["is_synthetic"])

    op.create_table(
        "algorithm_runs",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("parameters", JsonType, nullable=False),
        sa.Column("stats", JsonType, nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_algorithm_runs_kind_started", "algorithm_runs", ["kind", "started_at"])

    op.create_table(
        "observation_matches",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "observation_a_id",
            GUID(),
            sa.ForeignKey("fire_observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_b_id",
            GUID(),
            sa.ForeignKey("fire_observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("temporal_delta_seconds", sa.Integer(), nullable=False),
        sa.Column("spatial_distance_m", sa.Float(), nullable=False),
        sa.Column("footprint_overlap", sa.Float()),
        sa.Column("association_score", sa.Float(), nullable=False),
        sa.Column("match_status", sa.String(length=16), nullable=False),
        sa.Column("components", JsonType, nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "observation_a_id", "observation_b_id", name="uq_observation_matches_pair"
        ),
    )
    op.create_index("ix_observation_matches_status", "observation_matches", ["match_status"])
    op.create_index("ix_observation_matches_score", "observation_matches", ["association_score"])

    op.create_table(
        "fire_events",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("centroid_latitude", sa.Float(), nullable=False),
        sa.Column("centroid_longitude", sa.Float(), nullable=False),
        sa.Column("min_latitude", sa.Float(), nullable=False),
        sa.Column("max_latitude", sa.Float(), nullable=False),
        sa.Column("min_longitude", sa.Float(), nullable=False),
        sa.Column("max_longitude", sa.Float(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("sensor_count", sa.Integer(), nullable=False),
        sa.Column("maximum_frp_mw", sa.Float()),
        sa.Column("aggregate_frp_mw", sa.Float()),
        sa.Column("clustering_method", sa.String(length=32), nullable=False),
        sa.Column("clustering_parameters", JsonType, nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("run_id", GUID(), sa.ForeignKey("algorithm_runs.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "event_observations",
        sa.Column(
            "event_id",
            GUID(),
            sa.ForeignKey("fire_events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "observation_id",
            GUID(),
            sa.ForeignKey("fire_observations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("event_observations")
    op.drop_table("fire_events")
    op.drop_index("ix_observation_matches_score", table_name="observation_matches")
    op.drop_index("ix_observation_matches_status", table_name="observation_matches")
    op.drop_table("observation_matches")
    op.drop_index("ix_algorithm_runs_kind_started", table_name="algorithm_runs")
    op.drop_table("algorithm_runs")
    op.drop_index("ix_fire_observations_synthetic", table_name="fire_observations")
    op.drop_index("ix_fire_observations_position", table_name="fire_observations")
    op.drop_index("ix_fire_observations_sensor_acquired", table_name="fire_observations")
    op.drop_index("ix_fire_observations_acquired_at", table_name="fire_observations")
    op.drop_table("fire_observations")
    op.drop_table("source_availability")
    op.drop_table("raw_observations")
    op.drop_table("ingestion_partitions")
    op.drop_index("ix_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
