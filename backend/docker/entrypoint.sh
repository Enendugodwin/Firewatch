#!/usr/bin/env bash
# Container entrypoint: wait for the database, migrate, seed the registry, serve.
set -euo pipefail

echo "[entrypoint] waiting for the database..."
attempts=0
until alembic upgrade head >/tmp/alembic.log 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 30 ]; then
    echo "[entrypoint] database did not become ready in time" >&2
    cat /tmp/alembic.log >&2
    exit 1
  fi
  sleep 2
done
echo "[entrypoint] migrations applied"

python -m scripts.seed_sources || echo "[entrypoint] source seed skipped"

exec "$@"
