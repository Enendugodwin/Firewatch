"""Regional intelligence tables.

Stores selectable boundaries (GeoJSON, since PostGIS is absent), the materialised
region × day × sensor statistics, and the recurring-activity grid. The statistics
tables are what every read endpoint serves, so opening a region never scans the
observation table.

Revision ID: 0008_regional_intelligence
Revises: 0007_cell_activity_rollup
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import GUID

JsonColumn = sa.JSON().with_variant(JSONB(), "postgresql")

revision = "0008_regional_intelligence"
down_revision = "0007_cell_activity_rollup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geographic_regions",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False, server_default="custom"),
        sa.Column("boundary_kind", sa.String(length=16), nullable=False, server_default="polygon"),
        sa.Column("geometry", JsonColumn, nullable=False),
        sa.Column("bbox_west", sa.Float(), nullable=False),
        sa.Column("bbox_south", sa.Float(), nullable=False),
        sa.Column("bbox_east", sa.Float(), nullable=False),
        sa.Column("bbox_north", sa.Float(), nullable=False),
        sa.Column("area_km2", sa.Float(), nullable=True),
        sa.Column("vertices", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "boundary_version", sa.String(length=32), nullable=False, server_default="v1"
        ),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="custom"),
        sa.Column(
            "is_approximate", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_analysis_algorithm", sa.String(length=48), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_geographic_regions_level", "geographic_regions", ["level"])
    op.create_index("ix_geographic_regions_name", "geographic_regions", ["name"])

    op.create_table(
        "regional_daily_statistics",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "region_id",
            GUID(),
            sa.ForeignKey("geographic_regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("sensor", sa.String(length=16), nullable=False),
        sa.Column("detection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frp_sum_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column("frp_max_mw", sa.Float(), nullable=True),
        sa.Column(
            "high_confidence_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("coverage", JsonColumn, nullable=True),
        sa.Column("algorithm_version", sa.String(length=48), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "region_id", "activity_date", "sensor", name="uq_regional_daily_region_day_sensor"
        ),
    )
    op.create_index(
        "ix_regional_daily_region_date", "regional_daily_statistics", ["region_id", "activity_date"]
    )

    op.create_table(
        "regional_cell_statistics",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column(
            "region_id",
            GUID(),
            sa.ForeignKey("geographic_regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lat_index", sa.Integer(), nullable=False),
        sa.Column("lon_index", sa.Integer(), nullable=False),
        sa.Column("detection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frp_sum_mw", sa.Float(), nullable=False, server_default="0"),
        sa.Column("frp_max_mw", sa.Float(), nullable=True),
        sa.Column(
            "years_with_detections", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("first_year", sa.Integer(), nullable=True),
        sa.Column("last_year", sa.Integer(), nullable=True),
        sa.Column("algorithm_version", sa.String(length=48), nullable=False),
        sa.UniqueConstraint(
            "region_id", "lat_index", "lon_index", name="uq_regional_cell_region_cell"
        ),
    )
    op.create_index("ix_regional_cell_region", "regional_cell_statistics", ["region_id"])

    # The latitude/longitude prefilter index already exists from migration 0002
    # (``ix_fire_observations_position``); regional analysis reuses it.


def downgrade() -> None:
    op.drop_index("ix_regional_cell_region", table_name="regional_cell_statistics")
    op.drop_table("regional_cell_statistics")
    op.drop_index("ix_regional_daily_region_date", table_name="regional_daily_statistics")
    op.drop_table("regional_daily_statistics")
    op.drop_index("ix_geographic_regions_name", table_name="geographic_regions")
    op.drop_index("ix_geographic_regions_level", table_name="geographic_regions")
    op.drop_table("geographic_regions")
