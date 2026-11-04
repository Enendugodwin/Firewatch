"""Raw-payload retention and the admin export/delete portal.

Raw payloads are optional provenance. Everything the console shows is computed
from canonical observations, matches, events and rollups, so removing payloads
changes no analysis number. This surface exists to export the payloads for a
date range, hand the archive to an operator, and only then delete them for that
exact range.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import RawExport
from app.db.session import get_session
from app.services import raw_archive as archive

router = APIRouter(prefix="/admin/raw", tags=["admin"])


class ExportRequest(BaseModel):
    start_date: date
    end_date: date


class DeleteRequest(BaseModel):
    confirm_sha256: str


class RetentionRequest(BaseModel):
    days: int | None = None
    confirm: bool = False


def _out(record: RawExport) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "start_date": record.start_date.isoformat(),
        "end_date": record.end_date.isoformat(),
        "rows": record.rows,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
        "rows_deleted": record.rows_deleted,
    }


def _archive_error(exc: Exception) -> AppError:
    if isinstance(exc, LookupError):
        return AppError("not_found", str(exc))
    return AppError("unprocessable", str(exc))


@router.get("/inventory", summary="Raw payload footprint and retention policy")
def get_inventory(
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return archive.inventory(session, settings)


@router.get("/exports", summary="Export history")
def list_exports(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    records = session.scalars(select(RawExport).order_by(RawExport.created_at.desc())).all()
    return [_out(record) for record in records]


@router.post("/exports", status_code=201, summary="Export raw payloads for a date range")
def create_export(
    payload: ExportRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        record = archive.create_export(
            session, settings, start_date=payload.start_date, end_date=payload.end_date
        )
    except ValueError as exc:
        raise _archive_error(exc) from exc
    return _out(record)


@router.get("/exports/{export_id}/download", summary="Download an export archive")
def download_export(
    export_id: uuid.UUID,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> FileResponse:
    record = session.get(RawExport, export_id)
    if record is None:
        raise AppError("not_found", "No export with that identifier.")
    root = archive.export_root(settings)
    path = (root / record.path).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise AppError("not_found", "The archive file is no longer on disk.")
    return FileResponse(
        path,
        media_type="application/gzip",
        filename=path.name,
        headers={"X-Checksum-SHA256": record.sha256},
    )


@router.post("/exports/{export_id}/delete", summary="Delete the raw rows of an export")
def delete_export(
    export_id: uuid.UUID,
    payload: DeleteRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return archive.delete_export(
            session, export_id=export_id, confirm_sha256=payload.confirm_sha256
        )
    except (ValueError, LookupError) as exc:
        raise _archive_error(exc) from exc


@router.get("/retention/preview", summary="What the retention job would delete")
def retention_preview(
    days: int | None = Query(None, ge=1),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return archive.retention_preview(session, settings, days=days)
    except ValueError as exc:
        raise _archive_error(exc) from exc


@router.post("/retention", summary="Delete raw payloads past the retention window")
def run_retention(
    payload: RetentionRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if not payload.confirm:
        raise AppError("bad_request", "Set confirm=true to delete raw payloads.")
    try:
        return archive.run_retention(
            session, settings, days=payload.days, apply=True
        )
    except ValueError as exc:
        raise _archive_error(exc) from exc
