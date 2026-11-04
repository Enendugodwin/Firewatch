"""Restore a backup produced by ``scripts.backup_database``.

    python -m scripts.restore_database --file backups/firewatch-....dump \
        --target-url postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch_restore

The checksum sidecar is verified first when present. ``--clean`` drops the
target's existing objects, so the target must be an empty or disposable
database; the script refuses to restore over the database named in
``DATABASE_URL`` unless ``--force`` is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.logging import configure_logging


def _tool(name: str) -> str:
    override = os.environ.get("PG_BIN")
    if override and (Path(override) / f"{name}.exe").is_file():
        return str(Path(override) / f"{name}.exe")
    if override and (Path(override) / name).is_file():
        return str(Path(override) / name)
    found = shutil.which(name)
    if found:
        return found
    fallback = Path("C:/Users/user/pgsql/pgsql/bin") / f"{name}.exe"
    if fallback.is_file():
        return str(fallback)
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
    parser.add_argument("--file", required=True, help="Path to the .dump file")
    parser.add_argument("--target-url", required=True, help="Disposable target database")
    parser.add_argument("--force", action="store_true", help="Allow restoring over DATABASE_URL")
    args = parser.parse_args()

    configure_logging()
    dump = Path(args.file).expanduser().resolve()
    if not dump.is_file():
        raise SystemExit(f"No such backup: {dump}")

    sidecar = dump.with_suffix(dump.suffix + ".sha256")
    if sidecar.is_file():
        expected = sidecar.read_text(encoding="ascii").split()[0]
        actual = _sha256(dump)
        if actual != expected:
            raise SystemExit("Checksum mismatch: the backup is corrupt or was modified.")
        print(f"checksum ok: {actual}")

    target = make_url(args.target_url)
    if target.get_backend_name() != "postgresql":
        raise SystemExit("Restore targets must be PostgreSQL.")
    live = make_url(get_settings().database_url)
    if not args.force and (target.host, target.port, target.database) == (
        live.host,
        live.port,
        live.database,
    ):
        raise SystemExit("Refusing to overwrite the live database; use a scratch database.")

    env = os.environ.copy()
    if target.password:
        env["PGPASSWORD"] = target.password
    command = [
        _tool("pg_restore"),
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        f"--host={target.host or '127.0.0.1'}",
        f"--port={target.port or 5432}",
        f"--username={target.username or 'postgres'}",
        f"--dbname={target.database}",
        str(dump),
    ]
    subprocess.run(command, check=True, env=env)
    print(f"restored {dump.name} into {target.database} on {target.host}:{target.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
