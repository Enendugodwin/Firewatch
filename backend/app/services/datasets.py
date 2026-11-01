"""Dataset export and inventory.

Large historical data lives as Parquet, partitioned by year and month, written by
Polars with Zstandard compression. Each file gets a small JSON sidecar with the
facts a deployment manifest needs (coverage, record count, versions), so scanning
a dataset never has to read the whole file back.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import FireObservation
from app.storage.base import sha256_file

SCHEMA_VERSION = "detections-parquet-v1"

#: Explicit types: inference over millions of rows with sparse columns is both
#: slow and wrong (a null run makes Polars guess the wrong integer width).
EXPORT_SCHEMA: dict[str, Any] = {
    "id": pl.String,
    "sensor": pl.String,
    "satellite": pl.String,
    "acquired_at": pl.Datetime(time_zone="UTC"),
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "confidence_raw": pl.Int64,
    "confidence_category": pl.String,
    "brightness_temperature": pl.Float64,
    "frp_mw": pl.Float64,
    "scan_km": pl.Float64,
    "track_km": pl.Float64,
    "daynight": pl.String,
    "source_code": pl.String,
    "source_product": pl.String,
    "processing_version": pl.String,
    "is_synthetic": pl.Boolean,
}
PROCESSING_VERSION = "export-v1"
EXPORT_COLUMNS = (
    "id",
    "sensor",
    "satellite",
    "acquired_at",
    "latitude",
    "longitude",
    "confidence_raw",
    "confidence_category",
    "brightness_temperature",
    "frp_mw",
    "scan_km",
    "track_km",
    "daynight",
    "source_code",
    "source_product",
    "processing_version",
    "is_synthetic",
)


def dataset_root(base: str | Path) -> Path:
    root = Path(base) / "firewatch-data"
    for child in ("raw", "harmonized", "analytics", "manifests", "exports", "temporary"):
        (root / child).mkdir(parents=True, exist_ok=True)
    return root


def _month_ranges(start: date, end: date) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    cursor = start.replace(day=1)
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        month_end = next_month.fromordinal(next_month.toordinal() - 1)
        ranges.append((max(cursor, start), min(month_end, end)))
        cursor = next_month
    return ranges


def export_detections(
    session: Session,
    *,
    root: Path,
    start: date,
    end: date,
    synthetic: bool = False,
) -> list[dict[str, Any]]:
    """
    Write one Parquet file per month of stored detections. Streams from the
    database in month-sized batches and never holds more than one month in
    memory; the projection is fixed and narrow.
    """
    written: list[dict[str, Any]] = []
    for month_start, month_end in _month_ranges(start, end):
        start_dt = datetime.combine(month_start, datetime.min.time())
        end_dt = datetime.combine(
            month_end.fromordinal(month_end.toordinal() + 1), datetime.min.time()
        )
        statement = (
            select(
                FireObservation.id,
                FireObservation.sensor,
                FireObservation.satellite,
                FireObservation.acquired_at,
                FireObservation.latitude,
                FireObservation.longitude,
                FireObservation.confidence_raw,
                FireObservation.confidence_category,
                FireObservation.brightness_temperature,
                FireObservation.frp_mw,
                FireObservation.scan_km,
                FireObservation.track_km,
                FireObservation.daynight,
                FireObservation.source_code,
                FireObservation.source_product,
                FireObservation.processing_version,
                FireObservation.is_synthetic,
            )
            .where(
                FireObservation.acquired_at >= start_dt,
                FireObservation.acquired_at < end_dt,
                FireObservation.is_synthetic.is_(synthetic),
            )
            .order_by(FireObservation.acquired_at)
        )
        rows = session.execute(statement).mappings()
        records = []
        for row in rows:
            record = dict(row)
            record["id"] = str(record["id"])
            records.append(record)
        if not records:
            continue
        frame = pl.DataFrame(records, schema=EXPORT_SCHEMA, strict=False)
        if frame.height == 0:
            continue

        base = "harmonized" if not synthetic else "harmonized-synthetic"
        target_dir = root / base / f"year={month_start.year}" / f"month={month_start.month:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "detections.parquet"
        frame.write_parquet(target, compression="zstd", statistics=True)

        entry = {
            "dataset": (
                f"detections-{month_start.year}-{month_start.month:02d}"
                + ("-synthetic" if synthetic else "")
            ),
            "path": target.relative_to(root).as_posix(),
            "kind": "harmonized",
            "sensor": "all",
            "coverage_start": month_start.isoformat(),
            "coverage_end": month_end.isoformat(),
            "partition": f"year={month_start.year}/month={month_start.month:02d}",
            "records": frame.height,
            "size_bytes": target.stat().st_size,
            "checksum": sha256_file(target),
            "schema_version": SCHEMA_VERSION,
            "processing_version": PROCESSING_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "synthetic": synthetic,
        }
        (target_dir / "detections.meta.json").write_text(
            json.dumps(entry, indent=2), encoding="utf-8"
        )
        written.append(entry)
    return written


def export_daily_analytics(session: Session, *, root: Path) -> dict[str, Any] | None:
    """Export the daily rollup as one Parquet file for offline analysis."""
    from app.db.dialect import dialect_name

    if dialect_name(session) == "postgresql":
        rows = session.execute(
            text(
                "SELECT day, sensor, confidence_category, daynight, satellite, source_code, "
                "detections, frp_sum_mw, frp_max_mw FROM daily_activity ORDER BY day"
            )
        ).mappings()
    else:
        rows = session.execute(
            select(
                FireObservation.sensor,
                FireObservation.confidence_category,
                FireObservation.daynight,
                FireObservation.satellite,
                FireObservation.source_code,
            ).limit(0)
        ).mappings()
    records = [dict(row) for row in rows]
    if not records:
        return None
    frame = pl.DataFrame(records, infer_schema_length=None)

    target = root / "analytics" / "daily" / "daily_activity.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(target, compression="zstd", statistics=True)

    entry = {
        "dataset": "analytics-daily",
        "path": target.relative_to(root).as_posix(),
        "kind": "analytics",
        "sensor": "all",
        "coverage_start": str(frame["day"].min()),
        "coverage_end": str(frame["day"].max()),
        "partition": "daily",
        "records": frame.height,
        "size_bytes": target.stat().st_size,
        "checksum": sha256_file(target),
        "schema_version": "analytics-parquet-v1",
        "processing_version": PROCESSING_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "synthetic": False,
    }
    target.with_suffix(".meta.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def scan_datasets(root: Path) -> list[dict[str, Any]]:
    """Inventory every documented Parquet file under the data root."""
    entries: list[dict[str, Any]] = []
    for meta_path in sorted(root.rglob("*.meta.json")):
        try:
            entry = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        parquet = root / entry["path"]
        if not parquet.is_file():
            continue
        entry["size_bytes"] = parquet.stat().st_size
        # Recompute the checksum: a file could have been replaced since export.
        entry["checksum"] = sha256_file(parquet)
        entry["local_path"] = str(parquet)
        entries.append(entry)
    return entries


def manifest(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(entries)
    return {
        "manifest_version": "firewatch-manifest-v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "processing_version": PROCESSING_VERSION,
        "file_count": len(items),
        "record_count": sum(int(item.get("records", 0)) for item in items),
        "total_bytes": sum(int(item.get("size_bytes", 0)) for item in items),
        "datasets": [
            {
                "dataset": item.get("dataset"),
                "dataset_id": item.get("dataset"),
                "source": item.get("source", "NASA FIRMS"),
                "sensor": item.get("sensor"),
                "coverage_start": item.get("coverage_start"),
                "coverage_end": item.get("coverage_end"),
                "partition": item.get("partition"),
                "records": item.get("records"),
                "size_bytes": item.get("size_bytes"),
                "checksum": item.get("checksum"),
                "schema_version": item.get("schema_version"),
                "processing_version": item.get("processing_version"),
                "local_path": item.get("path"),
                "cloud_object": f"firewatch-data/{item.get('path')}",
                "status": item.get("sync_status", "pending"),
            }
            for item in items
        ],
    }
