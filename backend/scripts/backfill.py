"""Backfill a long window in bounded, resumable chunks.

The API deliberately caps a single request at five days. A sixty-day backfill is
therefore a loop, not one enormous request: each (source, 5-day window) is a
registered partition, so re-running the script after an interruption resumes
instead of duplicating rows.

Usage:
    python -m scripts.backfill --start 2026-09-02 --end 2026-10-31
    python -m scripts.backfill --start 2026-09-02 --end 2026-10-31 --sources MODIS_NRT
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

from app.core.logging import configure_logging, get_logger
from app.services.firms.tiles import WORLD
from app.services.ingestion import ingest_range
from app.services.sources import FIRMS_SOURCES, get_source

logger = get_logger("scripts.backfill")

#: Products whose standard-processing coverage has stopped contributing; they are
#: attempted last so the useful near-real-time data lands first.
NRT_ORDER = (
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "MODIS_NRT",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_SP",
    "MODIS_SP",
)


def chunks(start: date, end: date, size: int) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=size - 1), end)
        out.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return out


def _order(codes: list[str]) -> list[str]:
    rank = {code: index for index, code in enumerate(NRT_ORDER)}
    return sorted(codes, key=lambda code: rank.get(code, len(rank)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Resumable multi-day FIRMS backfill.")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--chunk-days", type=int, default=5)
    parser.add_argument(
        "--sources",
        default="all",
        help="Comma-separated product codes, or 'all' for every registered product",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging()

    if args.start > args.end:
        print("start must be on or before end", file=sys.stderr)
        return 2

    codes = (
        [source.code for source in FIRMS_SOURCES]
        if args.sources == "all"
        else [code.strip() for code in args.sources.split(",") if code.strip()]
    )
    unknown = [code for code in codes if get_source(code) is None]
    if unknown:
        print(f"unknown source(s): {unknown}", file=sys.stderr)
        return 2
    codes = _order(codes)

    windows = chunks(args.start, args.end, max(1, min(args.chunk_days, 5)))
    total_requests = len(windows) * len(codes)
    print(
        f"Backfill {args.start} -> {args.end}: {len(windows)} window(s) × "
        f"{len(codes)} source(s) = {total_requests} request(s)"
    )
    if args.dry_run:
        for start, end in windows:
            print(f"  window {start} -> {end}")
        return 0

    started = time.perf_counter()
    totals = {"received": 0, "inserted": 0, "rejected": 0, "failed": 0, "skipped": 0}
    per_source: dict[str, dict[str, int]] = {}
    done = 0

    for start, end in windows:
        for code in codes:
            done += 1
            began = time.perf_counter()
            try:
                result = ingest_range(code, start_date=start, end_date=end, tile=WORLD)
                status = result.status
            except Exception as error:  # noqa: BLE001 - one source must not abort the run
                logger.exception("backfill_chunk_failed", source=code, start=str(start))
                totals["failed"] += 1
                print(f"  [{done}/{total_requests}] {code} {start}..{end} FAILED: {error}")
                continue

            elapsed = time.perf_counter() - began
            source_totals = per_source.setdefault(
                code, {"received": 0, "inserted": 0, "rejected": 0}
            )
            source_totals["received"] += result.records_received
            source_totals["inserted"] += result.records_inserted
            source_totals["rejected"] += result.records_rejected
            if result.status == "failed":
                totals["failed"] += 1
            totals["received"] += result.records_received
            totals["inserted"] += result.records_inserted
            totals["rejected"] += result.records_rejected
            totals["skipped"] += result.partitions_skipped

            done_fraction = done / total_requests
            overall = time.perf_counter() - started
            eta = (overall / done_fraction) - overall if done_fraction > 0 else 0.0
            print(
                f"  [{done}/{total_requests}] {code} {start}..{end} "
                f"{status} +{result.records_inserted:,} "
                f"({result.partitions_skipped} skipped, {elapsed:.0f}s, ETA {eta / 60:.0f}m)"
            )

    overall = time.perf_counter() - started
    if totals["inserted"]:
        from app.db.session import session_scope
        from app.services.rollups import refresh_rollup

        print("\nRefreshing the daily activity rollup ...")
        with session_scope() as session:
            refreshed = refresh_rollup(session)
        print("rollup refreshed" if refreshed else "rollup not available (SQLite)")

    print("\nSummary")
    for code in codes:
        values = per_source.get(code)
        if values is None:
            print(f"  {code:<20} no data")
            continue
        print(
            f"  {code:<20} inserted {values['inserted']:>9,} "
            f"rejected {values['rejected']:>5,}"
        )
    print(
        f"\ninserted {totals['inserted']:,} rows, rejected {totals['rejected']:,}, "
        f"{totals['skipped']} partition(s) already complete, "
        f"{totals['failed']} failure(s) in {overall / 60:.1f} min"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
