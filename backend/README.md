# FIREWATCH X — Backend

FastAPI service for the FIREWATCH X global fire intelligence platform.

Phase 1 (Foundation) provides configuration, structured logging, the standard
error envelope, request correlation, CORS, health/readiness probes, the module
registry and the versioned `/api/v1` surface. Analytical endpoints return
`501 not_implemented` until the phase that builds them; no invented data is ever
served.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- PostgreSQL 16 + PostGIS 3.4 for production; SQLite is supported for local
  development and tests only

## Setup

```bash
cd backend
uv sync --group dev
cp ../.env.example .env          # then edit DATABASE_URL / FIRMS_MAP_KEY
uv run alembic upgrade head
uv run python -m scripts.seed_sources
uv run uvicorn app.main:app --reload --port 8200
```

API documentation: <http://localhost:8200/api/docs>

## Tests

```bash
uv run pytest            # unit + integration on SQLite
uv run ruff check .
```

## Layout

```
app/
  main.py            application factory
  core/              config, logging, errors, middleware, module registry
  api/               health probes + versioned routers
  db/                declarative base, session, models
  schemas/           pydantic request/response models
  services/          FIRMS source catalogue, health probes (Phase 2+ services)
migrations/          Alembic revisions
scripts/             seeding and operational entry points
tests/               pytest suite
```
