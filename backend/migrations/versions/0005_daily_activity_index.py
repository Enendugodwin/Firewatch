"""Covering index for the daily activity aggregation.

Analytics, the calendar, the anomaly engine and reports all group by UTC day and
summarise sensor, confidence and FRP. On a ten-million-row table that was a 15 s
heap scan per call. An index on the day expression with the aggregated columns
appended lets PostgreSQL answer it with an index-only scan.

PostgreSQL only: SQLite ignores the expression index, and the query planner does
not use one for this shape.

Revision ID: 0005_daily_activity_index
Revises: 0004_watched_assets
Create Date: 2026-11-01
"""

from __future__ import annotations

from alembic import op

revision = "0005_daily_activity_index"
down_revision = "0004_watched_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_fire_observations_daily_cover
        ON fire_observations (
            (CAST((acquired_at AT TIME ZONE 'UTC') AS date)),
            sensor,
            confidence_category,
            daynight,
            satellite,
            source_code
        )
        INCLUDE (frp_mw)
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_fire_observations_daily_cover")
