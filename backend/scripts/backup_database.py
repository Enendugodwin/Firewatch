"""Create a verified PostgreSQL backup with ``pg_dump``.

    python -m scripts.backup_database
    python -m scripts.backup_database --output-dir D:/backups

The dump is custom-format (compressed, restorable with ``pg_restore``) and gets
a sibling ``.sha256`` file so a restore can prove it used the intended bytes.
Cloud deployments should run this on a schedule and copy the pair off the host.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.logging import configure_logging


def _tool(name: str) -> str:
    override = os.environ.get("PG_BIN")
    candidates = []
    if override:
        candidates.append(Path(override) / name)
    found = shutil.which(name)
    if found:
        return found
    candidates.append(Path("C:/Users/user/pgsql/pgsql/bin") / f"{name}.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(f"{name} was not found. Set PG_BIN to the PostgreSQL bin directory.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="backups", help="Where to write the dump")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    args = parser.parse_args()

    configure_logging()
    url = make_url(args.database_url or get_settings().database_url)
    if url.get_backend_name() != "postgresql":
        raise SystemExit("Backups are only implemented for PostgreSQL.")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = output_dir / f"{url.database or 'firewatch'}-{stamp}.dump"

    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    command = [
        _tool("pg_dump"),
        "--format=custom",
        "--compress=6",
        "--no-owner",
        "--no-privileges",
        f"--host={url.host or '127.0.0.1'}",
        f"--port={url.port or 5432}",
        f"--username={url.username or 'postgres'}",
        f"--dbname={url.database}",
        f"--file={target}",
    ]
    subprocess.run(command, check=True, env=env)

    checksum = _sha256(target)
    sidecar = target.with_suffix(target.suffix + ".sha256")
    sidecar.write_text(f"{checksum}  {target.name}\n", encoding="ascii")

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"backup: {target}")
    print(f"size:   {size_mb:.1f} MB")
    print(f"sha256: {checksum}")
    print(f"sidecar: {sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
