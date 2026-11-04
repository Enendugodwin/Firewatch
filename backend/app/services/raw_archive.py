"""Raw-payload retention and the export-before-delete workflow.

Raw payloads are provenance, not analysis. The canonical observations, matches,
events and rollups are what the console reads, so payloads can be exported and
then removed without changing a single number on screen.

Two rules keep deletion honest:

* an export records the exact row count and SHA-256 of the CSV it produced;
* a delete is refused unless the caller presents that checksum and the range
  still holds exactly the exported number of rows.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.dialect import dialect_name
from app.db.models import DataSource, RawExport, RawObservation

CSV_HEADER = (
    "source_code",
    "source_record_id",
    "content_hash",
    "retrieved_at",
    "payload",
)


def acq_date_expr():
    """The acquisition day, taken from the retained source row."""
    return func.substr(RawObservation.payload["acq_date"].as_string(), 1, 10)


def export_root(settings: Settings) -> Path:
    root = Path(settings.local_data_directory) / "raw_exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _today() -> date:
    return datetime.now(UTC).date()


def _row_count(session: Session, start: date, end: date) -> int:
    expr = acq_date_expr()
    return int(
        session.scalar(
            select(func.count())
            .select_from(RawObservation)
            .where(expr >= start.isoformat(), expr <= end.isoformat())
        )
        or 0
    )


def inventory(session: Session, settings: Settings) -> dict[str, Any]:
    """Per-day payload footprint, plus the policy the console should show."""
    expr = acq_date_expr()
    day_rows = session.execute(
        select(expr.label("day"), func.count())
        .select_from(RawObservation)
        .group_by(expr)
        .order_by(expr.desc())
    ).all()

    sizes: dict[str, int] = {}
    if dialect_name(session) == "postgresql":
        for day, size in session.execute(
            select(expr.label("day"), func.sum(func.pg_column_size(RawObservation.payload)))
            .select_from(RawObservation)
            .group_by(expr)
        ).all():
            sizes[day] = int(size or 0)

    total_rows = sum(count for _, count in day_rows)
    today = _today()
    export_cutoff = today - timedelta(days=settings.raw_export_min_age_days)
    retention_cutoff = today - timedelta(days=settings.raw_retention_days)

    days = [
        {
            "day": day,
            "rows": int(count),
            "payload_bytes": sizes.get(day),
            "exportable": day is not None and day <= export_cutoff.isoformat(),
            "past_retention": day is not None and day < retention_cutoff.isoformat(),
        }
        for day, count in day_rows
        if day is not None
    ]

    return {
        "policy": {
            "retention_days": settings.raw_retention_days,
            "retention_cutoff": retention_cutoff.isoformat(),
            "export_min_age_days": settings.raw_export_min_age_days,
            "export_cutoff": export_cutoff.isoformat(),
            "export_max_days": settings.raw_export_max_days,
        },
        "totals": {
            "rows": total_rows,
            "payload_bytes": sum(sizes.values()) if sizes else None,
            "days": len(days),
            "past_retention_rows": sum(d["rows"] for d in days if d["past_retention"]),
        },
        "days": days,
    }


class _HashingSink(io.RawIOBase):
    """Forward bytes to the gzip stream while hashing the uncompressed CSV."""

    def __init__(self, target: Any, digest: Any) -> None:
        self._target = target
        self._digest = digest

    def writable(self) -> bool:  # noqa: D102 - io protocol
        return True

    def write(self, data: Any) -> int:  # noqa: D102 - io protocol
        self._digest.update(data)
        return self._target.write(data)


def create_export(
    session: Session,
    settings: Settings,
    *,
    start_date: date,
    end_date: date,
) -> RawExport:
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    span = (end_date - start_date).days + 1
    if span > settings.raw_export_max_days:
        raise ValueError(f"export at most {settings.raw_export_max_days} days at a time")
    latest_exportable = _today() - timedelta(days=settings.raw_export_min_age_days)
    if end_date > latest_exportable:
        raise ValueError(
            "only payloads older than "
            f"{settings.raw_export_min_age_days} days can be exported "
            f"(latest {latest_exportable.isoformat()})"
        )

    expr = acq_date_expr()
    statement = (
        select(
            DataSource.source_code,
            RawObservation.source_record_id,
            RawObservation.content_hash,
            RawObservation.retrieved_at,
            RawObservation.payload,
        )
        .join(DataSource, DataSource.id == RawObservation.source_id)
        .where(expr >= start_date.isoformat(), expr <= end_date.isoformat())
        .order_by(expr, DataSource.source_code, RawObservation.source_record_id)
    )

    root = export_root(settings)
    filename = f"raw_{start_date}_{end_date}_{uuid.uuid4().hex[:8]}.csv.gz"
    path = root / filename
    digest = hashlib.sha256()
    rows = 0

    with path.open("wb") as handle:
        gz = gzip.GzipFile(fileobj=handle, mode="wb", mtime=0)
        sink = _HashingSink(gz, digest)
        text = io.TextIOWrapper(io.BufferedWriter(sink), encoding="utf-8", newline="")
        writer = csv.writer(text)
        writer.writerow(CSV_HEADER)
        for source_code, record_id, content_hash, retrieved_at, payload in session.execute(
            statement
        ).yield_per(5_000):
            writer.writerow(
                (
                    source_code,
                    record_id,
                    content_hash,
                    retrieved_at.isoformat() if retrieved_at else "",
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                )
            )
            rows += 1
        text.flush()
        text.detach()
        gz.close()

    if rows == 0:
        path.unlink(missing_ok=True)
        raise ValueError("no raw payloads exist in that range")

    record = RawExport(
        start_date=start_date,
        end_date=end_date,
        rows=rows,
        size_bytes=path.stat().st_size,
        sha256=digest.hexdigest(),
        path=filename,
        status="ready",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def delete_export(
    session: Session,
    *,
    export_id: uuid.UUID,
    confirm_sha256: str,
) -> dict[str, Any]:
    record = session.get(RawExport, export_id)
    if record is None:
        raise LookupError("export not found")
    if record.status != "ready":
        raise ValueError("that range has already been deleted")
    if confirm_sha256.strip().lower() != record.sha256.lower():
        raise ValueError("checksum does not match the export")

    current = _row_count(session, record.start_date, record.end_date)
    if current != record.rows:
        raise ValueError(
            "the raw rows changed since the export "
            f"(exported {record.rows:,}, found {current:,}); export again first"
        )

    expr = acq_date_expr()
    result = session.execute(
        delete(RawObservation).where(
            expr >= record.start_date.isoformat(),
            expr <= record.end_date.isoformat(),
        )
    )
    deleted = int(getattr(result, "rowcount", 0) or 0)
    record.status = "deleted"
    record.deleted_at = datetime.now(UTC)
    record.rows_deleted = deleted
    session.commit()
    return {"export_id": str(record.id), "rows_deleted": deleted}


def retention_preview(
    session: Session, settings: Settings, *, days: int | None = None
) -> dict[str, Any]:
    days = settings.raw_retention_days if days is None else days
    if days < 1:
        raise ValueError("retention must keep at least one day")
    cutoff = _today() - timedelta(days=days)
    expr = acq_date_expr()
    rows = int(
        session.scalar(
            select(func.count())
            .select_from(RawObservation)
            .where(expr < cutoff.isoformat())
        )
        or 0
    )
    oldest = session.scalar(select(func.min(expr)).select_from(RawObservation))
    return {"days": days, "cutoff": cutoff.isoformat(), "rows": rows, "oldest_day": oldest}


def run_retention(
    session: Session, settings: Settings, *, days: int | None = None, apply: bool = False
) -> dict[str, Any]:
    preview = retention_preview(session, settings, days=days)
    if not apply:
        return {**preview, "applied": False}

    expr = acq_date_expr()
    result = session.execute(delete(RawObservation).where(expr < preview["cutoff"]))
    deleted = int(getattr(result, "rowcount", 0) or 0)
    session.commit()
    return {**preview, "applied": True, "rows_deleted": deleted}
