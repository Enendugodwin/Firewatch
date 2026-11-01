"""Storage abstraction.

Application code talks to :class:`StorageProvider`, never to a filesystem path or
an S3 SDK. Local mode uses the filesystem; R2 and any S3-compatible service use
the S3 adapter. Every operation returns verifiable metadata so a caller can check
what actually happened instead of assuming an upload succeeded.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHUNK = 1024 * 1024


@dataclass(frozen=True)
class ObjectMetadata:
    path: str
    size: int
    modified: datetime | None = None
    checksum: str | None = None
    content_type: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


class StorageProvider(ABC):
    """The only surface the rest of the application may use."""

    name: str = "storage"

    @abstractmethod
    def upload(self, source: Path, destination: str) -> ObjectMetadata: ...

    @abstractmethod
    def download(self, source: str, destination: Path) -> ObjectMetadata: ...

    @abstractmethod
    def delete(self, path: str) -> bool: ...

    @abstractmethod
    def exists(self, path: str) -> bool: ...

    @abstractmethod
    def get_metadata(self, path: str) -> ObjectMetadata: ...

    @abstractmethod
    def list(self, prefix: str = "") -> list[ObjectMetadata]: ...

    @abstractmethod
    def checksum(self, path: str) -> str: ...

    @abstractmethod
    def available_bytes(self) -> int | None: ...

    @abstractmethod
    def signed_url(self, path: str, expires_seconds: int = 3600) -> str | None: ...

    def used_bytes(self) -> int:
        """Bytes currently stored under this provider's root. Best effort."""
        return sum(item.size for item in self.list(""))

    def verify(self, path: str, *, size: int | None, checksum: str | None) -> bool:
        """
        Confirm a stored object matches what was uploaded. Never assume success
        from the absence of an exception.
        """
        try:
            metadata = self.get_metadata(path)
        except FileNotFoundError:
            return False
        if size is not None and metadata.size != size:
            return False
        if checksum is not None:
            remote = metadata.checksum or self.checksum(path)
            if remote != checksum:
                return False
        return True
