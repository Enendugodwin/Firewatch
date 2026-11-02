"""Where does the storage actually go?

Read-only. Reports the database size, per-table sizes (heap/index/TOAST), row
counts and how much of ``raw_observations`` is JSONB payload that duplicates the
canonical observation. Nothing is modified.

    python -m scripts.storage_report
    python -m scripts.storage_report --json
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import text

from app.db.session import session_scope


def _human(value: float | int | None) -> str:
    if value is None:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def _postgres_report(session) -> dict[str, Any]:
    database_size = session.scalar(text("SELECT pg_database_size(current_database())"))
    tables = session.execute(
        text(
            """
            SELECT c.relname,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   pg_relation_size(c.oid) AS heap_bytes,
                   pg_indexes_size(c.oid) AS index_bytes,
                   pg_total_relation_size(c.reltoastrelid) AS toast_bytes,
                   c.reltuples::bigint AS estimated_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            """
        )
    ).all()

    raw = session.execute(
        text(
            """
            SELECT count(*) AS rows,
                   COALESCE(sum(pg_column_size(payload)), 0) AS payload_bytes,
                   COALESCE(avg(pg_column_size(payload)), 0) AS avg_payload_bytes
            FROM raw_observations
            """
        )
    ).one()
    canonical = session.execute(
        text(
            """
            SELECT count(*) AS rows, COALESCE(sum(pg_column_size(f.*)), 0) AS row_bytes
            FROM fire_observations f
            """
        )
    ).one()
    by_source = session.execute(
        text(
            """
            SELECT source_code, count(*) AS rows
            FROM fire_observations
            GROUP BY source_code
            ORDER BY count(*) DESC
            """
        )
    ).all()

    return {
        "dialect": "postgresql",
        "database_size_bytes": int(database_size or 0),
        "tables": [
            {
                "name": row.relname,
                "total_bytes": int(row.total_bytes),
                "heap_bytes": int(row.heap_bytes),
                "index_bytes": int(row.index_bytes),
                "toast_bytes": int(row.toast_bytes or 0),
                "estimated_rows": int(row.estimated_rows or 0),
            }
            for row in tables
        ],
        "raw_observations": {
            "rows": int(raw.rows or 0),
            "payload_bytes": int(raw.payload_bytes or 0),
            "average_payload_bytes": round(float(raw.avg_payload_bytes or 0), 1),
        },
        "fire_observations": {
            "rows": int(canonical.rows or 0),
            "row_bytes": int(canonical.row_bytes or 0),
        },
        "rows_by_source": [
            {"source_code": row.source_code, "rows": int(row.rows)} for row in by_source
        ],
    }


def _sqlite_report(session) -> dict[str, Any]:
    counts = {}
    for table in ("fire_observations", "raw_observations", "regional_daily_statistics"):
        counts[table] = int(session.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
    return {"dialect": "sqlite", "row_counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Storage and duplication report")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    args = parser.parse_args()

    with session_scope() as session:
        dialect = session.get_bind().dialect.name
        report = (
            _postgres_report(session) if dialect == "postgresql" else _sqlite_report(session)
        )

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"Dialect: {report['dialect']}")
    if report["dialect"] != "postgresql":
        for table, rows in report["row_counts"].items():
            print(f"  {table:32s} {rows:>12,} rows")
        return 0

    print(f"Database size: {_human(report['database_size_bytes'])}")
    print()
    print(f"{'Table':32s} {'Total':>10s} {'Heap':>10s} {'Index':>10s} {'TOAST':>10s} {'Rows':>12s}")
    for table in report["tables"]:
        print(
            f"{table['name']:32s} {_human(table['total_bytes']):>10s} "
            f"{_human(table['heap_bytes']):>10s} {_human(table['index_bytes']):>10s} "
            f"{_human(table['toast_bytes']):>10s} {table['estimated_rows']:>12,}"
        )

    raw = report["raw_observations"]
    canonical = report["fire_observations"]
    print()
    print(f"fire_observations rows          {canonical['rows']:>14,}")
    print(f"raw_observations rows           {raw['rows']:>14,}")
    print(f"raw JSONB payload               {_human(raw['payload_bytes']):>14s}")
    print(f"average payload per raw row     {raw['average_payload_bytes']:>14,.1f} B")
    if raw["rows"]:
        print(
            "duplication ratio (raw rows / canonical rows): "
            f"{raw['rows'] / max(1, canonical['rows']):.2f}"
        )
    print()
    print("Largest sources:")
    for row in report["rows_by_source"][:8]:
        print(f"  {row['source_code']:24s} {row['rows']:>12,}")
    print()
    print(
        "The raw payload is the largest reclaimable block. It is pruned only after a "
        "verified Parquet export covers the day — see scripts/prune_raw_payloads.py."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
