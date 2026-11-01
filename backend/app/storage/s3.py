"""S3-compatible object storage: Cloudflare R2 and any S3 endpoint.

Cloudflare R2 speaks the S3 API, so one adapter covers R2, AWS S3, MinIO and the
like. Checksums travel with the object as ``x-amz-meta-sha256`` so a later
verification does not have to download it again.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import ObjectMetadata, StorageProvider, sha256_file

CHECKSUM_META = "sha256"


class StorageUnavailable(RuntimeError):
    """Raised when the provider is not configured or cannot be reached."""


class S3Storage(StorageProvider):
    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str = "auto",
        prefix: str = "",
    ) -> None:
        if not bucket:
            raise StorageUnavailable("A bucket name is required for S3/R2 storage.")
        if not access_key_id or not secret_access_key:
            raise StorageUnavailable("S3/R2 credentials are missing (ACCESS_KEY_ID / SECRET).")

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
            ),
        )

    def _key(self, path: str) -> str:
        clean = str(path).replace("\\", "/").lstrip("/")
        if ".." in clean.split("/"):
            raise ValueError(f"Refusing object key with traversal: {path}")
        return f"{self.prefix}/{clean}" if self.prefix else clean

    def upload(self, source: Path, destination: str) -> ObjectMetadata:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        key = self._key(destination)
        checksum = sha256_file(source)
        try:
            # upload_file switches to multipart automatically for large files.
            self.client.upload_file(
                str(source),
                self.bucket,
                key,
                ExtraArgs={"Metadata": {CHECKSUM_META: checksum}},
            )
        except (BotoCoreError, ClientError) as error:  # pragma: no cover - network path
            raise StorageUnavailable(f"Upload failed for {key}: {error}") from error
        return self.get_metadata(destination)

    def download(self, source: str, destination: Path) -> ObjectMetadata:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, self._key(source), str(destination))
        except (BotoCoreError, ClientError) as error:  # pragma: no cover - network path
            raise FileNotFoundError(f"Object not available: {source}") from error
        return self.get_metadata(source)

    def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except (BotoCoreError, ClientError):  # pragma: no cover - network path
            return False

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageUnavailable(str(error)) from error
        except BotoCoreError as error:  # pragma: no cover - network path
            raise StorageUnavailable(str(error)) from error

    def get_metadata(self, path: str) -> ObjectMetadata:
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=self._key(path))
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(path) from error
            raise StorageUnavailable(str(error)) from error
        except BotoCoreError as error:  # pragma: no cover - network path
            raise StorageUnavailable(str(error)) from error

        metadata = head.get("Metadata") or {}
        return ObjectMetadata(
            path=self._key(path),
            size=int(head.get("ContentLength", 0)),
            modified=head.get("LastModified"),
            checksum=metadata.get(CHECKSUM_META),
            content_type=head.get("ContentType"),
        )

    def list(self, prefix: str = "") -> list[ObjectMetadata]:
        key_prefix = self._key(prefix) if prefix else (self.prefix or "")
        objects: list[ObjectMetadata] = []
        paginator = self.client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=key_prefix):
                for item in page.get("Contents", []):
                    objects.append(
                        ObjectMetadata(
                            path=item["Key"],
                            size=int(item["Size"]),
                            modified=item.get("LastModified"),
                        )
                    )
        except (BotoCoreError, ClientError) as error:  # pragma: no cover - network path
            raise StorageUnavailable(str(error)) from error
        return objects

    def checksum(self, path: str) -> str:
        metadata = self.get_metadata(path)
        if metadata.checksum:
            return metadata.checksum
        # Older objects without the metadata: download to a temporary file.
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            temp = Path(handle.name)
        try:
            self.download(path, temp)
            return sha256_file(temp)
        finally:
            temp.unlink(missing_ok=True)

    def available_bytes(self) -> int | None:
        # Object storage exposes no quota; callers compare usage against a
        # configured allocation instead.
        return None

    def used_bytes(self) -> int:
        return sum(item.size for item in self.list(""))

    def signed_url(self, path: str, expires_seconds: int = 3600) -> str | None:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self._key(path)},
                ExpiresIn=expires_seconds,
            )
        except (BotoCoreError, ClientError):  # pragma: no cover - network path
            return None

    def test_connection(self) -> dict[str, object]:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return {"ok": True, "bucket": self.bucket, "checked_at": datetime.now(UTC).isoformat()}
        except (BotoCoreError, ClientError) as error:
            return {
                "ok": False,
                "bucket": self.bucket,
                "error": str(error),
                "checked_at": datetime.now(UTC).isoformat(),
            }
