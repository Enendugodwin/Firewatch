"""Foundation: spatial extension and the data-source registry.

Phase 1 creates only what exists: the PostGIS extension (PostgreSQL only) and the
`data_sources` catalogue. Satellite observation tables are deliberately deferred
to Phase 2, where their partitioning and index strategy is decided against real
measured volumes instead of guesses.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import GUID

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if _is_postgres():
        # PostGIS is required for every spatial query in later phases.
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "data_sources",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("source_code", sa.String(length=32), nullable=False),
        sa.Column("sensor", sa.String(length=16), nullable=False),
        sa.Column("satellite", sa.String(length=32), nullable=False),
        sa.Column("processing_level", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_code", name="uq_data_sources_source_code"),
    )
    op.create_index("ix_data_sources_processing_level", "data_sources", ["processing_level"])
    # Keeps queries on the PostgreSQL data_sources table cheap regardless of size.
    _ = bind


def downgrade() -> None:
    op.drop_index("ix_data_sources_processing_level", table_name="data_sources")
    op.drop_table("data_sources")
