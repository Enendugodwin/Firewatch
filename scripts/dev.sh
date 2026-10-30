#!/usr/bin/env bash
# Start the FIREWATCH X development servers (API :8100, frontend :5173).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$root/.env" ]; then
  cp "$root/.env.example" "$root/.env"
  echo "Created .env from .env.example — set FIRMS_MAP_KEY when you have one."
fi

cd "$root/backend"
uv run alembic upgrade head
uv run python -m scripts.seed_sources

uv run uvicorn app.main:app --reload --port 8100 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT

cd "$root/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
npm run dev
