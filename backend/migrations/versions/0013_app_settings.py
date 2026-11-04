"""Application settings set from the admin portal.

Revision ID: 0013_app_settings
Revises: 0012_raw_exports
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op

revision = "0013_app_settings"
down_revision = "0012_raw_exports"
branch_labels = None
depends_on = None


PG_DDL = """
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(PG_DDL if bind.dialect.name == "postgresql" else SQLITE_DDL)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
