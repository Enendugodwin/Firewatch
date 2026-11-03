"""Score cross-sensor associations across the stored archive, day by day.

The in-app harmonization pass is a single-scope recompute. This runner walks a
date range one UTC day per transaction, records each processed day in
``harmonization_coverage`` and therefore resumes cleanly after an interruption.

Usage:
    python -m scripts.harmonize_history
    python -m scripts.harmonize_history --region amazon --start 2016-01-01 --end 2024-12-31
    python -m scripts.harmonize_history --start 2026-09-01 --end 2026-11-01 --force
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from sqlalchemy import func, select

from app.core.logging import configure_logging
from app.db.models import FireObservation
from app.db.session import session_scope
from app.services.harmonization import (
    MatchParameters,
    coverage_summary,
    run_harmonization_range,
)
from app.services.historical_backfill import resolve_tile
from app.services.observation_queries import BBox


def _stored_range() -> tuple[date, date] | None:
    with session_scope() as session:
        row = session.execute(
            select(
                func.min(FireObservation.acquired_at),
                func.max(FireObservation.acquired_at),
            )
        ).one()
    if row[0] is None or row[1] is None:
        return None
    return row[0].date(), row[1].date()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Day-by-day, resumable cross-sensor association pass."
    )
    parser.add_argument("--start", type=date.fromisoformat, help="First day (UTC)")
    parser.add_argument("--end", type=date.fromisoformat, help="Last day (UTC)")
    parser.add_argument("--region", help="Catalogue region key (limits the pass to its bbox)")
    parser.add_argument("--bbox", help="west,south,east,north")
    parser.add_argument("--name", default="custom", help="Scope name for a custom bbox")
    parser.add_argument("--synthetic", action="store_true", help="Score fixture rows")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute days that already have a coverage record",
    )
    parser.add_argument("--limit-days", type=int, default=0, help="Stop after N processed days")
    parser.add_argument(
        "--status-every", type=int, default=10, help="Print progress every N processed days"
    )
    args = parser.parse_args()

    configure_logging()

    stored = _stored_range()
    if stored is None:
        print("No observations stored.", file=sys.stderr)
        return 1
    start = args.start or stored[0]
    end = args.end or stored[1]
    if start > end:
        print("start must be on or before end", file=sys.stderr)
        return 2

    bbox: BBox | None = None
    if args.region or args.bbox:
        tile = resolve_tile(region=args.region, bbox=args.bbox, name=args.name)
        bbox = BBox(west=tile.west, south=tile.south, east=tile.east, north=tile.north)

    print(
        f"Harmonizing {start} .. {end} "
        f"({'whole stored archive' if bbox is None else f'bbox {bbox.as_list()}'})"
    )

    from app.services.harmonization import scope_key

    scope = scope_key(bbox)
    with session_scope() as session:
        before = coverage_summary(session, is_synthetic=args.synthetic)
    covered_before = next(
        (item["days"] for item in before["scopes"] if item["scope"] == scope), 0
    )
    print(f"Scope {scope}: {covered_before} day(s) already covered")

    started = time.perf_counter()
    processed_this_run = 0

    def progress(state: dict) -> None:
        nonlocal processed_this_run
        processed_this_run += 1
        if args.limit_days and processed_this_run >= args.limit_days:
            # The range runner has no early-stop hook; the signal is advisory and
            # a rerun skips what is already covered.
            print("  limit reached; finishing the current day and stopping next run")
        if processed_this_run % max(1, args.status_every) == 0:
            elapsed = time.perf_counter() - started
            done = state["processed"] + state["skipped"]
            rate = done / elapsed if elapsed else 0.0
            remaining = (state["days"] - done) / rate if rate else 0.0
            print(
                f"  {state['day']} processed={state['processed']} "
                f"obs={state['observations']:,} pairs={state['pairs']:,} "
                f"({rate * 60:.0f} days/min, ETA {remaining / 60:.0f}m)"
            )

    summary = run_harmonization_range(
        start=start,
        end=end,
        params=MatchParameters(),
        is_synthetic=args.synthetic,
        bbox=bbox,
        force=args.force,
        progress=progress,
    )

    print("\nSummary")
    print(
        f"  processed {summary['processed']} day(s), skipped {summary['skipped']}, "
        f"truncated {summary['truncated_days']}"
    )
    print(
        f"  observations {summary['observations']:,}; pairs {summary['pairs']:,} "
        f"(probable {summary['probable']:,}, possible {summary['possible']:,}, "
        f"rejected {summary['rejected']:,})"
    )
    print(f"  finished in {(time.perf_counter() - started) / 60:.1f} min")

    # Numbers below are still detections, never fires.
    with session_scope() as session:
        after = coverage_summary(session, is_synthetic=args.synthetic)
    print("\nCoverage by scope")
    for item in after["scopes"]:
        print(
            f"  {item['scope']:<40} {item['days']:>5} day(s) "
            f"{item['first_day']} .. {item['last_day']} "
            f"pairs={item['pairs']:,}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
