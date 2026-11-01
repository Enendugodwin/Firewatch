"""Progress bar for a running (or finished) backfill.

Partitions are the source of truth: each (product, 5-day window) is one unit, so
completed/total is exact rather than estimated. Works while the backfill runs:

    python -m scripts.backfill_status --start 2026-09-02 --end 2026-10-31
    python -m scripts.backfill_status --start 2026-09-02 --end 2026-10-31 --watch
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.db.models import DataSource, IngestionPartition
from app.db.session import session_scope

BAR_WIDTH = 40


def _windows(start: date, end: date, size: int) -> list[date]:
    out: list[date] = []
    cursor = start
    while cursor <= end:
        out.append(cursor)
        cursor = cursor + timedelta(days=size)
    return out


def _bar(fraction: float) -> str:
    filled = int(round(max(0.0, min(1.0, fraction)) * BAR_WIDTH))
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


def snapshot(start: date, end: date, chunk_days: int, sources: int) -> str:
    windows = set(_windows(start, end, chunk_days))
    expected = len(windows) * sources

    with session_scope() as session:
        rows = session.execute(
            select(
                DataSource.source_code,
                IngestionPartition.status,
                func.count(),
                func.sum(IngestionPartition.records_received),
            )
            .join(DataSource, DataSource.id == IngestionPartition.source_id)
            .where(IngestionPartition.date_start.in_(sorted(windows)))
            .group_by(DataSource.source_code, IngestionPartition.status)
        ).all()

        timestamps = session.execute(
            select(IngestionPartition.created_at, IngestionPartition.updated_at).where(
                IngestionPartition.date_start >= start,
                IngestionPartition.date_start <= end,
            )
        ).all()

        # Only the current burst counts. Chunks land every minute or two, so
        # anything updated more than three hours ago belongs to an earlier run and
        # would otherwise make the rate look absurdly slow.
        cutoff = datetime.now(UTC) - timedelta(hours=3)
        recent = [
            (created, updated)
            for created, updated in timestamps
            if updated is not None
            and (updated if updated.tzinfo else updated.replace(tzinfo=UTC)) >= cutoff
        ]
        started_at = min((entry[0] for entry in recent), default=None)
        last_activity = max((entry[1] for entry in recent if entry[1] is not None), default=None)

        per_source: dict[str, dict[str, int]] = {}
        for code, status, count, records in rows:
            entry = per_source.setdefault(code, {"succeeded": 0, "other": 0, "rows": 0})
            if status == "succeeded":
                entry["succeeded"] += int(count)
            else:
                entry["other"] += int(count)
            entry["rows"] += int(records or 0)

    completed = sum(entry["succeeded"] for entry in per_source.values())
    failed = sum(entry["other"] for entry in per_source.values())
    inserted = sum(entry["rows"] for entry in per_source.values())
    fraction = min(1.0, completed / expected) if expected else 0.0

    elapsed = ""
    eta = ""
    if started_at is not None and completed:
        now = datetime.now(UTC)
        begin = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
        last = last_activity if last_activity and last_activity.tzinfo else last_activity
        reference = min(now, last.replace(tzinfo=UTC)) if last else now
        minutes = max(0.1, (reference - begin).total_seconds() / 60)
        rate = completed / minutes
        remaining = expected - completed
        elapsed = f"  {minutes:.0f}m elapsed"
        if rate > 0 and remaining > 0:
            eta = f"  ~{remaining / rate:.0f}m left"

    lines = [
        f"Backfill {start} -> {end}  ({len(windows)} windows x {sources} sources)",
        f"{_bar(fraction)}  {completed}/{expected}  {fraction * 100:5.1f}%"
        + (f"  failed {failed}" if failed else "")
        + f"  rows {inserted:,}{elapsed}{eta}",
    ]
    for code, entry in sorted(per_source.items()):
        done = entry["succeeded"]
        lines.append(
            f"  {code:<20} {_bar(done / len(windows))} {done}/{len(windows)}"
            f"  {entry['rows']:>10,} rows"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill progress from partitions.")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--chunk-days", type=int, default=5)
    parser.add_argument("--sources", type=int, default=8)
    parser.add_argument("--watch", action="store_true", help="refresh until complete")
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()

    if not args.watch:
        print(snapshot(args.start, args.end, args.chunk_days, args.sources))
        return 0

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        text = snapshot(args.start, args.end, args.chunk_days, args.sources)
        print(text)
        print("\nCtrl+C to stop watching (the backfill keeps running).")
        current = text.splitlines()[1]
        done, total = current.split("  ")[1].split("/")
        if int(done) >= int(total):
            print("\nBackfill complete.")
            return 0
        try:
            time.sleep(max(2, args.interval))
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
