"""Copy every table from one database to another (SQLite -> PostgreSQL).

Ids, UUIDs and timestamps are preserved so API responses stay stable across the
move. Rows that already exist in the target are skipped, so the script is safe to
re-run after a partial copy.

Usage:
    python -m scripts.copy_to_postgres \
        --source sqlite+pysqlite:///./firewatch.db \
        --target postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import models  # noqa: F401 - registers every table on Base.metadata
from app.db.base import Base

BATCH = 1000


def _utc(value: Any) -> Any:
    """SQLite hands back naive datetimes; they were stored as UTC."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _utc(value) for key, value in row.items()}


def copy(source: Engine, target: Engine) -> dict[str, int]:
    copied: dict[str, int] = {}
    with source.connect() as src, target.begin() as dst:
        for table in Base.metadata.sorted_tables:
            rows = [dict(row) for row in src.execute(select(table)).mappings()]
            if not rows:
                copied[table.name] = 0
                continue
            for start in range(0, len(rows), BATCH):
                chunk = [_clean(row) for row in rows[start : start + BATCH]]
                statement = pg_insert(table).values(chunk)
                statement = statement.on_conflict_do_nothing()
                dst.execute(statement)
            copied[table.name] = len(rows)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy all tables between databases.")
    parser.add_argument(
        "--source", default="sqlite+pysqlite:///./firewatch.db", help="source database URL"
    )
    parser.add_argument("--target", required=True, help="target database URL")
    args = parser.parse_args()

    if not args.target.startswith("postgresql"):
        print("Target must be a PostgreSQL URL.", file=sys.stderr)
        return 2

    source = create_engine(args.source, future=True)
    target = create_engine(args.target, future=True)

    copied = copy(source, target)
    total = sum(copied.values())
    for name, count in copied.items():
        print(f"{name:<24} {count:>8}")
    print(f"{'total':<24} {total:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
