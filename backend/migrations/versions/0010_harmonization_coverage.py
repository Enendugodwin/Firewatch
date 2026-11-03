"""Harmonisation coverage checkpoints and a lookup index for matched VIIRS.

Associations used to be computed in one pass capped at 20,000 observations,
which silently kept only the tail of a long window. The historical pass processes
one UTC day per transaction instead, so this table records which days a scope has
actually scanned. A day without a row means "not processed", which is different
from "processed and no duplicates found".

Revision ID: 0010_harmonization_coverage
Revises: 0009_incremental_rollups
Create Date: 2026-11-03
"""

from __future__ import annotations

from alembic import op

revision = "0010_harmonization_coverage"
down_revision = "0009_incremental_rollups"
branch_labels = None
depends_on = None


PG_DDL = """
CREATE TABLE IF NOT EXISTS harmonization_coverage (
    day DATE NOT NULL,
    scope VARCHAR(64) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    algorithm_version VARCHAR(32) NOT NULL,
    observations INTEGER NOT NULL DEFAULT 0,
    pairs INTEGER NOT NULL DEFAULT 0,
    probable INTEGER NOT NULL DEFAULT 0,
    possible INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    truncated BOOLEAN NOT NULL DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (day, scope, is_synthetic)
)
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS harmonization_coverage (
    day DATE NOT NULL,
    scope VARCHAR(64) NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    algorithm_version VARCHAR(32) NOT NULL,
    observations INTEGER NOT NULL DEFAULT 0,
    pairs INTEGER NOT NULL DEFAULT 0,
    probable INTEGER NOT NULL DEFAULT 0,
    possible INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    truncated BOOLEAN NOT NULL DEFAULT 0,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (day, scope, is_synthetic)
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(PG_DDL)
    else:
        op.execute(SQLITE_DDL)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_harmonization_coverage_scope_day "
        "ON harmonization_coverage (scope, day)"
    )
    # The harmonised series joins matches to the VIIRS side; without this index
    # that join is a sequential scan of every association.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_observation_matches_observation_b_id "
        "ON observation_matches (observation_b_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_observation_matches_status_b "
        "ON observation_matches (match_status, observation_b_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_observation_matches_status_b")
    op.execute("DROP INDEX IF EXISTS ix_observation_matches_observation_b_id")
    op.execute("DROP TABLE IF EXISTS harmonization_coverage")
