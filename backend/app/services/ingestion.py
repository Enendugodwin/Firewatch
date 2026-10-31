"""Ingestion orchestration: retrieve, retain raw payloads, normalize, persist.

Every unit of work is a (source, tile, date window) partition recorded in
``ingestion_partitions``. A re-run skips partitions already marked succeeded, so
a backfill can be stopped and resumed without duplicating records or losing
provenance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    DataSource,
    FireObservation,
    IngestionPartition,
    IngestionRun,
    RawObservation,
    SourceAvailability,
)
from app.db.session import session_scope
from app.services.firms.client import (
    FirmsAuthError,
    FirmsClient,
    FirmsError,
    FirmsResponse,
)
from app.services.firms.tiles import WORLD, Tile, date_windows, window_days
from app.services.normalization import NormalizationError, normalize_row
from app.services.sources import get_source

logger = get_logger(__name__)


@dataclass
class IngestResult:
    source_code: str
    run_id: str | None
    status: str
    records_received: int = 0
    records_inserted: int = 0
    records_rejected: int = 0
    partitions_completed: int = 0
    partitions_skipped: int = 0
    windows_failed: int = 0
    rejections: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    is_synthetic: bool = False


def build_client() -> FirmsClient:
    settings = get_settings()
    return FirmsClient(
        settings.firms_map_key,
        base_url=settings.firms_base_url,
        timeout=settings.firms_request_timeout,
        max_retries=settings.firms_max_retries,
    )


def _get_source(session: Session, source_code: str) -> DataSource:
    row = session.scalars(select(DataSource).where(DataSource.source_code == source_code)).first()
    if row is None:
        raise FirmsError(
            f"Data source {source_code!r} is not registered. Run scripts/seed_sources.py."
        )
    return row


def _existing(
    session: Session, model: type[FireObservation] | type[RawObservation], source_id, ids: list[str]
) -> set[str]:
    found: set[str] = set()
    # Keep IN lists comfortably below SQLite's bound-variable limit.
    for start in range(0, len(ids), 400):
        chunk = ids[start : start + 400]
        found.update(
            session.scalars(
                select(model.source_record_id).where(
                    model.source_id == source_id, model.source_record_id.in_(chunk)
                )
            ).all()
        )
    return found


def _store_response(
    session: Session,
    *,
    source: DataSource,
    source_code: str,
    response: FirmsResponse,
    run: IngestionRun,
    result: IngestResult,
    is_synthetic: bool,
) -> int:
    registry_source = get_source(source_code)
    if registry_source is None:
        raise FirmsError(f"Unsupported source {source_code!r}")

    accepted: list[dict] = []
    seen_in_batch: set[str] = set()

    for row in response.rows:
        try:
            normalized = normalize_row(row, registry_source)
        except NormalizationError as exc:
            result.records_rejected += 1
            key = f"{exc.field_name or 'row'}: {exc.reason}"
            result.rejections[key] = result.rejections.get(key, 0) + 1
            continue

        record_id = normalized.source_record_id
        if record_id in seen_in_batch:
            continue
        seen_in_batch.add(record_id)
        accepted.append(normalized.to_row())

    if not accepted:
        return 0

    ids = [item["source_record_id"] for item in accepted]

    existing_raw = _existing(session, RawObservation, source.id, ids)
    for item in accepted:
        if item["source_record_id"] in existing_raw:
            continue
        payload = item["source_payload"]
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        session.add(
            RawObservation(
                run_id=run.id,
                source_id=source.id,
                source_record_id=item["source_record_id"],
                content_hash=hashlib.sha256(blob).hexdigest(),
                payload=payload,
                is_synthetic=is_synthetic,
            )
        )

    existing = _existing(session, FireObservation, source.id, ids)
    inserted = 0
    for item in accepted:
        if item["source_record_id"] in existing:
            continue
        session.add(
            FireObservation(source_id=source.id, run_id=run.id, is_synthetic=is_synthetic, **item)
        )
        inserted += 1

    return inserted


def _upsert_availability(
    session: Session, source_id, window_start: date, window_end: date, had_records: bool
) -> None:
    cursor = window_start
    status = "available" if had_records else "empty"
    while cursor <= window_end:
        row = session.scalars(
            select(SourceAvailability).where(
                SourceAvailability.source_id == source_id,
                SourceAvailability.observation_date == cursor,
            )
        ).first()
        if row is None:
            session.add(
                SourceAvailability(source_id=source_id, observation_date=cursor, status=status)
            )
        elif row.status != "missing":
            # An availability check is authoritative; do not overwrite it.
            row.status = status
        cursor += timedelta(days=1)


def _ingest(
    session: Session,
    *,
    source_code: str,
    start_date: date,
    end_date: date,
    tile: Tile,
    client: FirmsClient,
    is_synthetic: bool,
    resume: bool,
) -> IngestResult:
    result = IngestResult(
        source_code=source_code, run_id=None, status="running", is_synthetic=is_synthetic
    )

    source = _get_source(session, source_code)
    run = IngestionRun(
        source_id=source.id,
        status="running",
        query_parameters={
            "tile": tile.key,
            "bbox": tile.bbox,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "synthetic": is_synthetic,
        },
        is_synthetic=is_synthetic,
    )
    session.add(run)
    session.flush()
    result.run_id = str(run.id)

    for window_start, window_end in date_windows(start_date, end_date):
        partition = session.scalars(
            select(IngestionPartition).where(
                IngestionPartition.source_id == source.id,
                IngestionPartition.tile_key == tile.key,
                IngestionPartition.date_start == window_start,
            )
        ).first()

        if partition is not None and resume and partition.status == "succeeded":
            result.partitions_skipped += 1
            result.records_received += partition.records_received
            continue

        if partition is None:
            partition = IngestionPartition(
                source_id=source.id,
                tile_key=tile.key,
                bbox=tile.bbox,
                date_start=window_start,
                date_end=window_end,
                status="running",
            )
            session.add(partition)
        else:
            partition.status = "running"
            partition.attempts += 1
        session.flush()

        try:
            response = client.fetch_area(
                source_code,
                tile.bbox,
                day_range=window_days(window_start, window_end),
                request_date=window_start,
            )
        except FirmsAuthError:
            session.rollback()
            raise
        except FirmsError as exc:
            partition.status = "failed"
            partition.error_message = str(exc)[:500]
            result.windows_failed += 1
            result.errors.append(f"{window_start.isoformat()}: {exc}")
            logger.warning(
                "ingest_window_failed",
                source=source_code,
                window=window_start.isoformat(),
                error=str(exc),
            )
            session.commit()
            continue

        result.records_received += response.record_count
        result.records_inserted += _store_response(
            session,
            source=source,
            source_code=source_code,
            response=response,
            run=run,
            result=result,
            is_synthetic=is_synthetic,
        )

        partition.records_received = response.record_count
        partition.status = "succeeded"
        partition.completed_at = datetime.now(UTC)
        partition.error_message = None
        _upsert_availability(
            session, source.id, window_start, window_end, had_records=response.record_count > 0
        )
        result.partitions_completed += 1
        session.commit()

    run.records_received = result.records_received
    run.records_inserted = result.records_inserted
    run.records_rejected = result.records_rejected
    run.completed_at = datetime.now(UTC)
    if result.windows_failed and not result.partitions_completed:
        run.status = "failed"
        result.status = "failed"
    elif result.windows_failed:
        run.status = "partial"
        result.status = "partial"
    else:
        run.status = "succeeded"
        result.status = "succeeded"
    if result.errors:
        run.error_message = "; ".join(result.errors)[:2000]
    session.commit()

    logger.info(
        "ingest_complete",
        source=source_code,
        status=result.status,
        received=result.records_received,
        inserted=result.records_inserted,
        rejected=result.records_rejected,
        partitions=result.partitions_completed,
        skipped=result.partitions_skipped,
        synthetic=is_synthetic,
    )
    return result


def ingest_range(
    source_code: str,
    *,
    start_date: date,
    end_date: date,
    tile: Tile = WORLD,
    client: FirmsClient | None = None,
    is_synthetic: bool = False,
    resume: bool = True,
    session: Session | None = None,
) -> IngestResult:
    """Ingest an inclusive date range for one source and tile."""
    client = client or build_client()
    if session is not None:
        return _ingest(
            session,
            source_code=source_code,
            start_date=start_date,
            end_date=end_date,
            tile=tile,
            client=client,
            is_synthetic=is_synthetic,
            resume=resume,
        )
    with session_scope() as own_session:
        return _ingest(
            own_session,
            source_code=source_code,
            start_date=start_date,
            end_date=end_date,
            tile=tile,
            client=client,
            is_synthetic=is_synthetic,
            resume=resume,
        )


class StaticCsvClient(FirmsClient):
    """Client that replays a CSV payload â€” fixture loading and tests only."""

    def __init__(self, csv_text: str) -> None:
        super().__init__(map_key="fixture", max_retries=1, sleep=lambda _seconds: None)
        self._csv_text = csv_text

    def fetch_area(
        self,
        source_code: str,
        bbox: str,
        day_range: int = 1,
        request_date: date | None = None,
    ) -> FirmsResponse:
        import csv
        import io

        rows = [
            {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(io.StringIO(self._csv_text))
            if row.get("latitude")
        ]
        return FirmsResponse(
            source_code=source_code,
            bbox=bbox,
            day_range=day_range,
            request_date=request_date,
            status="ok" if rows else "empty",
            rows=rows,
        )


def ingest_csv_text(
    source_code: str,
    csv_text: str,
    *,
    start_date: date,
    end_date: date,
    tile: Tile = WORLD,
    is_synthetic: bool = True,
) -> IngestResult:
    """Ingest a FIRMS-format CSV payload (used by the labelled fixture loader)."""
    return ingest_range(
        source_code,
        start_date=start_date,
        end_date=end_date,
        tile=tile,
        client=StaticCsvClient(csv_text),
        is_synthetic=is_synthetic,
    )


def sync_availability(
    source_code: str,
    *,
    start_date: date,
    end_date: date,
    client: FirmsClient | None = None,
) -> dict[str, object]:
    """
    Ask FIRMS which dates the product covers, then record one status per date.

    Dates inside the provider's coverage window are ``available`` â€” they may
    contain zero detections and that is still an observed day. Dates outside the
    window are recorded as ``before_coverage`` or ``not_yet_available`` so a gap
    is never mistaken for quiet conditions.
    """
    client = client or build_client()
    window = client.fetch_availability(source_code)
    counts: dict[str, int] = {}

    with session_scope() as session:
        source = _get_source(session, source_code)
        cursor = start_date
        while cursor <= end_date:
            status = window.classify(cursor)
            row = session.scalars(
                select(SourceAvailability).where(
                    SourceAvailability.source_id == source.id,
                    SourceAvailability.observation_date == cursor,
                )
            ).first()
            if row is None:
                session.add(
                    SourceAvailability(source_id=source.id, observation_date=cursor, status=status)
                )
            else:
                row.status = status
                row.checked_at = datetime.now(UTC)
            counts[status] = counts.get(status, 0) + 1
            cursor += timedelta(days=1)

    logger.info("availability_synced", source=source_code, **counts)
    return {
        "counts": counts,
        "coverage": {
            "min_date": window.min_date.isoformat() if window.min_date else None,
            "max_date": window.max_date.isoformat() if window.max_date else None,
            "rows": window.rows,
        },
    }
