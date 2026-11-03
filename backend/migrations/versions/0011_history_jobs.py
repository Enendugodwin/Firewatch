"""A durable job row for long historical runs.

A backfill across years is thousands of five-day requests and can take hours; it
cannot be an HTTP request. ``history_jobs`` stores the request, the latest
progress and the final summary so the API can start a run, poll it and cancel it
between windows. Completed ingestion partitions and association days are skipped
on a rerun, so the same row doubles as the resume handle.

Revision ID: 0011_history_jobs
Revises: 0010_harmonization_coverage
Create Date: 2026-11-03
"""

from __future__ import annotations

from alembic import op

revision = "0011_history_jobs"
down_revision = "0010_harmonization_coverage"
branch_labels = None
depends_on = None


PG_DDL = """
CREATE TABLE IF NOT EXISTS history_jobs (
    id UUID PRIMARY KEY,
    kind VARCHAR(32) NOT NULL DEFAULT 'history',
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    datasets JSONB NOT NULL DEFAULT '[]'::jsonb,
    region VARCHAR(64),
    bbox VARCHAR(64),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    harmonize BOOLEAN NOT NULL DEFAULT FALSE,
    progress JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS history_jobs (
    id CHAR(32) PRIMARY KEY,
    kind VARCHAR(32) NOT NULL DEFAULT 'history',
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    datasets TEXT NOT NULL DEFAULT '[]',
    region VARCHAR(64),
    bbox VARCHAR(64),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    harmonize BOOLEAN NOT NULL DEFAULT 0,
    progress TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    cancel_requested BOOLEAN NOT NULL DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(PG_DDL if bind.dialect.name == "postgresql" else SQLITE_DDL)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_history_jobs_created_at ON history_jobs (created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_history_jobs_status ON history_jobs (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_history_jobs_status")
    op.execute("DROP INDEX IF EXISTS ix_history_jobs_created_at")
    op.execute("DROP TABLE IF EXISTS history_jobs")
