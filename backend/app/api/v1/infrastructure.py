"""Infrastructure: storage modes, dataset inventory, cloud synchronisation.

Everything here is safe to call in local mode: with no cloud credentials the
storage provider is the filesystem, the sync preview simply reports that nothing
was uploaded, and the readiness page states that plainly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import FireObservation
from app.db.session import get_session
from app.services import datasets as dataset_service
from app.services import parquet_query
from app.services import sync as sync_service
from app.services.rollups import rollup_status
from app.storage import LocalStorage, S3Storage, StorageUnavailable, get_storage, storage_report

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


class ExportRequest(BaseModel):
    start_date: date
    end_date: date
    include_analytics: bool = True
    synthetic: bool = False


class SyncRequest(BaseModel):
    allocation_bytes: int | None = Field(default=None, ge=0)
    verify: bool = True


def _provider(settings: Settings):
    try:
        return get_storage(settings)
    except StorageUnavailable as error:
        raise AppError(
            "unavailable",
            "Object storage is not configured.",
            details={"error": str(error), "hint": "Set R2 credentials or keep STORAGE_MODE=local."},
        ) from error


@router.get("/status", summary="Deployment mode, storage and database state")
def infrastructure_status(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    report = storage_report(settings)
    if settings.database_dialect == "postgresql":
        database_size = session.scalar(text("SELECT pg_database_size(current_database())"))
        tables = session.scalar(
            text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        )
    else:
        database_size = 0
        tables = len(FireObservation.metadata.tables)
    return {
        "deployment_mode": settings.deployment_mode,
        "database_mode": settings.database_mode,
        "storage": report,
        "database": {
            "dialect": settings.database_dialect,
            "size_bytes": int(database_size or 0),
            "tables": int(tables or 0),
            "cloud_database_configured": bool(settings.cloud_database_url),
        },
        "rollups": rollup_status(session),
    }


@router.post("/storage/test", summary="Test the configured storage provider")
def storage_test(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    provider = _provider(settings)
    if isinstance(provider, S3Storage):
        result = provider.test_connection()
        result["provider"] = "s3/r2"
        return result
    if isinstance(provider, LocalStorage):
        return {
            "ok": True,
            "provider": "local",
            "root": str(provider.root),
            "free_bytes": provider.available_bytes(),
            "used_bytes": provider.used_bytes(),
        }
    return {"ok": False, "provider": provider.name}


@router.post("/export", summary="Export stored detections to Parquet")
def export_datasets(
    payload: ExportRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if payload.start_date > payload.end_date:
        raise AppError("bad_request", "start_date must be on or before end_date.")
    root = dataset_service.dataset_root(settings.local_data_directory)
    files = dataset_service.export_detections(
        session,
        root=root,
        start=payload.start_date,
        end=payload.end_date,
        synthetic=payload.synthetic,
    )
    analytics = (
        dataset_service.export_daily_analytics(session, root=root)
        if payload.include_analytics
        else None
    )
    written = files + ([analytics] if analytics else [])
    # The response describes this export; the full inventory is /datasets.
    manifest = dataset_service.manifest(written)
    inventory = dataset_service.scan_datasets(root)
    sync_service.write_local_manifest(root, dataset_service.manifest(inventory))
    return {
        "root": str(root),
        "written": len(files),
        "analytics": analytics,
        "files": files,
        "manifest": {
            "file_count": manifest["file_count"],
            "record_count": manifest["record_count"],
            "total_bytes": manifest["total_bytes"],
        },
    }


@router.get("/datasets", summary="Inventory of exported datasets")
def list_datasets(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    root = dataset_service.dataset_root(settings.local_data_directory)
    entries = dataset_service.scan_datasets(root)
    return {
        "root": str(root),
        "count": len(entries),
        "total_bytes": sum(int(entry["size_bytes"]) for entry in entries),
        "records": sum(int(entry.get("records", 0)) for entry in entries),
        "datasets": entries,
    }


@router.get("/datasets/{dataset_id}/verify", summary="Verify one Parquet dataset with DuckDB")
def verify_dataset(
    dataset_id: str, settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    root = dataset_service.dataset_root(settings.local_data_directory)
    entry = next(
        (item for item in dataset_service.scan_datasets(root) if item.get("dataset") == dataset_id),
        None,
    )
    if entry is None:
        raise AppError("not_found", "No exported dataset with that identifier.")
    path = Path(entry["local_path"])
    summary = parquet_query.summarise(path)
    return {"dataset": entry, "parquet": summary}


@router.post("/sync/preview", summary="Compare local datasets with the bucket")
def sync_preview(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    provider = _provider(settings)
    root = dataset_service.dataset_root(settings.local_data_directory)
    entries = dataset_service.scan_datasets(root)
    return sync_service.preview(provider, entries)


@router.post("/sync", summary="Upload selected datasets and verify them")
def run_sync(
    payload: SyncRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    provider = _provider(settings)
    root = dataset_service.dataset_root(settings.local_data_directory)
    entries = dataset_service.scan_datasets(root)
    if not entries:
        raise AppError(
            "bad_request",
            "No exported datasets to synchronise.",
            details={"hint": "Run POST /infrastructure/export first."},
        )
    allocation = payload.allocation_bytes or settings.r2_allocation_bytes
    report = sync_service.sync(
        provider, entries, allocation_bytes=allocation, verify=payload.verify
    )
    sync_service.write_local_manifest(
        root,
        {
            "manifest_version": "firewatch-manifest-v1",
            "report": report,
        },
    )
    return report


@router.get("/parquet/sensors", summary="Per-sensor totals from the Parquet export (DuckDB)")
def parquet_sensor_totals(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    root = dataset_service.dataset_root(settings.local_data_directory)
    try:
        totals = parquet_query.sensor_totals(root)
    except Exception as error:  # noqa: BLE001 - DuckDB raises its own error types
        raise AppError(
            "bad_request",
            "No Parquet datasets are available to query.",
            details={"error": str(error)},
        ) from error
    return {"sensors": totals, "engine": "duckdb"}
