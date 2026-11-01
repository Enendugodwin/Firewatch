"""Watched assets for exposure screening.

Revision ID: 0004_watched_assets
Revises: 0003_availability_status_width
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import GUID

revision = "0004_watched_assets"
down_revision = "0003_availability_status_width"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watched_assets",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False, server_default="unspecified"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_watched_assets_position", "watched_assets", ["latitude", "longitude"])
    op.create_index("ix_watched_assets_name", "watched_assets", ["name"])


def downgrade() -> None:
    op.drop_index("ix_watched_assets_name", table_name="watched_assets")
    op.drop_index("ix_watched_assets_position", table_name="watched_assets")
    op.drop_table("watched_assets")
