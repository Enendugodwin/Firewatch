"""Delete everything older than a cutoff, keeping recent analysis.

    python -m scripts.cleanup_before --before 2026-10-06            # dry run
    python -m scripts.cleanup_before --before 2026-10-06 --apply --vacuum

This is destructive and intentionally explicit: it removes canonical
observations, raw payloads, matches, event memberships, availability, coverage,
partitions and rollup rows before the cutoff. Ingestion run rows are kept as an
audit trail. Nothing after the cutoff is touched.

The delete uses temp tables and suspends FK triggers in one transaction, the same
pattern as ``delete_history.py``: cascading checks on unindexed
``event_observations.observation_id`` otherwise re-scan the table per row.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy import text

from app.core.logging import configure_logging
from app.db.session import get_engine, session_scope

PREVIEW_SQL = """
select
  (select count(*) from fire_observations where acquired_at < :before),
  (select count(*) from raw_observations where payload->>'acq_date' < :before_text),
  (select count(*) from observation_matches where match_day < :before),
  (select count(*) from ingestion_partitions where date_end < :before),
  (select count(*) from source_availability where observation_date < :before),
  (select count(*) from harmonization_coverage where day < :before)
"""


def _preview(session, before: date) -> tuple[int, ...]:
    row = session.execute(
        text(PREVIEW_SQL), {"before": before, "before_text": before.isoformat()}
    ).one()
    return tuple(int(value or 0) for value in row)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, help="Delete data before this UTC day")
    parser.add_argument("--apply", action="store_true", help="Actually delete")
    parser.add_argument("--vacuum", action="store_true", help="VACUUM FULL afterwards")
    args = parser.parse_args()

    configure_logging()
    before = date.fromisoformat(args.before)

    with session_scope() as session:
        observations, raw, matches, partitions, availability, coverage = _preview(session, before)
        in_db = session.execute(
            text("select pg_size_pretty(pg_database_size(current_database()))")
        ).scalar()
        print(f"Cutoff: keep data from {before.isoformat()} onward")
        print(f"  database now:        {in_db}")
        print(f"  canonical before:    {observations:,}")
        print(f"  raw payloads before: {raw:,}")
        print(f"  matches before:      {matches:,}")
        print(f"  partitions before:   {partitions:,}")
        print(f"  availability before: {availability:,}")
        print(f"  coverage before:     {coverage:,}")
        if not args.apply:
            print("Dry run. Re-run with --apply to delete.")
            return 0

        session.execute(text("SET statement_timeout = 0"))
        session.execute(text("SET session_replication_role = replica"))
        session.execute(text("DROP TABLE IF EXISTS doomed_observations"))
        session.execute(text("DROP TABLE IF EXISTS doomed_raw_payloads"))
        session.execute(
            text(
                "CREATE TEMP TABLE doomed_observations ON COMMIT DROP AS "
                "SELECT id FROM fire_observations WHERE acquired_at < :before"
            ),
            {"before": before},
        )
        session.execute(
            text(
                "CREATE TEMP TABLE doomed_raw_payloads ON COMMIT DROP AS "
                "SELECT id FROM raw_observations WHERE payload->>'acq_date' < :before_text"
            ),
            {"before_text": before.isoformat()},
        )

        members = (
            session.execute(
                text(
                    "DELETE FROM event_observations eo USING doomed_observations d "
                    "WHERE eo.observation_id = d.id"
                )
            ).rowcount
            or 0
        )
        deleted_matches = (
            session.execute(
                text(
                    "DELETE FROM observation_matches m USING doomed_observations d "
                    "WHERE m.observation_a_id = d.id OR m.observation_b_id = d.id"
                )
            ).rowcount
            or 0
        )
        deleted_obs = (
            session.execute(
                text(
                    "DELETE FROM fire_observations o USING doomed_observations d WHERE o.id = d.id"
                )
            ).rowcount
            or 0
        )
        deleted_raw = (
            session.execute(
                text("DELETE FROM raw_observations r USING doomed_raw_payloads d WHERE r.id = d.id")
            ).rowcount
            or 0
        )
        deleted_events = (
            session.execute(
                text(
                    "DELETE FROM fire_events e WHERE NOT EXISTS "
                    "(SELECT 1 FROM event_observations eo WHERE eo.event_id = e.id)"
                )
            ).rowcount
            or 0
        )
        deleted_availability = (
            session.execute(
                text("DELETE FROM source_availability WHERE observation_date < :before"),
                {"before": before},
            ).rowcount
            or 0
        )
        deleted_coverage = (
            session.execute(
                text("DELETE FROM harmonization_coverage WHERE day < :before"),
                {"before": before},
            ).rowcount
            or 0
        )
        deleted_partitions = (
            session.execute(
                text("DELETE FROM ingestion_partitions WHERE date_end < :before"),
                {"before": before},
            ).rowcount
            or 0
        )
        deleted_daily = (
            session.execute(
                text("DELETE FROM daily_activity WHERE day < :before"), {"before": before}
            ).rowcount
            or 0
        )
        deleted_cells = (
            session.execute(
                text("DELETE FROM cell_activity WHERE day < :before"), {"before": before}
            ).rowcount
            or 0
        )
        session.execute(text("SET session_replication_role = origin"))
        session.commit()
        print(
            "Deleted: "
            f"observations={deleted_obs:,}, raw={deleted_raw:,}, matches={deleted_matches:,}, "
            f"memberships={members:,}, events={deleted_events:,}, "
            f"availability={deleted_availability:,}, coverage={deleted_coverage:,}, "
            f"partitions={deleted_partitions:,}, daily_rows={deleted_daily:,}, "
            f"cell_rows={deleted_cells:,}"
        )

    if args.vacuum:
        print("VACUUM FULL (this can take minutes)...")
        engine = get_engine()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("SET statement_timeout = 0"))
            for table in (
                "fire_observations",
                "raw_observations",
                "observation_matches",
                "event_observations",
                "fire_events",
                "daily_activity",
                "cell_activity",
            ):
                print(f"  vacuum {table}")
                connection.execute(text(f"VACUUM (FULL, ANALYZE) {table}"))

    with session_scope() as session:
        size = session.execute(
            text("select pg_size_pretty(pg_database_size(current_database()))")
        ).scalar()
        obs = session.execute(text("select count(*) from fire_observations")).scalar()
        raw = session.execute(text("select count(*) from raw_observations")).scalar()
        print(f"Done. database={size}, observations={obs:,}, raw_payloads={raw:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
