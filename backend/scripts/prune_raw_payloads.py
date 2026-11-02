"""Prune duplicated raw JSONB payloads after a verified Parquet export.

``raw_observations.payload`` holds the original source row. Once the canonical
observation is exported to Parquet with a checksum, the JSONB copy duplicates the
archive and is the largest reclaimable block in PostgreSQL.

This script is deliberately conservative:

* dry run by default — nothing is written unless ``--apply`` is passed;
* only days at or before ``--before`` are touched;
* every candidate day must be covered by a dataset entry whose
  ``coverage_start <= day <= coverage_end`` and which carries a checksum;
* rows are **not deleted**: the payload is replaced with a small provenance
  marker, so the row, its fingerprint and its relations survive;
* work is batched and committed per batch, so an interruption resumes cleanly.

    python -m scripts.prune_raw_payloads --before 2026-10-01
    python -m scripts.prune_raw_payloads --before 2026-10-01 --apply
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import session_scope
from app.services.datasets import dataset_root, scan_datasets

MARKER = '{"pruned": true, "reason": "verified_parquet"}'


def _dataset_coverage() -> list[dict[str, Any]]:
    root = dataset_root(get_settings().local_data_directory)
    entries = scan_datasets(root)
    return [
        entry
        for entry in entries
        if entry.get("kind") == "harmonized"
        and entry.get("coverage_start")
        and entry.get("coverage_end")
        and entry.get("checksum")
    ]


def _covered(day: date, datasets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in datasets:
        start = date.fromisoformat(entry["coverage_start"])
        end = date.fromisoformat(entry["coverage_end"])
        if start <= day <= end:
            return entry
    return None


def _candidate_days(session, before: date, source: str | None) -> list[date]:
    clauses = [
        "CAST((f.acquired_at AT TIME ZONE 'UTC') AS date) <= :before",
        "(r.payload->>'pruned') IS NULL",
    ]
    params: dict[str, Any] = {"before": before}
    if source:
        clauses.append("f.source_code = :source")
        params["source"] = source
    rows = session.execute(
        text(
            f"""
            SELECT DISTINCT CAST((f.acquired_at AT TIME ZONE 'UTC') AS date) AS day
            FROM raw_observations r
            JOIN fire_observations f
              ON f.source_id = r.source_id AND f.source_record_id = r.source_record_id
            WHERE {' AND '.join(clauses)}
            ORDER BY day
            """
        ),
        params,
    ).all()
    return [row.day for row in rows]


def _payload_bytes(session, days: list[date], source: str | None) -> int:
    if not days:
        return 0
    params: dict[str, Any] = {"days": days}
    source_clause = ""
    if source:
        source_clause = "AND f.source_code = :source"
        params["source"] = source
    return int(
        session.scalar(
            text(
                f"""
                SELECT COALESCE(sum(pg_column_size(r.payload)), 0)
                FROM raw_observations r
                JOIN fire_observations f
                  ON f.source_id = r.source_id AND f.source_record_id = r.source_record_id
                WHERE CAST((f.acquired_at AT TIME ZONE 'UTC') AS date) = ANY(:days)
                  AND (r.payload->>'pruned') IS NULL
                  {source_clause}
                """
            ),
            params,
        )
        or 0
    )


def _prune_batch(session, day: date, source: str | None, batch: int) -> int:
    params: dict[str, Any] = {"day": day, "batch": batch, "marker": MARKER}
    source_clause = ""
    if source:
        source_clause = "AND f.source_code = :source"
        params["source"] = source
    result = session.execute(
        text(
            f"""
            UPDATE raw_observations r
            SET payload = CAST(:marker AS jsonb)
            FROM fire_observations f
            WHERE f.source_id = r.source_id
              AND f.source_record_id = r.source_record_id
              AND CAST((f.acquired_at AT TIME ZONE 'UTC') AS date) = :day
              AND (r.payload->>'pruned') IS NULL
              {source_clause}
              AND r.id IN (
                  SELECT r2.id
                  FROM raw_observations r2
                  JOIN fire_observations f2
                    ON f2.source_id = r2.source_id
                   AND f2.source_record_id = r2.source_record_id
                  WHERE CAST((f2.acquired_at AT TIME ZONE 'UTC') AS date) = :day
                    AND (r2.payload->>'pruned') IS NULL
                  LIMIT :batch
              )
            """
        ),
        params,
    )
    return int(result.rowcount or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune verified raw payloads")
    parser.add_argument("--before", required=True, help="Last day to prune (YYYY-MM-DD)")
    parser.add_argument("--source", help="Only this source code")
    parser.add_argument("--apply", action="store_true", help="Actually write (default: dry run)")
    parser.add_argument("--batch", type=int, default=50_000, help="Rows per commit")
    args = parser.parse_args()

    before = date.fromisoformat(args.before)
    datasets = _dataset_coverage()

    with session_scope() as session:
        if session.get_bind().dialect.name != "postgresql":
            print("This procedure only applies to PostgreSQL.")
            return 1

        days = _candidate_days(session, before, args.source)
        if not days:
            print("No prunable raw payloads found for that boundary.")
            return 0

        covered: list[date] = []
        missing: list[date] = []
        for day in days:
            if _covered(day, datasets):
                covered.append(day)
            else:
                missing.append(day)

        total_bytes = _payload_bytes(session, covered, args.source)
        print(f"Candidate days: {len(days)}  covered by verified Parquet: {len(covered)}")
        if missing:
            print(
                "Refusing to touch days without a verified export: "
                + ", ".join(day.isoformat() for day in missing[:10])
                + (" …" if len(missing) > 10 else "")
            )
        print(f"Reclaimable payload: {total_bytes / 1024 / 1024:.1f} MB")

        if not args.apply:
            print("Dry run only. Re-run with --apply to replace the covered payloads.")
            return 0

        pruned = 0
        while True:
            batch_total = 0
            for day in covered:
                batch_total += _prune_batch(session, day, args.source, args.batch)
            session.commit()
            pruned += batch_total
            if batch_total == 0:
                break
            print(f"  pruned {pruned:,} rows…")

    print(f"Done. Replaced {pruned:,} payloads with a provenance marker; rows retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
