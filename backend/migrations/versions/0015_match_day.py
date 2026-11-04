"""Denormalize the association day onto ``observation_matches``.

Period-scoped Sensor Intelligence queries used to join every match to its MODIS
observation just to read a date, which cost ~1.4 s for a week. The MODIS side's
UTC day is immutable, so it is stored once at insert and indexed with the status.
Old rows are backfilled from their observation.

Revision ID: 0015_match_day
Revises: 0014_harmonized_cell_rollup
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op

revision = "0015_match_day"
down_revision = "0014_harmonized_cell_rollup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("ALTER TABLE observation_matches ADD COLUMN match_day DATE")
    if bind.dialect.name == "postgresql":
        op.execute("SET LOCAL statement_timeout = 0")
        op.execute(
            """
            UPDATE observation_matches m
            SET match_day = (
                SELECT CAST((f.acquired_at AT TIME ZONE 'UTC') AS date)
                FROM fire_observations f
                WHERE f.id = m.observation_a_id
            )
            WHERE m.match_day IS NULL
            """
        )
        op.execute("ALTER TABLE observation_matches ALTER COLUMN match_day SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_observation_matches_day "
        "ON observation_matches (match_day, match_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_observation_matches_day")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE observation_matches DROP COLUMN IF EXISTS match_day")
