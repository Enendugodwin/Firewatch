"""Materialized daily activity rollup for PostgreSQL.

The calendar, analytics and anomaly engine all aggregate by UTC day. On eleven
million observations that is a ~20 s full scan per request; this rollup answers
those views from a few thousand rows instead. Requests that need row-level
filters (a bbox or a per-detection FRP floor) still scan the table, and the
service layer chooses between the two explicitly.

Revision ID: 0006_daily_activity_rollup
Revises: 0005_daily_activity_index
Create Date: 2026-11-01
"""

from __future__ import annotations

from alembic import op

revision = "0006_daily_activity_rollup"
down_revision = "0005_daily_activity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS daily_activity AS
        SELECT
            CAST((acquired_at AT TIME ZONE 'UTC') AS date) AS day,
            sensor,
            COALESCE(confidence_category, 'unknown') AS confidence_category,
            COALESCE(daynight, '') AS daynight,
            satellite,
            source_code,
            is_synthetic,
            count(*)::bigint AS detections,
            COALESCE(sum(frp_mw), 0) AS frp_sum_mw,
            max(frp_mw) AS frp_max_mw
        FROM fire_observations
        GROUP BY 1, 2, 3, 4, 5, 6, 7
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_activity_key
        ON daily_activity (
            day, sensor, confidence_category, daynight, satellite, source_code, is_synthetic
        )
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_activity")
