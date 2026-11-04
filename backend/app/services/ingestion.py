"""Ingestion orchestration: retrieve, retain raw payloads, normalize, persist.

Every unit of work is a (source, tile, date window) partition recorded in
``ingestion_partitions``. A re-run skips partitions already marked succeeded, so
a backfill can be stopped and resumed without duplicating records or losing
provenance.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
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
    AvailabilityWindow,
    FirmsAuthError,
    FirmsClient,
    FirmsError,
    FirmsResponse,
)
from app.services.firms.tiles import WORLD, Tile, date_windows, window_days
from app.services.normalization import NormalizationError, normalize_row
from app.services.sources import get_source

logger = get_logger(__name__)

#: Coverage is stable for the life of a process; one lookup per product is enough.
_COVERAGE_CACHE: dict[str, AvailabilityWindow | None] = {}


def _product_coverage(
    client: FirmsClient, source_code: str
) -> AvailabilityWindow | None:
    if source_code not in _COVERAGE_CACHE:
        try:
            _COVERAGE_CACHE[source_code] = client.fetch_availability(source_code)
        except FirmsError:
            _COVERAGE_CACHE[source_code] = None
    return _COVERAGE_CACHE[source_code]


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


def _relax_statement_timeout(session: Session) -> None:
    """Bulk COPY/INSERT needs longer than the interactive read timeout.

    Connections default to a 60 s ``statement_timeout`` so a runaway analytical
    query cannot pin a worker. A global four-day VIIRS window is hundreds of
    thousands of rows and legitimately exceeds that; without this override the
    insert is cancelled and the API returns a 500.
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    timeout_ms = max(0, int(get_settings().ingestion_statement_timeout_ms))
    session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))


def _bulk_insert(
    session: Session, model, rows: list[dict], *, conflict_columns: tuple[str, ...]
) -> int:
    """
    Insert many rows with duplicate protection, as fast as the engine allows.

    PostgreSQL takes a COPY into a temporary table followed by one
    ``INSERT … SELECT … ON CONFLICT DO NOTHING``: a single round trip per batch,
    which is roughly an order of magnitude faster than row-at-a-time inserts.
    SQLite uses a chunked executemany with the same conflict rule.
    """
    if not rows:
        return 0

    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return _copy_insert(session, model, rows, conflict_columns)
    return _executemany_insert(session, model, rows, conflict_columns)


def _executemany_insert(
    session: Session, model, rows: list[dict], conflict_columns: tuple[str, ...]
) -> int:
    from sqlalchemy import insert as plain_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    statement: Any = plain_insert(model)
    if session.get_bind().dialect.name == "sqlite":
        statement = sqlite_insert(model).on_conflict_do_nothing(
            index_elements=list(conflict_columns)
        )
    try:
        result = session.execute(statement.returning(model.id), rows)
        return len(result.fetchall())
    except Exception:  # pragma: no cover - RETURNING unsupported path
        session.execute(statement, rows)
        return len(rows)


def _copy_insert(
    session: Session, model, rows: list[dict], conflict_columns: tuple[str, ...]
) -> int:
    from psycopg.types.json import Jsonb

    table = model.__table__
    # Rows may omit the primary key (it is normally assigned in Python); COPY
    # needs it, so supply one rather than violating the not-null constraint.
    if "id" in table.columns and "id" not in rows[0]:
        for row in rows:
            row.setdefault("id", uuid.uuid4())
    columns = [column.name for column in table.columns if column.name in rows[0]]
    staging = f"_stage_{table.name}"
    column_list = ", ".join(columns)

    connection = session.connection()
    dbapi = connection.connection.driver_connection
    assert dbapi is not None  # a live session always has a DBAPI connection
    dbapi.execute(
        f"CREATE TEMP TABLE {staging} (LIKE {table.name} INCLUDING DEFAULTS) ON COMMIT DROP"
    )

    def adapt(column_name: str, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return Jsonb(value)
        return value

    with dbapi.cursor() as cursor:
        with cursor.copy(f"COPY {staging} ({column_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row([adapt(name, row.get(name)) for name in columns])
        cursor.execute(
            f"INSERT INTO {table.name} ({column_list}) "
            f"SELECT {column_list} FROM {staging} ON CONFLICT DO NOTHING"
        )
        inserted = int(cursor.rowcount or 0)
        cursor.execute(f"DROP TABLE IF EXISTS {staging}")
    return inserted


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

    raw_rows: list[dict] = []
    fire_rows: list[dict] = []
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

        item = normalized.to_row()
        payload = item["source_payload"]
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        raw_rows.append(
            {
                "id": uuid.uuid4(),
                "run_id": run.id,
                "source_id": source.id,
                "source_record_id": record_id,
                "content_hash": hashlib.sha256(blob).hexdigest(),
                "payload": payload,
                "is_synthetic": is_synthetic,
            }
        )
        fire_rows.append(
            {"source_id": source.id, "run_id": run.id, "is_synthetic": is_synthetic, **item}
        )

    if not fire_rows:
        return 0

    _bulk_insert(
        session,
        RawObservation,
        raw_rows,
        conflict_columns=("source_id", "source_record_id"),
    )
    inserted = _bulk_insert(
        session,
        FireObservation,
        fire_rows,
        conflict_columns=("source_id", "source_record_id"),
    )
    return inserted


def _upsert_availability(
    session: Session,
    source_id,
    window_start: date,
    window_end: date,
    had_records: bool,
    *,
    covered: bool = True,
) -> None:
    cursor = window_start
    if had_records:
        status = "available"
    elif covered:
        status = "empty"
    else:
        # The product never processed this window; "empty" would read as "quiet".
        status = "not_yet_available"
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

        # A partition is only resumable when it covers the *same* window. The
        # key is (source, tile, date_start), so a one-day run would otherwise
        # mark a four-day window as done and skip three days of data.
        if (
            partition is not None
            and resume
            and partition.status == "succeeded"
            and partition.date_end == window_end
        ):
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
            partition.date_end = window_end
        session.flush()
        _relax_statement_timeout(session)

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
        had_records = response.record_count > 0
        covered = True
        registry = get_source(source_code)
        if (
            not had_records
            and registry is not None
            and registry.is_standard_processing
        ):
            window = _product_coverage(client, source_code)
            if window is not None and getattr(window, "min_date", None) is not None:
                covered = bool(
                    window.covers(window_start) and window.covers(window_end)
                )
        _upsert_availability(
            session,
            source.id,
            window_start,
            window_end,
            had_records=had_records,
            covered=covered,
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
    """Client that replays a CSV payload — fixture loading and tests only."""

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

    Dates inside the provider's coverage window are ``available`` — they may
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
