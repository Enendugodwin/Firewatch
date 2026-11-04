"""Harmonized counts in the cell rollup, and the anti-join index.

The map's harmonized view used to fall back to a live scan over every detection
because the rollup could not express "exclude VIIRS with a MODIS association".
That scan exceeded the 60 s statement cap at world zoom and the map went blank.

``cell_activity`` now stores, per day / 2° cell / sensor, how many VIIRS
detections have a probable or possible MODIS association and the resulting
harmonized count. The map's world view reads the rollup again.

The live anti-join at high zoom already has indexes on
``observation_matches.observation_b_id`` and ``(match_status,
observation_b_id)`` from migration 0010.

Revision ID: 0014_harmonized_cell_rollup
Revises: 0013_app_settings
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op

revision = "0014_harmonized_cell_rollup"
down_revision = "0013_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE cell_activity "
            "ADD COLUMN IF NOT EXISTS matched_viirs BIGINT NOT NULL DEFAULT 0"
        )
        op.execute(
            "ALTER TABLE cell_activity "
            "ADD COLUMN IF NOT EXISTS harmonized BIGINT NOT NULL DEFAULT 0"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE cell_activity DROP COLUMN IF EXISTS harmonized")
        op.execute("ALTER TABLE cell_activity DROP COLUMN IF EXISTS matched_viirs")
