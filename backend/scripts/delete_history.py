"""Remove a historical backfill completely and consistently.

Deleting observations alone leaves the store lying: availability would still say
the days were observed (so the calendar would show them as quiet), ingestion
partitions would still claim the windows are done (so a rerun would skip them),
and harmonization coverage would still claim the days were scanned. This script
removes the whole footprint of one backfill tile and then rebuilds the rollups
for the days it touched.

Scope is identified by the ingestion runs of a tile (for example
``region:amazon``), so data from other runs — the global 2026 ingest, fixtures —
is not touched.

Dry run by default:

    python -m scripts.delete_history --tile-key region:amazon
    python -m scripts.delete_history --tile-key region:amazon --apply

After ``--apply`` the rows are gone; space returns to the filesystem only after a
``VACUUM FULL`` of ``fire_observations`` and ``raw_observations`` while nothing
else is writing. This script never runs that automatically.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.db.dialect import dialect_name
from app.db.session import session_scope
from app.services.rollups import refresh_rollup_range

BATCH = 50_000


def _runs_filter() -> str:
    return "select id from ingestion_runs where query_parameters->>'tile' = :tile"


def _counts(session: Session, tile: str) -> dict[str, Any]:
    runs = _runs_filter()
    row = session.execute(
        text(
            f"""
            select
              (select count(*) from fire_observations where run_id in ({runs})),
              (select count(*) from raw_observations where run_id in ({runs})),
              (select count(*) from ingestion_partitions where tile_key = :tile),
              (select count(*) from ingestion_runs
                 where query_parameters->>'tile' = :tile),
              (select count(distinct sa.observation_date) from source_availability sa
                 where exists (
                   select 1 from ingestion_partitions ip
                   where ip.tile_key = :tile and ip.source_id = sa.source_id
                     and sa.observation_date between ip.date_start and ip.date_end
                 ))
            """
        ),
        {"tile": tile},
    ).one()
    days = session.execute(
        text(
            """
            select min(ip.date_start), max(ip.date_end), min(ip.bbox)
            from ingestion_partitions ip where ip.tile_key = :tile
            """
        ),
        {"tile": tile},
    ).one()
    return {
        "observations": row[0],
        "raw_observations": row[1],
        "partitions": row[2],
        "runs": row[3],
        "availability_days": row[4],
        "first_day": days[0],
        "last_day": days[1],
        "bbox": days[2],
    }


def _temp_ids(session: Session, name: str, source_sql: str, params: dict[str, Any]) -> int:
    session.execute(text(f"DROP TABLE IF EXISTS {name}"))
    session.execute(text(f"CREATE TEMP TABLE {name} AS {source_sql}"), params)
    session.commit()
    return int(session.scalar(text(f"SELECT count(*) FROM {name}")) or 0)


def _drain(session: Session, temp: str, target: str, column: str = "id") -> int:
    """Delete target rows whose ids are still in the temp table, in batches."""
    deleted = 0
    while True:
        ids = session.execute(
            text(
                f"DELETE FROM {temp} WHERE ctid IN "
                f"(SELECT ctid FROM {temp} LIMIT :batch) RETURNING id"
            ),
            {"batch": BATCH},
        ).scalars().all()
        session.commit()
        if not ids:
            return deleted
        session.execute(
            text(f"DELETE FROM {target} WHERE {column} = ANY(:ids)"), {"ids": ids}
        )
        session.commit()
        deleted += len(ids)


def _scope_key(bbox: str) -> str:
    west, south, east, north = (float(part) for part in bbox.split(","))
    return f"bbox:{west:g},{south:g},{east:g},{north:g}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile-key", required=True, help="e.g. region:amazon")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry run)")
    args = parser.parse_args()
    configure_logging()

    if args.tile_key in ("world", ""):
        print("Refusing to delete the world tile; pass a region tile key.", file=sys.stderr)
        return 2

    with session_scope() as session:
        if dialect_name(session) != "postgresql":
            print("This script targets the PostgreSQL store; SQLite is for tests.", file=sys.stderr)
            return 2

        before = _counts(session, args.tile_key)
        if before["first_day"] is None:
            print(f"No ingestion partitions for tile {args.tile_key!r}; nothing to do.")
            return 0

        print(f"Tile {args.tile_key}")
        print(f"  days              {before['first_day']} .. {before['last_day']}")
        print(f"  bbox              {before['bbox']}")
        print(f"  observations      {before['observations']:>12,}")
        print(f"  raw payload rows  {before['raw_observations']:>12,}")
        print(f"  availability days {before['availability_days']:>12,}")
        print(f"  partitions        {before['partitions']:>12,}")
        print(f"  ingestion runs    {before['runs']:>12,}")

        if not args.apply:
            print("\nDry run. Pass --apply to delete this footprint.")
            return 0

        started = time.perf_counter()
        scope = _scope_key(str(before["bbox"]))
        runs = _runs_filter()

        doomed_obs = _temp_ids(
            session,
            "doomed_obs",
            f"SELECT id FROM fire_observations WHERE run_id IN ({runs})",
            {"tile": args.tile_key},
        )
        doomed_raw = _temp_ids(
            session,
            "doomed_raw",
            f"SELECT id FROM raw_observations WHERE run_id IN ({runs})",
            {"tile": args.tile_key},
        )
        print(f"\nCollected {doomed_obs:,} observations and {doomed_raw:,} raw rows")

        # 1. Associations and event memberships that reference the rows.
        matches = 0
        for side in ("observation_a_id", "observation_b_id"):
            matches += session.execute(
                text(
                    f"DELETE FROM observation_matches m USING doomed_obs d "
                    f"WHERE m.{side} = d.id"
                )
            ).rowcount or 0
            session.commit()
        members = session.execute(
            text(
                "DELETE FROM event_observations eo USING doomed_obs d "
                "WHERE eo.observation_id = d.id"
            )
        ).rowcount or 0
        session.commit()

        # 2. Availability must forget the days, otherwise they read as quiet.
        availability = session.execute(
            text(
                """
                DELETE FROM source_availability sa
                USING ingestion_partitions ip
                WHERE sa.source_id = ip.source_id
                  AND ip.tile_key = :tile
                  AND sa.observation_date BETWEEN ip.date_start AND ip.date_end
                """
            ),
            {"tile": args.tile_key},
        ).rowcount or 0
        session.commit()

        # 3. Observations and their raw payloads, batch by batch.
        observations = _drain(session, "doomed_obs", "fire_observations")
        raw = _drain(session, "doomed_raw", "raw_observations")

        # 4. Coverage checkpoints for the matching bbox scope.
        coverage = session.execute(
            text(
                "DELETE FROM harmonization_coverage "
                "WHERE scope = :scope AND day BETWEEN :start AND :end"
            ),
            {"scope": scope, "start": before["first_day"], "end": before["last_day"]},
        ).rowcount or 0
        session.commit()

        # 5. Partitions and runs last, so the steps above could still find them.
        partitions = session.execute(
            text("DELETE FROM ingestion_partitions WHERE tile_key = :tile"),
            {"tile": args.tile_key},
        ).rowcount or 0
        runs_deleted = session.execute(
            text("DELETE FROM ingestion_runs WHERE query_parameters->>'tile' = :tile"),
            {"tile": args.tile_key},
        ).rowcount or 0
        session.commit()
        session.execute(text("DROP TABLE IF EXISTS doomed_obs"))
        session.execute(text("DROP TABLE IF EXISTS doomed_raw"))
        session.commit()

        # 6. Rebuild only the affected days.
        refreshed = refresh_rollup_range(session, before["first_day"], before["last_day"])

    elapsed = time.perf_counter() - started
    print("\nDeleted")
    print(f"  observations      {observations:>12,}  (of {before['observations']:,})")
    print(f"  raw payload rows  {raw:>12,}  (of {before['raw_observations']:,})")
    print(f"  matches           {matches:>12,}")
    print(f"  event memberships {members:>12,}")
    print(f"  availability rows {availability:>12,}")
    print(f"  coverage days     {coverage:>12,}  (scope {scope})")
    print(f"  partitions        {partitions:>12,}")
    print(f"  ingestion runs    {runs_deleted:>12,}")
    print(f"  rollups rebuilt   {refreshed}")
    print(f"  finished in {elapsed / 60:.1f} min")
    print(
        "\nSpace returns to the filesystem only after VACUUM FULL of "
        "fire_observations and raw_observations with writers stopped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
