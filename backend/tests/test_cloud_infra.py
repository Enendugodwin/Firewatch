"""Storage abstraction, dataset export, DuckDB reads and cloud sync."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import datasets as dataset_service
from app.services import parquet_query
from app.services import sync as sync_service
from app.storage.base import sha256_file
from app.storage.local import LocalStorage


@pytest.fixture()
def local_provider(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "store")


def test_local_storage_round_trip(local_provider: LocalStorage, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"firewatch" * 1000)

    uploaded = local_provider.upload(source, "raw/2026/file.bin")
    assert uploaded.size == source.stat().st_size
    assert uploaded.checksum == sha256_file(source)
    assert local_provider.exists("raw/2026/file.bin")

    fetched = local_provider.get_metadata("raw/2026/file.bin")
    assert fetched.size == source.stat().st_size

    target = tmp_path / "copy.bin"
    local_provider.download("raw/2026/file.bin", target)
    assert target.read_bytes() == source.read_bytes()

    assert [item.path for item in local_provider.list("raw")] == ["raw/2026/file.bin"]
    assert local_provider.verify("raw/2026/file.bin", size=fetched.size, checksum=fetched.checksum)
    assert not local_provider.verify("raw/2026/file.bin", size=fetched.size + 1, checksum=None)

    assert local_provider.delete("raw/2026/file.bin") is True
    assert local_provider.exists("raw/2026/file.bin") is False


def test_local_storage_rejects_traversal(local_provider: LocalStorage) -> None:
    with pytest.raises(ValueError):
        local_provider.upload(Path(__file__), "../escape.txt")


def test_preview_and_sync_are_idempotent(tmp_path: Path) -> None:
    cloud = LocalStorage(tmp_path / "cloud")

    source = tmp_path / "detections.parquet"
    source.write_bytes(b"parquet-bytes")
    entry = {
        "dataset": "detections-2026-10",
        "path": "harmonized/year=2026/month=10/detections.parquet",
        "kind": "harmonized",
        "sensor": "all",
        "coverage_start": "2026-10-01",
        "coverage_end": "2026-10-31",
        "partition": "year=2026/month=10",
        "records": 10,
        "size_bytes": source.stat().st_size,
        "checksum": sha256_file(source),
        "schema_version": "detections-parquet-v1",
        "processing_version": "export-v1",
        "local_path": str(source),
    }

    first = sync_service.preview(cloud, [entry])
    assert first["counts"]["missing"] == 1
    assert first["upload_bytes"] == entry["size_bytes"]

    report = sync_service.sync(cloud, [entry], allocation_bytes=10_000_000)
    assert report["status"] == "ok"
    assert report["uploaded"] == 1
    assert report["verified"] == 1
    assert cloud.exists(f"firewatch-data/{entry['path']}")
    assert cloud.exists("firewatch-data/manifests/latest.json")

    second = sync_service.preview(cloud, [entry])
    assert second["counts"]["matched"] == 1
    assert second["upload_bytes"] == 0

    # Local files are never deleted by a sync.
    assert source.exists()


def test_sync_blocks_when_allocation_would_be_exceeded(tmp_path: Path) -> None:
    cloud = LocalStorage(tmp_path / "cloud")
    source = tmp_path / "big.bin"
    source.write_bytes(b"x" * 2048)
    entry = {
        "dataset": "big",
        "path": "exports/big.bin",
        "size_bytes": source.stat().st_size,
        "checksum": sha256_file(source),
        "local_path": str(source),
        "records": 1,
    }

    report = sync_service.sync(cloud, [entry], allocation_bytes=1024)
    assert report["status"] == "blocked"
    assert report["reason"] == "allocation_exceeded"
    assert not cloud.exists("firewatch-data/exports/big.bin")


def test_sync_detects_changed_content(tmp_path: Path) -> None:
    cloud = LocalStorage(tmp_path / "cloud")
    source = tmp_path / "file.bin"
    source.write_bytes(b"first")
    entry = {
        "dataset": "file",
        "path": "exports/file.bin",
        "size_bytes": source.stat().st_size,
        "checksum": sha256_file(source),
        "local_path": str(source),
        "records": 1,
    }
    sync_service.sync(cloud, [entry])

    source.write_bytes(b"second-version")
    changed = {
        **entry,
        "size_bytes": source.stat().st_size,
        "checksum": sha256_file(source),
    }
    preview = sync_service.preview(cloud, [changed])
    assert preview["counts"]["size_mismatch"] == 1


def test_parquet_export_and_duckdb_read(
    client: TestClient, loaded_fixture: dict, tmp_path: Path
) -> None:
    from datetime import date as date_type

    from app.db.session import session_scope

    root = dataset_service.dataset_root(tmp_path / "data")
    with session_scope() as session:
        files = dataset_service.export_detections(
            session,
            root=root,
            start=date_type(2026, 10, 1),
            end=date_type(2026, 10, 31),
            synthetic=True,
        )

    assert files, "expected at least one Parquet file"
    assert sum(item["records"] for item in files) == loaded_fixture["inserted"]

    first = Path(root / files[0]["path"])
    summary = parquet_query.summarise(first)
    assert summary["rows"] == files[0]["records"]
    assert "acquired_at" in summary["columns"]
    assert summary["size_bytes"] > 0

    scanned = dataset_service.scan_datasets(root)
    assert len(scanned) == len(files)
    assert scanned[0]["checksum"] == files[0]["checksum"]

    manifest = dataset_service.manifest(scanned)
    assert manifest["file_count"] == len(files)
    assert manifest["record_count"] == loaded_fixture["inserted"]
    assert manifest["datasets"][0]["cloud_object"].startswith("firewatch-data/")


def test_infrastructure_status_reports_local_mode(client: TestClient) -> None:
    body = client.get("/api/v1/infrastructure/status").json()

    assert body["deployment_mode"] in {"local", "hybrid", "cloud"}
    assert body["storage"]["mode"] in {"local", "r2", "s3"}
    assert body["database"]["tables"] >= 1


def test_infrastructure_storage_test(client: TestClient) -> None:
    body = client.post("/api/v1/infrastructure/storage/test").json()
    assert body["ok"] is True
    assert body["provider"] == "local"


def test_export_endpoint_writes_and_lists(client: TestClient, loaded_fixture: dict) -> None:
    exported = client.post(
        "/api/v1/infrastructure/export",
        json={"start_date": "2026-10-01", "end_date": "2026-10-31", "synthetic": True},
    )
    assert exported.status_code == 200
    body = exported.json()
    assert body["written"] >= 1
    assert body["manifest"]["record_count"] == loaded_fixture["inserted"]

    listed = client.get("/api/v1/infrastructure/datasets").json()
    assert listed["count"] >= 1
    assert listed["records"] >= loaded_fixture["inserted"]

    first = listed["datasets"][0]["dataset"]
    verified = client.get(f"/api/v1/infrastructure/datasets/{first}/verify").json()
    assert verified["parquet"]["rows"] == listed["datasets"][0]["records"]

    preview = client.post("/api/v1/infrastructure/sync/preview").json()
    # Local mode stores datasets under the same root, so they are already present.
    assert preview["counts"]["missing"] == 0
    assert preview["counts"]["matched"] >= 1

    pytest.importorskip("duckdb")
    sensors = client.get("/api/v1/infrastructure/parquet/sensors")
    assert sensors.status_code in {200, 400}
    if sensors.status_code == 200:
        assert "sensors" in sensors.json()
