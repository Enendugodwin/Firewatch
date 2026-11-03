"""Backfill the standard-processing archive for a documented fire region.

The FIRMS area API serves history (MODIS from 2000-11-01, VIIRS from 2012-01-20)
but only five days per request, so this is a bounded loop over resumable
partitions, not one enormous download. Coverage is read from the API first and
the requested window is clamped to it: days a product never processed are never
marked "empty" (which the calendar would read as "quiet").

Usage:
    python -m scripts.backfill_history --region amazon --start 2016-01-01 --end 2024-12-31 \
        --sources MODIS_SP,VIIRS_SNPP_SP

    # a short pilot that finishes quickly
    python -m scripts.backfill_history --region amazon --start 2024-08-01 --end 2024-08-31 \
        --sources MODIS_SP --limit-requests 3
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from app.core.logging import configure_logging, get_logger
from app.services.firms.client import FirmsAuthError, FirmsError
from app.services.historical_backfill import (
    HISTORY_SOURCES,
    REGIONS,
    clamped_window,
    plan_windows,
    resolve_tile,
    validate_history_source,
)
from app.services.ingestion import build_client, ingest_range

logger = get_logger("scripts.backfill_history")


def _parse_sources(value: str) -> list[str]:
    codes = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [code for code in codes if not validate_history_source(code)]
    if unknown:
        raise SystemExit(
            f"Not a standard-processing source: {', '.join(unknown)}. "
            f"Choose from {', '.join(HISTORY_SOURCES)}."
        )
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resumable historical backfill for one fire region."
    )
    parser.add_argument("--region", choices=sorted(REGIONS), help="Catalogue region key")
    parser.add_argument("--bbox", help="west,south,east,north for a custom region")
    parser.add_argument("--name", default="custom", help="Stable partition key for --bbox")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--sources",
        default="MODIS_SP,VIIRS_SNPP_SP",
        help=f"Comma-separated standard-processing products ({', '.join(HISTORY_SOURCES)})",
    )
    parser.add_argument("--limit-requests", type=int, default=0, help="Stop after N requests")
    parser.add_argument(
        "--rollup-every",
        type=int,
        default=50,
        help="Refresh the daily rollup every N completed requests (0 = only at the end)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--ignore-coverage",
        action="store_true",
        help="Ingest even where FIRMS reports no coverage (not recommended)",
    )
    args = parser.parse_args()

    configure_logging()

    if args.start > args.end:
        print("start must be on or before end", file=sys.stderr)
        return 2

    try:
        tile = resolve_tile(region=args.region, bbox=args.bbox, name=args.name)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    codes = _parse_sources(args.sources)
    client = build_client()

    # Coverage first: a product that never processed a day must not produce an
    # "empty" availability row for it.
    windows_by_source: dict[str, list[tuple[date, date]]] = {}
    for code in codes:
        try:
            coverage = client.fetch_availability(code)
        except FirmsAuthError:
            print("FIRMS rejected the MAP_KEY.", file=sys.stderr)
            return 2
        except FirmsError as exc:
            print(f"Could not read coverage for {code}: {exc}", file=sys.stderr)
            return 2

        if args.ignore_coverage:
            windows = plan_windows(args.start, args.end)
        else:
            clamped = clamped_window(coverage, args.start, args.end)
            windows = plan_windows(*clamped) if clamped else []
        windows_by_source[code] = windows
        print(
            f"{code}: coverage {coverage.min_date} .. {coverage.max_date}; "
            f"{len(windows)} window(s) in {args.start} .. {args.end}"
        )

    total_requests = sum(len(windows) for windows in windows_by_source.values())
    if args.limit_requests:
        total_requests = min(total_requests, args.limit_requests)
    print(
        f"Region {tile.key} ({tile.bbox}): {total_requests} request(s) across "
        f"{len(codes)} source(s)"
    )
    if args.dry_run:
        for code, windows in windows_by_source.items():
            for start, end in windows:
                print(f"  {code} {start} -> {end}")
        return 0
    if total_requests == 0:
        print("Nothing to do: the requested period is outside the product coverage.")
        return 0

    started = time.perf_counter()
    done = 0
    inserted = received = rejected = failed = skipped = 0
    per_source: dict[str, int] = {code: 0 for code in codes}

    def refresh(reason: str) -> None:
        from app.db.session import session_scope
        from app.services.rollups import refresh_rollup

        began = time.perf_counter()
        with session_scope() as session:
            available = refresh_rollup(session)
        print(f"  rollup refreshed ({reason}) in {time.perf_counter() - began:.1f}s"
              if available
              else "  rollup not available (SQLite)")

    for code, windows in windows_by_source.items():
        for start, end in windows:
            if args.limit_requests and done >= args.limit_requests:
                break
            done += 1
            began = time.perf_counter()
            try:
                result = ingest_range(code, start_date=start, end_date=end, tile=tile)
            except Exception as error:  # noqa: BLE001 - one window must not abort the run
                failed += 1
                logger.exception("backfill_window_failed", source=code, start=str(start))
                print(f"  [{done}/{total_requests}] {code} {start}..{end} FAILED: {error}")
                continue

            elapsed = time.perf_counter() - began
            inserted += result.records_inserted
            received += result.records_received
            rejected += result.records_rejected
            skipped += result.partitions_skipped
            per_source[code] += result.records_inserted
            if result.status == "failed":
                failed += 1

            overall = time.perf_counter() - started
            eta = (overall / done) * (total_requests - done) if done else 0.0
            print(
                f"  [{done}/{total_requests}] {code} {start}..{end} {result.status} "
                f"+{result.records_inserted:,} ({elapsed:.0f}s, ETA {eta / 60:.0f}m)"
            )
            if args.rollup_every and done % args.rollup_every == 0:
                refresh(f"every {args.rollup_every} requests")

    if inserted:
        refresh("final")

    overall = time.perf_counter() - started
    print("\nSummary")
    for code in codes:
        print(f"  {code:<20} inserted {per_source[code]:>10,}")
    print(
        f"\ninserted {inserted:,} of {received:,} received; rejected {rejected:,}; "
        f"{skipped} partition(s) already complete; {failed} failure(s) in "
        f"{overall / 60:.1f} min"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
