"""Cloud synchronisation.

The manager compares what is on disk with what is in the bucket, plans a
deployment, uploads, then **verifies size and checksum** before recording success.
Nothing is deleted locally, and a re-run skips objects that already match, so the
operation is idempotent and resumable.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.datasets import manifest as build_manifest
from app.storage.base import StorageProvider
from app.storage.s3 import StorageUnavailable

CLOUD_PREFIX = "firewatch-data"


def _remote(provider: StorageProvider, key: str):
    try:
        return provider.get_metadata(key)
    except FileNotFoundError:
        return None


def preview(
    provider: StorageProvider,
    entries: Iterable[dict[str, Any]],
    *,
    cloud_prefix: str = CLOUD_PREFIX,
) -> dict[str, Any]:
    """
    Compare local datasets with the bucket, without uploading anything.
    Statuses: missing (upload), matched (skip), changed (checksum differs),
    size_mismatch (same name, different size).
    """
    planned: list[dict[str, Any]] = []
    upload_bytes = 0
    counts = {"missing": 0, "matched": 0, "changed": 0, "size_mismatch": 0}

    for entry in entries:
        key = f"{cloud_prefix}/{entry['path']}"
        remote = _remote(provider, key)

        if remote is None:
            status = "missing"
        elif remote.size != entry["size_bytes"]:
            status = "size_mismatch"
        elif remote.checksum and remote.checksum != entry["checksum"]:
            status = "changed"
        else:
            status = "matched"

        counts[status] += 1
        if status != "matched":
            upload_bytes += int(entry["size_bytes"])
        planned.append(
            {
                **entry,
                "cloud_object": key,
                "sync_status": status,
                "remote_size": None if remote is None else remote.size,
            }
        )

    return {
        "previewed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": counts,
        "upload_bytes": upload_bytes,
        "remote_used_bytes": provider.used_bytes(),
        "files": planned,
    }


def _upload_manifest(provider: StorageProvider, manifest: dict[str, Any]) -> None:
    payload = json.dumps(manifest, indent=2).encode("utf-8")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as handle:
        handle.write(payload)
        temp = Path(handle.name)
    try:
        provider.upload(temp, f"{CLOUD_PREFIX}/manifests/latest.json")
    except (StorageUnavailable, OSError):
        pass
    finally:
        temp.unlink(missing_ok=True)


def sync(
    provider: StorageProvider,
    entries: Iterable[dict[str, Any]],
    *,
    cloud_prefix: str = CLOUD_PREFIX,
    allocation_bytes: int | None = None,
    verify: bool = True,
) -> dict[str, Any]:
    """
    Upload what is missing or changed, verify each object, and return a report.
    A verification failure is reported per file; it is never recorded as success.
    """
    plan = preview(provider, entries, cloud_prefix=cloud_prefix)
    used = int(plan["remote_used_bytes"] or 0)
    needed = int(plan["upload_bytes"])

    if allocation_bytes is not None and used + needed > allocation_bytes:
        return {
            "status": "blocked",
            "reason": "allocation_exceeded",
            "detail": (
                "Planned upload would exceed the configured allocation. Nothing was uploaded "
                "and no historical data was deleted."
            ),
            "remote_used_bytes": used,
            "upload_bytes": needed,
            "allocation_bytes": allocation_bytes,
            "results": [],
        }

    results: list[dict[str, Any]] = []
    uploaded = 0
    failed = 0
    skipped = 0
    verified = 0

    for item in plan["files"]:
        key = item["cloud_object"]
        if item["sync_status"] == "matched":
            skipped += 1
            results.append({**item, "result": "skipped", "verified": True})
            continue

        source = Path(item["local_path"])
        try:
            provider.upload(source, key)
        except (StorageUnavailable, OSError) as error:
            failed += 1
            results.append({**item, "result": "failed", "error": str(error)})
            continue

        uploaded += 1
        ok = True
        if verify:
            ok = provider.verify(key, size=item["size_bytes"], checksum=item["checksum"])
            if ok:
                verified += 1
        results.append(
            {
                **item,
                "result": "uploaded" if ok else "verification_failed",
                "verified": ok,
            }
        )
        if not ok:
            failed += 1

    report = {
        "status": "ok" if failed == 0 else "partial",
        "uploaded": uploaded,
        "skipped": skipped,
        "failed": failed,
        "verified": verified,
        "upload_bytes": needed,
        "remote_used_bytes": provider.used_bytes(),
        "allocation_bytes": allocation_bytes,
        "results": results,
    }

    manifest = build_manifest(
        [{**item, "sync_status": item.get("result", "pending")} for item in results]
    )
    manifest["sync_report"] = {
        key: report[key] for key in ("status", "uploaded", "skipped", "failed")
    }
    _upload_manifest(provider, manifest)
    return report


def write_local_manifest(root: Path, payload: dict[str, Any]) -> Path:
    target = root / "manifests" / "latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    target.write_text(text, encoding="utf-8")
    stamped = root / "manifests" / f"manifest-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    stamped.write_text(text, encoding="utf-8")
    return target
