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
| `firms_ingestion` | Phase 2 — implemented | `services/firms/`, `services/ingestion.py` |
| `normalization` | Phase 2 — implemented | `services/normalization.py` |
| `harmonization` | Phase 3 — implemented | `services/harmonization.py`, `services/events.py` |
| `geospatial` | Phase 4 — implemented | `services/map_aggregation.py`, `services/gazetteer.py` |
| `calendar` | Phase 5 | `services/calendar` |
| `anomaly_engine` | Phase 6 | `services/anomalies` |
| `exposure_engine` | Phase 6 | `services/exposure` |
| `reporting` | Phase 7 | `services/reporting` |
| `ai_assistant` | Phase 7 | `services/assistant` |
| `notification_engine` | Phase 7 | `services/notifications` |
| `auth` | Phase 8 | `services/auth` |
| `audit` | Phase 8 | `services/audit` |

## Phase 2/3 decisions worth knowing

**Partitions are the unit of work.** `(source, tile, date window)` is recorded before a request and
marked succeeded after the rows are committed, so a backfill can be stopped and resumed without
duplicating records. Ingestion commits per window.

**Two identities, two layers.** Raw payloads are kept verbatim with a content hash; normalized rows
carry a fingerprint derived from the measurement itself (FIRMS supplies no row id). Both layers are
unique on `(source_id, source_record_id)`, so re-ingestion is a no-op rather than a duplicate.

**Analysis is scoped, not global.** Every harmonization and event run records its `scope` (bbox and
dates) in `algorithm_runs`, and the console states which scope the displayed associations cover.
Detection totals stay global — the two are labelled separately so a scoped result is never read as
a global measurement.

**Provenance scopes never blend.** Synthetic fixture rows (`is_synthetic = true`) are harmonized
separately from real observations; there is no code path that compares the two.

**Scores are association scores.** The UI calls them that, stores every component, and never
converts them into a probability of physical identity.

## Phase 4 decisions worth knowing

**The map never downloads the dataset.** Below zoom 6 the server returns gridded counts
(`/fires/aggregate`), one row per cell with detection counts by sensor and the strongest FRP.
Past zoom 6 the client requests bounded GeoJSON for the viewport, capped at 5,000 features and
labelled `truncated` when the cap is hit. This is the difference between a map and a bulk export.

**Cells are counts, not fires.** A cell's radius and colour encode how many detections fell inside
it (and FRP only as cell metadata), so a single intense detection cannot recolour a whole cell or
masquerade as one fire.

**Search is offline.** `services/gazetteer.py` ships approximate country and city centroids plus
`lat,lon` parsing, so geographic search needs no API key and no third-party geocoder. Results are
navigation aids, not authoritative boundaries.

**Themes are one contract, four looks.** `components/map/mapStyle.ts` holds the theme table:
field colour, basemap paint, detection palette, sensor outlines, cell opacity and heat ramp. A theme
change re-applies paint to existing layers instead of rebuilding the style, so switching never
refetches data. Bright themes use deep detection colours and thick white outlines; the dark theme
keeps the luminous palette. Bright earth is the default because the signal stays legible in
daylight and on projectors.

**The basemap is optional and attributed.** An OSM raster layer is heavily desaturated and
darkened to sit inside the orbital palette; turning it off leaves a pure dark field with the data.
Tile failures degrade to the dark canvas rather than breaking the map.

## Foundation decisions worth knowing

**Honest empty states over sample data.** Analytical routes exist in OpenAPI from day one but
raise `AppError("not_implemented")`, rendered as:

```json
{"error": {"code": "not_implemented", "message": "…",
           "details": {"current_phase": "Phase 4", "planned_for_phase": "Phase 5"},
           "request_id": "…"}}
```

The UI treats `501` as "contract published, implementation pending", which keeps navigation and
documentation honest while later phases are built.

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
