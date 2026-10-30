"""FIREWATCH X bootstrap.

Checks prerequisites, creates `.env` from the template when missing, applies
migrations and seeds the NASA FIRMS source registry. Idempotent: safe to re-run.

Usage (from the repository root)::

    python scripts/bootstrap.py            # check + migrate + seed
    python scripts/bootstrap.py --check    # checks only, no writes
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MIN_PYTHON = (3, 11)


def ok(message: str) -> None:
    print(f"  [ok]   {message}")


def warn(message: str) -> None:
    print(f"  [warn] {message}")


def fail(message: str) -> None:
    print(f"  [fail] {message}")


def _env_value(content: str, key: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith(f"{key}=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip()
    return ""


def check_prerequisites() -> bool:
    healthy = True

    if sys.version_info < MIN_PYTHON:
        fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {sys.version.split()[0]}")
        healthy = False
    else:
        ok(f"python {sys.version.split()[0]}")

    for tool, required in (("uv", True), ("node", False), ("npm", False), ("docker", False)):
        path = shutil.which(tool)
        if path:
            ok(f"{tool} found")
        elif required:
            fail(f"{tool} not found (install from https://docs.astral.sh/uv/)")
            healthy = False
        else:
            warn(f"{tool} not found (only needed for containers / the frontend)")

    if not (BACKEND / "pyproject.toml").exists():
        fail("backend/pyproject.toml is missing; run from a complete checkout")
        healthy = False
    if not (ROOT / "frontend" / "package.json").exists():
        fail("frontend/package.json is missing")
        healthy = False

    env_file = ROOT / ".env"
    if env_file.exists():
        ok(".env present")
        content = env_file.read_text(encoding="utf-8")
        if "FIRMS_MAP_KEY=" in content and not _env_value(content, "FIRMS_MAP_KEY"):
            warn("FIRMS_MAP_KEY is empty; the platform runs without NASA data (by design)")
    else:
        warn(".env missing (copy .env.example to .env)")

    return healthy


def run(command: list[str], cwd: Path) -> int:
    print(f"  $ {' '.join(command)}")
    return subprocess.call(command, cwd=cwd)


def migrate_and_seed() -> bool:
    upgrade = run(["uv", "run", "--project", "backend", "alembic", "upgrade", "head"], BACKEND)
    if upgrade != 0:
        fail("migrations failed; check DATABASE_URL and that the database is running")
        return False
    seed = run(
        ["uv", "run", "--project", "backend", "python", "-m", "scripts.seed_sources"], BACKEND
    )
    if seed != 0:
        fail("source seeding failed")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap FIREWATCH X")
    parser.add_argument("--check", action="store_true", help="only run prerequisite checks")
    args = parser.parse_args()

    print("FIREWATCH X - bootstrap")
    print("\nPrerequisites")
    healthy = check_prerequisites()

    if args.check:
        return 0 if healthy else 1

    if not healthy:
        fail("resolve the failures above before continuing")
        return 1

    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copyfile(ROOT / ".env.example", env_file)
        ok("created .env from .env.example (edit DATABASE_URL / FIRMS_MAP_KEY)")

    print("\nDatabase")
    if not migrate_and_seed():
        return 1
    ok("migrations applied and NASA FIRMS sources seeded")

    print("\nNext steps")
    print("  backend : cd backend && uv run uvicorn app.main:app --reload --port 8100")
    print("  frontend: cd frontend && npm install && npm run dev")
    print("  or both : docker compose up --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
