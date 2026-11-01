"""Widen availability status.

``not_yet_available`` is 17 characters, but the column was declared ``varchar(16)``.
SQLite ignores the declared width, PostgreSQL does not, so the first Postgres copy
failed with "value too long". Widen the column; SQLite needs no rebuild because it
never enforced the length.

Revision ID: 0003_availability_status_width
Revises: 0002_observations
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_availability_status_width"
down_revision = "0002_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "source_availability",
            "status",
            existing_type=sa.String(length=16),
            type_=sa.String(length=24),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Reverting would truncate values longer than 16 characters; leave it widened.
    pass
