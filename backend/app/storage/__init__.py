"""Storage provider selection from configuration."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings, get_settings
from app.storage.base import StorageProvider
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage, StorageUnavailable

__all__ = ["LocalStorage", "S3Storage", "StorageUnavailable", "get_storage", "storage_report"]


def get_storage(settings: Settings | None = None) -> StorageProvider:
    """
    Build the provider for the active mode. Local mode never needs cloud
    credentials; cloud mode fails loudly when they are missing rather than
    silently writing to disk.
    """
    settings = settings or get_settings()
    mode = settings.storage_mode

    if mode in {"local", ""}:
        return LocalStorage(Path(settings.local_data_directory))

    if mode in {"r2", "s3", "cloud"}:
        if mode == "r2":
            endpoint = settings.r2_endpoint_url or (
                f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
                if settings.r2_account_id
                else None
            )
            return S3Storage(
                bucket=settings.r2_bucket_name or "",
                endpoint_url=endpoint,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
                region="auto",
            )
        return S3Storage(
            bucket=settings.r2_bucket_name or "",
            endpoint_url=settings.r2_endpoint_url,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
        )

    raise StorageUnavailable(f"Unknown STORAGE_MODE {mode!r}; use local, r2 or s3.")


def storage_report(settings: Settings | None = None) -> dict[str, object]:
    """Configuration and capacity without raising, for the readiness page."""
    settings = settings or get_settings()
    report: dict[str, object] = {
        "mode": settings.storage_mode,
        "local_directory": settings.local_data_directory,
        "database_mode": settings.database_mode,
        "r2_bucket": settings.r2_bucket_name or None,
        "r2_configured": bool(
            settings.r2_access_key_id
            and settings.r2_secret_access_key
            and settings.r2_bucket_name
        ),
    }
    try:
        provider = get_storage(settings)
    except (StorageUnavailable, ValueError) as error:
        report.update({"available": False, "error": str(error)})
        return report

    report["available"] = True
    report["provider"] = provider.name
    try:
        report["used_bytes"] = provider.used_bytes()
        if isinstance(provider, LocalStorage):
            report["free_bytes"] = provider.available_bytes()
        report["allocation_bytes"] = settings.r2_allocation_bytes
    except StorageUnavailable as error:  # pragma: no cover - network path
        report.update({"available": False, "error": str(error)})
    return report
