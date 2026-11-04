"""Raw-payload export receipts.

One row per exported CSV archive. The stored SHA-256 and row count are the
authority for the later delete: raw payloads are only removed for a range whose
current row count still matches what was exported.

Revision ID: 0012_raw_exports
Revises: 0011_history_jobs
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op

revision = "0012_raw_exports"
down_revision = "0011_history_jobs"
branch_labels = None
depends_on = None


PG_DDL = """
CREATE TABLE IF NOT EXISTS raw_exports (
    id UUID PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    rows INTEGER NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    path VARCHAR(512) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,
    rows_deleted INTEGER
)
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS raw_exports (
    id CHAR(32) PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    rows INTEGER NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    path VARCHAR(512) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    rows_deleted INTEGER
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(PG_DDL if bind.dialect.name == "postgresql" else SQLITE_DDL)
    op.execute("CREATE INDEX IF NOT EXISTS ix_raw_exports_created_at ON raw_exports (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_raw_exports_status ON raw_exports (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_raw_exports_status")
    op.execute("DROP INDEX IF EXISTS ix_raw_exports_created_at")
    op.execute("DROP TABLE IF EXISTS raw_exports")
