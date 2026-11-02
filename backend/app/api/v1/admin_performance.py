"""Processing and storage telemetry.

Answers "is the platform healthy and where is the pressure?" from measurements
only: database size and per-table sizes, rollup freshness, the last ingestion
throughput, process memory/CPU and the in-process cache. Nothing is estimated
when a measurement is unavailable — the field is null and a warning explains it.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.cache import cache_stats
from app.db.dialect import dialect_name
from app.db.models import FireObservation, IngestionRun
from app.db.session import get_session
from app.services.rollups import rollup_status

router = APIRouter(prefix="/admin", tags=["admin"])

#: A single API process should stay well below this; above it the device is at risk.
RSS_WARN_BYTES = 900 * 1024 * 1024
#: A rollup older than the newest observation delays every dashboard read.
ROLLUP_LAG_WARN_DAYS = 2


def _human_bytes(value: int | None) -> str | None:
    if value is None:
        return None
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return None


def _database_block(session: Session) -> dict[str, Any]:
    dialect = dialect_name(session)
    if dialect != "postgresql":
        try:
            path = get_settings_path()
            size = os.path.getsize(path) if path and os.path.exists(path) else None
        except OSError:
            size = None
        return {
            "dialect": dialect,
            "size_bytes": size,
            "size_human": _human_bytes(size),
            "tables": [],
            "connections": None,
            "statement_timeout_ms": None,
        }

    size = session.scalar(text("SELECT pg_database_size(current_database())"))
    connections = session.scalar(
        text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
    )
    timeout = session.scalar(text("SHOW statement_timeout"))
    tables = session.execute(
        text(
            """
            SELECT c.relname,
                   pg_total_relation_size(c.oid) AS bytes,
                   c.reltuples::bigint AS estimated_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'm')
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 12
            """
        )
    ).all()
    return {
        "dialect": dialect,
        "size_bytes": int(size or 0),
        "size_human": _human_bytes(int(size or 0)),
        "connections": int(connections or 0),
        "statement_timeout_ms": timeout,
        "tables": [
            {
                "name": row.relname,
                "size_bytes": int(row.bytes),
                "size_human": _human_bytes(int(row.bytes)),
                "estimated_rows": int(row.estimated_rows or 0),
            }
            for row in tables
        ],
    }


def get_settings_path() -> str | None:
    from app.core.config import get_settings

    url = get_settings().database_url
    if url.startswith("sqlite"):
        return url.split("///", 1)[-1]
    return None


def _ingestion_block(session: Session) -> dict[str, Any]:
    run = session.scalars(
        select(IngestionRun)
        .where(IngestionRun.status == "succeeded")
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    ).first()
    if run is None:
        return {"last_run": None, "throughput_rows_per_second": None}
    duration = None
    if run.completed_at and run.started_at:
        duration = (run.completed_at - run.started_at).total_seconds()
    throughput = (
        round(run.records_inserted / duration, 2)
        if duration and duration > 0 and run.records_inserted
        else None
    )
    return {
        "last_run": {
            "source_code": run.source.source_code if run.source else None,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_seconds": round(duration, 2) if duration is not None else None,
            "records_received": run.records_received,
            "records_inserted": run.records_inserted,
            "records_rejected": run.records_rejected,
        },
        "throughput_rows_per_second": throughput,
    }


def _process_block() -> dict[str, Any]:
    process = psutil.Process()
    with process.oneshot():
        return {
            "pid": process.pid,
            "rss_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": process.cpu_percent(interval=0.0),
            "threads": process.num_threads(),
            "system_memory_used_percent": psutil.virtual_memory().percent,
        }


@router.get("/performance", summary="Processing, storage and cache telemetry")
def performance(session: Session = Depends(get_session)) -> dict[str, Any]:
    database = _database_block(session)
    rollups = rollup_status(session)
    ingestion = _ingestion_block(session)
    process = _process_block()
    caches = cache_stats()

    latest_observation = session.scalar(select(func.max(FireObservation.acquired_at)))
    warnings: list[str] = []

    if process["rss_mb"] * 1024 * 1024 > RSS_WARN_BYTES:
        warnings.append(
            f"API process RSS is {process['rss_mb']} MB; restart the worker if it keeps growing."
        )
    if database["size_bytes"] and database["size_bytes"] > 20 * 1024**3:
        warnings.append(
            "Database exceeds 20 GB. Most of it is raw payload duplication; see "
            "docs/operations.md for the verified pruning procedure."
        )
    if rollups.get("available") and rollups.get("latest_day"):
        from datetime import date

        latest = date.fromisoformat(rollups["latest_day"])
        if latest_observation is not None:
            observed_day = latest_observation.date()
            if (observed_day - latest).days > ROLLUP_LAG_WARN_DAYS:
                warnings.append(
                    f"Rollups end at {latest} but observations reach {observed_day}; "
                    "run refresh_rollup()."
                )
    if not rollups.get("available"):
        warnings.append("Rollups are unavailable on this dialect; dashboards use live scans.")

    return {
        "generated_at": datetime.now(UTC),
        "database": database,
        "rollups": rollups,
        "ingestion": ingestion,
        "process": process,
        "cache": caches,
        "latest_observation_at": latest_observation,
        "warnings": warnings,
        "notes": [
            "Counts are detections, not fires.",
            "Rollups are tables and are refreshed incrementally per ingested window.",
        ],
    }
