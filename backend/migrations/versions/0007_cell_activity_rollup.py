"""Cell rollup for the analytics ranking.

Analytics still had one full scan left: the top-activity cells grouped by a 2°
grid index computed from latitude/longitude. This materialized view stores the
2° grid per day, so the ranking reads ~200k rows instead of 11M. Requests with a
bbox or a per-detection FRP floor keep using the live scan.

Revision ID: 0007_cell_activity_rollup
Revises: 0006_daily_activity_rollup
Create Date: 2026-11-01
"""

from __future__ import annotations

from alembic import op

revision = "0007_cell_activity_rollup"
down_revision = "0006_daily_activity_rollup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS cell_activity AS
        SELECT
            CAST((acquired_at AT TIME ZONE 'UTC') AS date) AS day,
            CAST(floor((latitude + 90.0) / 2.0) AS integer) AS lat_index,
            CAST(floor((longitude + 180.0) / 2.0) AS integer) AS lon_index,
            is_synthetic,
            count(*)::bigint AS detections,
            COALESCE(sum(frp_mw), 0) AS frp_sum_mw,
            max(frp_mw) AS frp_max_mw
        FROM fire_observations
        GROUP BY 1, 2, 3, 4
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_cell_activity_key
        ON cell_activity (day, lat_index, lon_index, is_synthetic)
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS cell_activity")
