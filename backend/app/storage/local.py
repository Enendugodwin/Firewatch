"""Filesystem storage provider (local mode, and the fallback everywhere)."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from app.storage.base import ObjectMetadata, StorageProvider, sha256_file


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- path handling -----------------------------------------------------
    def _resolve(self, path: str) -> Path:
        relative = PurePosixPath(str(path).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Refusing path outside the data root: {path}")
        target = (self.root / Path(*relative.parts)).resolve()
        if not str(target).startswith(str(self.root)):
            raise ValueError(f"Refusing path outside the data root: {path}")
        return target

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    # -- operations --------------------------------------------------------
    def upload(self, source: Path, destination: str) -> ObjectMetadata:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        target = self._resolve(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")
        shutil.copyfile(source, partial)
        os.replace(partial, target)  # atomic: a reader never sees a half file
        return self.get_metadata(destination)

    def download(self, source: str, destination: Path) -> ObjectMetadata:
        origin = self._resolve(source)
        if not origin.is_file():
            raise FileNotFoundError(source)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
        return self.get_metadata(source)

    def delete(self, path: str) -> bool:
        target = self._resolve(path)
        if target.is_file():
            target.unlink()
            return True
        return False

    def exists(self, path: str) -> bool:
        return self._resolve(path).is_file()

    def get_metadata(self, path: str) -> ObjectMetadata:
        target = self._resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        stat = target.stat()
        return ObjectMetadata(
            path=self._relative(target),
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            checksum=sha256_file(target),
        )

    def list(self, prefix: str = "") -> list[ObjectMetadata]:
        base = self._resolve(prefix) if prefix else self.root
        if base.is_file():
            return [self.get_metadata(self._relative(base))]
        if not base.is_dir():
            return []
        objects = []
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.name.endswith(".part"):
                objects.append(self.get_metadata(self._relative(path)))
        return objects

    def checksum(self, path: str) -> str:
        return sha256_file(self._resolve(path))

    def available_bytes(self) -> int | None:
        usage = shutil.disk_usage(self.root)
        return int(usage.free)

    def used_bytes(self) -> int:
        total = 0
        for path in self.root.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def signed_url(self, path: str, expires_seconds: int = 3600) -> str | None:
        # The filesystem has no signed URLs; the caller serves the file itself.
        return None
