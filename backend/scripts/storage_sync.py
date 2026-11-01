"""Command-line dataset export and cloud synchronisation.

    python -m scripts.storage_sync export --start 2026-09-02 --end 2026-10-31
    python -m scripts.storage_sync scan
    python -m scripts.storage_sync preview
    python -m scripts.storage_sync sync
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import session_scope
from app.services import datasets as dataset_service
from app.services import sync as sync_service
from app.storage import StorageUnavailable, get_storage


def main() -> int:
    parser = argparse.ArgumentParser(description="FIREWATCH X dataset export and sync.")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="write Parquet datasets for a date range")
    export.add_argument("--start", required=True, type=date.fromisoformat)
    export.add_argument("--end", required=True, type=date.fromisoformat)
    export.add_argument("--synthetic", action="store_true")

    sub.add_parser("scan", help="list exported datasets")
    sub.add_parser("preview", help="compare local datasets with the configured storage")
    sync_parser = sub.add_parser("sync", help="upload and verify missing or changed datasets")
    sync_parser.add_argument("--allocation-bytes", type=int, default=None)

    args = parser.parse_args()
    configure_logging()
    settings = get_settings()
    root = dataset_service.dataset_root(settings.local_data_directory)

    if args.command == "export":
        with session_scope() as session:
            files = dataset_service.export_detections(
                session, root=root, start=args.start, end=args.end, synthetic=args.synthetic
            )
            analytics = dataset_service.export_daily_analytics(session, root=root)
        manifest = dataset_service.manifest(dataset_service.scan_datasets(root))
        sync_service.write_local_manifest(root, manifest)
        print(f"exported {len(files)} file(s) for {args.start}..{args.end}")
        for item in files:
            print(
                f"  {item['dataset']:<28} {item['records']:>10,} rows  "
                f"{item['size_bytes'] / 1e6:.1f} MB"
            )
        if analytics:
            print(f"  analytics/daily              {analytics['records']:>10,} rows")
        print(f"manifest: {manifest['file_count']} files, {manifest['record_count']:,} records")
        return 0

    entries = dataset_service.scan_datasets(root)
    if args.command == "scan":
        print(f"{len(entries)} dataset(s) under {root}")
        for item in entries:
            megabytes = item["size_bytes"] / 1e6
            print(
                f"  {item['dataset']:<28} {item['records']:>10,} rows  {megabytes:.1f} MB"
            )
        return 0

    try:
        provider = get_storage(settings)
    except StorageUnavailable as error:
        print(f"storage unavailable: {error}", file=sys.stderr)
        return 2

    if args.command == "preview":
        plan = sync_service.preview(provider, entries)
        summary = {key: plan[key] for key in ("counts", "upload_bytes", "remote_used_bytes")}
        print(json.dumps(summary, indent=2))
        return 0

    allocation = args.allocation_bytes or settings.r2_allocation_bytes
    report = sync_service.sync(provider, entries, allocation_bytes=allocation)
    print(
        json.dumps(
            {k: report.get(k) for k in ("status", "uploaded", "skipped", "failed", "verified")},
            indent=2,
        )
    )
    return 0 if report.get("status") in {"ok", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
