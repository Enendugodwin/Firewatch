# FIREWATCH X

**Global fire intelligence, from satellite detections to defensible analysis.**

FIREWATCH X is a geospatial intelligence platform for NASA MODIS and VIIRS active-fire
observations. It ingests real satellite thermal detections, normalises and harmonises them across
sensor families, and exposes historical burning activity, anomalies, regional profiles and
generated intelligence reports through a dark analytical console.

> [!IMPORTANT]
> **Status: Phase 1 of 9 — Foundation.** The platform shell, API, database, design system,
> navigation and test suites are complete and running. **No observations have been ingested yet**,
> so every module reports an empty state. Nothing is populated with sample data, and the API
> returns `501 not_implemented` for analytical routes rather than inventing numbers.
>
> Satellite thermal anomalies are detections, not confirmed wildfires. They may be false
> positives, may be agricultural or industrial heat, and can be hidden by cloud. Do not use this
> platform as the sole basis for protecting life or property.

---

## What works today

| Area | State |
| --- | --- |
| FastAPI application (config, structured logs, error envelope, request IDs, CORS, security headers) | Working |
| `GET /health`, `GET /ready` probes with degraded-state reporting | Working |
| Module registry + capability truth (`/api/v1/system/status`, `/modules`, `/sources`) | Working |
| PostgreSQL/PostGIS migration + idempotent 8-source FIRMS seed (SQLite fallback for dev) | Working |
| Dark geospatial design system (tokens, themes, panels, navigation, status bar) | Working |
| Responsive application shell: sidebar, command palette, date range, freshness, notices | Working |
| Type-checked React console, 11 module routes + 404 | Working |
| Docker Compose stack (PostGIS, Redis, API, Celery worker, nginx frontend) | Authored (no Docker on this host) |
| NASA FIRMS client, ingestion, harmonization, map, calendar, anomaly engine, reports, AI | Phase 2–7 |

## Quick start (local, no Docker)

Requires **Python 3.11+**, **[uv](https://docs.astral.sh/uv/)**, **Node 20+**.

```bash
cp .env.example .env          # optional: set FIRMS_MAP_KEY if you have one
python scripts/bootstrap.py   # prerequisites, migrations, source seed

# terminal 1 — API on :8200
cd backend && uv sync --group dev && uv run uvicorn app.main:app --reload --port 8200

# terminal 2 — console on :5273
cd frontend && npm install && npm run dev
```

Open <http://localhost:5273>. API docs: <http://127.0.0.1:8200/api/docs>.

Windows helper: `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1`.

Without a `FIRMS_MAP_KEY` the platform runs in its **unconfigured, empty state** — by design. It
never fabricates observations to look complete.

## Quick start (containers)

```bash
cp .env.example .env          # set POSTGRES_PASSWORD and FIRMS_MAP_KEY
docker compose up --build
```

- Console: <http://localhost:8088>
- API: <http://localhost:8200>
- PostGIS: `localhost:5433`

The `api` and `worker` containers share one image; the API runs migrations and the seed on boot.

## Repository layout

```
backend/          FastAPI app, Alembic migrations, Celery worker, pytest suite
frontend/         React + TypeScript + Tailwind console (Vite), Vitest suite
infrastructure/   container/deployment/monitoring assets as they are added
scripts/          bootstrap + dev runners
docs/             architecture, API, data dictionary, methodology, deployment, validation
docker-compose.yml
.env.example
```

Detailed structure and service responsibilities: [docs/architecture.md](docs/architecture.md).

## Configuration

All settings are environment variables read by the backend (`backend/app/core/config.py`).
A single root `.env` serves both local development and Compose. See [`.env.example`](.env.example).

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | PostgreSQL+PostGIS in deployments; SQLite is dev/test only |
| `FIRMS_MAP_KEY` | for data | NASA FIRMS key — **backend only**, never shipped to the browser |
| `REDIS_URL` | for workers | Celery broker/result backend |
| `CORS_ORIGINS` | yes | Comma-separated allowed frontend origins |
| `ENVIRONMENT` | no | `local` / `development` / `staging` / `production` |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | no | Optional assistant; statistical analysis works without an LLM |

Request a free FIRMS key: <https://firms.modaps.eosdis.nasa.gov/api/map_key/>

## Tests

```bash
cd backend  && uv run pytest      # 23 tests: API surface, honesty guarantees, migrations, seed
cd frontend && npm test           # 7 tests: shell, navigation, empty-state reporting
cd backend  && uv run ruff check . && uv run mypy app
cd frontend && npm run typecheck
```

Backend tests run against SQLite; the same migrations apply to PostgreSQL (the PostGIS
`CREATE EXTENSION` statement is dialect-guarded). Docker-based PostgreSQL testing arrives with the
ingestion phase.

## Design language

**Orbital Intelligence** — a near-black field (`#131315`) with deep-navy glass surfaces
(`#0B101D`), hairline white borders inside a gradient edge shell, and one restrained green accent
(`#60D58B`). Display type is Newsreader; interface copy is light-weight Inter; measurements,
coordinates and source codes are JetBrains Mono. Fire severity keeps its own semantic scale
(amber `#FACC15`, orange `#FB923C`, red `#EF4444`) so colour never confuses chrome with hazard.

A perspective grid field sits behind the console — green hairlines on black, breathing slowly and
drifting with the pointer, faded into the chrome at the edges. Radii stay in the 7/8/11/12/pill
family; motion is limited to 150 ms colour transitions and a 4 s ambient pulse, and is disabled
under `prefers-reduced-motion`. A high-contrast theme remaps the surface tokens only.

Full specification and component recipes: [docs/design.md](docs/design.md).

## Roadmap

| Phase | Scope | State |
| --- | --- | --- |
| 1 | Foundation: shell, API, database, design system, navigation | **Complete** |
| 2 | NASA FIRMS client, resumable ingestion, normalisation | Next |
| 3 | MODIS/VIIRS harmonization, event grouping, inspection UI | Planned |
| 4 | Global fire map with MapLibre, filters, hotspot provenance | Planned |
| 5 | Historical burning calendar with drill-down | Planned |
| 6 | Analytics, baselines, anomaly engine, exposure screening | Planned |
| 7 | Reports/exports, alerts, AI assistant | Planned |
| 8 | Validation, backtesting, performance, security hardening | Planned |
| 9 | Production deployment and monitoring | Planned |

## Attribution and limitations

Observations come from NASA FIRMS (MODIS Terra/Aqua and VIIRS Suomi-NPP / NOAA-20 / NOAA-21).
Standard Processing products power historical analysis; Near-Real-Time products power operational
monitoring. Processing versions are retained and never merged silently.

MODIS and VIIRS differ in spatial resolution, detection algorithm and confidence semantics, so
their raw totals are not interchangeable. Counts are of *detections*, not fires. Missing satellite
data is never presented as zero activity.

## Licence

MIT (see `LICENSE`).
