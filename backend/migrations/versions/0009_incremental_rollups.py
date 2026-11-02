"""Incremental rollups as tables, with sensor on the cell rollup.

Two problems with materialized views:

* ``REFRESH MATERIALIZED VIEW`` rebuilds the whole 11 M-row aggregate after an
  ingestion, even when one day was added;
* the cell rollup has no sensor dimension, so the map cannot honour a sensor
  filter without falling back to a full scan.

This migration replaces both views with ordinary tables. The daily shape is
unchanged; the cell table gains ``sensor``. ``refresh_rollup(since=...)`` then
recomputes only the affected days.

Revision ID: 0009_incremental_rollups
Revises: 0008_regional_intelligence
Create Date: 2026-11-02
"""

from __future__ import annotations

from alembic import op

revision = "0009_incremental_rollups"
down_revision = "0008_regional_intelligence"
branch_labels = None
depends_on = None


DAILY_DDL = """
CREATE TABLE IF NOT EXISTS daily_activity (
    day DATE NOT NULL,
    sensor VARCHAR(16) NOT NULL,
    confidence_category VARCHAR(16),
    daynight VARCHAR(1),
    satellite VARCHAR(32),
    source_code VARCHAR(32),
    is_synthetic BOOLEAN NOT NULL,
    detections BIGINT NOT NULL,
    frp_sum_mw DOUBLE PRECISION NOT NULL,
    frp_max_mw DOUBLE PRECISION
)
"""

CELL_DDL = """
CREATE TABLE IF NOT EXISTS cell_activity (
    day DATE NOT NULL,
    lat_index INTEGER NOT NULL,
    lon_index INTEGER NOT NULL,
    sensor VARCHAR(16) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    detections BIGINT NOT NULL,
    frp_sum_mw DOUBLE PRECISION NOT NULL,
    frp_max_mw DOUBLE PRECISION
)
"""

DAILY_FILL = """
INSERT INTO daily_activity (
    day, sensor, confidence_category, daynight, satellite, source_code,
    is_synthetic, detections, frp_sum_mw, frp_max_mw
)
SELECT
    CAST((acquired_at AT TIME ZONE 'UTC') AS date),
    sensor,
    confidence_category,
    daynight,
    satellite,
    source_code,
    is_synthetic,
    count(*)::bigint,
    COALESCE(sum(frp_mw), 0),
    max(frp_mw)
FROM fire_observations
GROUP BY 1, 2, 3, 4, 5, 6, 7
"""

CELL_FILL = """
INSERT INTO cell_activity (
    day, lat_index, lon_index, sensor, is_synthetic,
    detections, frp_sum_mw, frp_max_mw
)
SELECT
    CAST((acquired_at AT TIME ZONE 'UTC') AS date),
    CAST(floor((latitude + 90.0) / 2.0) AS integer),
    CAST(floor((longitude + 180.0) / 2.0) AS integer),
    sensor,
    is_synthetic,
    count(*)::bigint,
    COALESCE(sum(frp_mw), 0),
    max(frp_mw)
FROM fire_observations
GROUP BY 1, 2, 3, 4, 5
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Schema parity only: SQLite keeps using the live scan.
        op.execute(DAILY_DDL.replace("DOUBLE PRECISION", "FLOAT"))
        op.execute(CELL_DDL.replace("DOUBLE PRECISION", "FLOAT"))
        return

    # The old views have no sensor on the cell rollup and cannot be updated
    # incrementally; drop them and rebuild as tables.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS cell_activity")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_activity")

    op.execute(DAILY_DDL)
    op.execute(CELL_DDL)
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_activity_day ON daily_activity (day)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_daily_activity_day_synthetic "
        "ON daily_activity (day, is_synthetic)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_cell_activity_day ON cell_activity (day)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cell_activity_lookup "
        "ON cell_activity (day, is_synthetic, lat_index, lon_index)"
    )

    op.execute(DAILY_FILL)
    op.execute(CELL_FILL)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        op.execute("DROP TABLE IF EXISTS cell_activity")
        op.execute("DROP TABLE IF EXISTS daily_activity")
        return

    op.execute("DROP TABLE IF EXISTS cell_activity")
    op.execute("DROP TABLE IF EXISTS daily_activity")
    # Recreate the previous shapes so an older code revision still reads them.
    op.execute(
        """
        CREATE MATERIALIZED VIEW daily_activity AS
        SELECT
            CAST((acquired_at AT TIME ZONE 'UTC') AS date) AS day,
            sensor,
            confidence_category,
            daynight,
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
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_activity_key "
        "ON daily_activity "
        "(day, sensor, confidence_category, daynight, satellite, source_code, is_synthetic)"
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW cell_activity AS
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
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_cell_activity_key "
        "ON cell_activity (day, lat_index, lon_index, is_synthetic)"
    )
