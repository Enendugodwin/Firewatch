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

Two details make it fast enough to be practical:

* the target ids are materialised into temporary tables and joined, so each
  delete is one hash join instead of a correlated lookup per row;
* foreign-key triggers are suspended for the delete because the dependent rows
  (matches, event memberships) are removed explicitly first. This matters:
  ``event_observations`` has no index on ``observation_id``, so cascading one
  delete at a time re-scans it per observation.

Everything runs in a single transaction, so an interruption leaves the footprint
intact rather than half-removed.

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


def _scope_key(bbox: str) -> str:
    west, south, east, north = (float(part) for part in bbox.split(","))
    return f"bbox:{west:g},{south:g},{east:g},{north:g}"


def _teardown(session: Session, tile: str, before: dict[str, Any]) -> dict[str, int | bool]:
    runs = _runs_filter()
    scope = _scope_key(str(before["bbox"]))
    counts: dict[str, int | bool] = {}

    session.execute(text("SET statement_timeout = 0"))
    session.execute(text("SET session_replication_role = replica"))
    session.execute(text("drop table if exists doomed_observations"))
    session.execute(text("drop table if exists doomed_raw_payloads"))
    session.execute(
        text(
            "create temp table doomed_observations on commit drop as "
            f"select id from fire_observations where run_id in ({runs})"
        ),
        {"tile": tile},
    )
    session.execute(
        text(
            "create temp table doomed_raw_payloads on commit drop as "
            f"select id from raw_observations where run_id in ({runs})"
        ),
        {"tile": tile},
    )

    counts["members"] = session.execute(
        text(
            "delete from event_observations eo using doomed_observations d "
            "where eo.observation_id = d.id"
        )
    ).rowcount or 0
    matches = 0
    for side in ("observation_a_id", "observation_b_id"):
        matches += session.execute(
            text(
                f"delete from observation_matches m using doomed_observations d "
                f"where m.{side} = d.id"
            )
        ).rowcount or 0
    counts["matches"] = matches
    counts["observations"] = session.execute(
        text("delete from fire_observations o using doomed_observations d where o.id = d.id")
    ).rowcount or 0
    counts["raw"] = session.execute(
        text("delete from raw_observations r using doomed_raw_payloads d where r.id = d.id")
    ).rowcount or 0

    counts["availability"] = session.execute(
        text(
            """
            delete from source_availability sa
            using ingestion_partitions ip
            where sa.source_id = ip.source_id
              and ip.tile_key = :tile
              and sa.observation_date between ip.date_start and ip.date_end
            """
        ),
        {"tile": tile},
    ).rowcount or 0
    counts["coverage"] = session.execute(
        text(
            "delete from harmonization_coverage "
            "where scope = :scope and day between :start and :end"
        ),
        {"scope": scope, "start": before["first_day"], "end": before["last_day"]},
    ).rowcount or 0
    counts["partitions"] = session.execute(
        text("delete from ingestion_partitions where tile_key = :tile"), {"tile": tile}
    ).rowcount or 0
    counts["runs"] = session.execute(
        text("delete from ingestion_runs where query_parameters->>'tile' = :tile"),
        {"tile": tile},
    ).rowcount or 0

    session.execute(text("SET session_replication_role = origin"))
    session.commit()
    return counts


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
        counts = _teardown(session, args.tile_key, before)

    refreshed = False
    if counts["observations"]:
        with session_scope() as session:
            refreshed = refresh_rollup_range(
                session, before["first_day"], before["last_day"]
            )

    elapsed = time.perf_counter() - started
    print("\nDeleted")
    print(f"  observations      {counts['observations']:>12,}  (of {before['observations']:,})")
    print(f"  raw payload rows  {counts['raw']:>12,}  (of {before['raw_observations']:,})")
    print(f"  matches           {counts['matches']:>12,}")
    print(f"  event memberships {counts['members']:>12,}")
    print(f"  availability rows {counts['availability']:>12,}")
    print(f"  coverage days     {counts['coverage']:>12,}")
    print(f"  partitions        {counts['partitions']:>12,}")
    print(f"  ingestion runs    {counts['runs']:>12,}")
    print(f"  rollups rebuilt   {refreshed}")
    print(f"  finished in {elapsed / 60:.1f} min")
    print(
        "\nSpace returns to the filesystem only after VACUUM FULL of "
        "fire_observations and raw_observations with writers stopped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
