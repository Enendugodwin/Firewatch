# Architecture

## Shape

FIREWATCH X is a **modular monolith**: one deployable API with clearly separated service modules,
one background worker, one database, one web client. No microservices — the interfaces are module
boundaries, not network hops.

```
Browser (React SPA)
   │  /api/v1/*  (same-origin in production, Vite proxy in development)
   ▼
FastAPI application  ──────────────►  PostgreSQL + PostGIS
   │        (SQLAlchemy 2.0)              observations, regions,
   │                                      matches, events, statistics
   │  task hand-off (Redis)
   ▼
Celery worker  ────────────────────►  NASA FIRMS API
   (ingestion, harmonization,             (MODIS / VIIRS, SP + NRT)
    anomaly scoring, reports)
```

## Layers

| Layer | Location | Responsibility |
| --- | --- | --- |
| Application | `backend/app/main.py` | App factory, lifespan, middleware, router mounting |
| Core | `backend/app/core/` | Settings, logging, error envelope, request context, module registry |
| API | `backend/app/api/` | Probes and versioned routers; request/response schemas |
| Schemas | `backend/app/schemas/` | Pydantic models; the public contract |
| DB | `backend/app/db/` | Declarative base, dialect-portable UUIDs, session management, models |
| Services | `backend/app/services/` | FIRMS source catalogue, health probes; ingestion/analytics/reporting to follow |
| Workers | `backend/app/workers/` | Celery app and tasks |
| Migrations | `backend/migrations/` | Alembic revisions (dialect-aware) |

Frontend layers: `src/components/layout` (shell), `src/components/ui` (design system),
`src/pages` (module workspaces), `src/lib` (API client, queries, formatting),
`src/store` (persisted UI state), `src/config` (navigation and API contracts).

## Service responsibilities (target architecture)

The specification names twelve services. They map onto modules of this monolith:

| Service | Status | Location |
| --- | --- | --- |
| `firms_ingestion` | Phase 2 | `services/ingestion` |
| `normalization` | Phase 2 | `services/normalization` |
| `harmonization` | Phase 3 | `services/harmonization` |
| `geospatial` | Phase 4 | `services/geospatial` |
| `calendar` | Phase 5 | `services/calendar` |
| `anomaly_engine` | Phase 6 | `services/anomalies` |
| `exposure_engine` | Phase 6 | `services/exposure` |
| `reporting` | Phase 7 | `services/reporting` |
| `ai_assistant` | Phase 7 | `services/assistant` |
| `notification_engine` | Phase 7 | `services/notifications` |
| `auth` | Phase 8 | `services/auth` |
| `audit` | Phase 8 | `services/audit` |

## Phase 1 decisions worth knowing

**Honest empty states over sample data.** Analytical routes exist in OpenAPI from day one but
raise `AppError("not_implemented")`, rendered as:

```json
{"error": {"code": "not_implemented", "message": "…",
           "details": {"current_phase": "Phase 1", "planned_for_phase": "Phase 2"},
           "request_id": "…"}}
```

The UI treats `501` as "contract published, implementation pending", which keeps navigation and
documentation honest while the pipeline is built.

**One registry, two readers.** `app/core/modules.py` is the single source of truth for module
labels, routes, phases and capabilities. The API serves it; the console renders it. A module
cannot claim to be operational in the UI unless the backend says `ready`.

**Dialect-portable schema.** `GUID` stores native `uuid` on PostgreSQL and `CHAR(32)` elsewhere;
`CREATE EXTENSION postgis` runs only on PostgreSQL. CI and local development therefore run the
identical migration chain on SQLite, while deployments get real spatial types.

**Sessions are lazy.** The engine is created on first use, so `/health` answers even when the
database is down and `/ready` can report *why* it is not ready.

**Secrets never cross the boundary.** `FIRMS_MAP_KEY`, database credentials and AI keys are read
only by the backend. The browser bundle contains no secret and calls only relative `/api` paths.

## Data flow (target)

1. **Retrieve** — tiled, resumable FIRMS area queries (≤5 days per request), raw payloads retained
   with retrieval metadata.
2. **Normalise** — canonical observation record per source, preserving original confidence,
   brightness channel and processing version.
3. **Harmonise** — spatial-temporal candidate association, scored `S = wₜT + wₛG + w_fF`, classified
   probable/possible/unmatched; raw observations are never overwritten.
4. **Aggregate** — daily statistics per region, sensor and metric; calendar aggregates precomputed.
5. **Analyse** — seasonal baselines, robust deviations (MAD), optional Isolation Forest.
6. **Explain** — every anomaly and report carries method, sample size, baseline period and limits.

## Non-negotiables

- A detection count is never presented as a count of fires.
- Missing data is never zero activity.
- MODIS and VIIRS totals are not compared as if interchangeable.
- Every displayed number traces to stored observations with NASA attribution.
- Proximity is geographic screening, not fire threat.
