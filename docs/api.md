# API

Base path: `/api/v1`. Interactive documentation: `/api/docs` (OpenAPI JSON at
`/api/openapi.json`). Everything is JSON; timestamps are ISO-8601 UTC.

## Error envelope

Every failure — validation, not-found, not-implemented, internal — uses one shape:

```json
{
  "error": {
    "code": "not_implemented",
    "message": "Observation search is not implemented yet.",
    "details": {"module": "Observation search", "current_phase": "Phase 1",
                "planned_for_phase": "Phase 2"},
    "request_id": "3f9c…"
  }
}
```

| Code | HTTP | Meaning |
| --- | --- | --- |
| `bad_request` | 400 | Malformed request |
| `unauthorized` / `forbidden` | 401 / 403 | Auth (Phase 8) |
| `not_found` | 404 | Unknown route or record |
| `unprocessable` | 422 | Schema validation failed; `details.errors` lists fields |
| `rate_limited` | 429 | Client exceeded its budget |
| `not_implemented` | 501 | Contract published, module pending — **never fake data** |
| `unavailable` | 503 | Dependency down (database, upstream) |
| `internal_error` | 500 | Unexpected failure, logged with the request id |

Every response carries `X-Request-ID` (echoed if supplied) and `X-Process-Time-Ms`.

## Probes (no version prefix)

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/health` | Liveness. 200 `{"status":"ok","service":"FIREWATCH X","version":"0.1.0"}` |
| GET | `/ready` | Readiness. Probes the database; 503 with `database.error` when unreachable |

## System

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/system/status` | Phase, uptime, database probe, data freshness, capabilities, modules |
| GET | `/system/modules` | Module registry: key, label, route, phase, status, planned capabilities |
| GET | `/system/sources` | The eight registered NASA FIRMS products with ingestion state |

`/system/status` is the honesty surface. In Phase 1 it returns:

```json
{
  "data": {
    "freshness": "no_data",
    "freshness_reason": "FIRMS_MAP_KEY is not configured, so no NASA observations can be retrieved…",
    "firms_configured": false,
    "sources_registered": 8,
    "observations_stored": null,
    "last_ingested_at": null,
    "last_observation_at": null
  },
  "capabilities": {"authentication": false, "ingestion": false, "spatial": false, "...": false}
}
```

## Published but pending

These routes exist so the contract is fixed before implementation. All currently return `501`.

| Group | Paths | Phase |
| --- | --- | --- |
| Calendar | `/calendar` | 5 |
| Anomalies | `/anomalies` | 6 |
| Regions | `/regions` | 6 |
| Exposure | `/exposure` | 6 |
| Reports | `/reports` | 7 |
| Assistant | `POST /assistant/chat` | 7 |
| Auth | `POST /auth/login` | 8 |

## Implemented (Phases 2–3)

### Observations

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/fires` | Filters: `bbox`, `start_date`, `end_date`, `sensor`, `satellite`, `min_frp`, `daynight`, `synthetic`; `limit` ≤ 5000, `offset` |
| GET | `/fires/{id}` | Full record including `quality_flags` and fingerprint |
| GET | `/fires/sources` | Counts and last-seen per product |
| GET | `/fires/geojson` | Bounded FeatureCollection plus `truncated`/`total` |

### Map

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/fires/aggregate` | Required `bbox`, `zoom` 0–14; returns cells with counts by sensor, max FRP, cell size and total |
| GET | `/fires/geojson` | Bounded FeatureCollection (≤5,000) with `truncated`/`total` |
| GET | `/geo/search` | Offline country/city centroids and `lat,lon` parsing |

Filters shared by `/fires`, `/fires/geojson` and `/fires/aggregate`: `bbox`, `start_date`,
`end_date`, `sensor`, `satellite`, `min_frp`, `daynight`, `min_confidence` (`low|nominal|high`) and
`synthetic`.

Window: `start_at` / `end_at` take ISO 8601 timestamps (`2026-10-30T06:00:00Z`). `start_at` is
inclusive, `end_at` exclusive, and both override the date-only bounds — that is how an hour-level
query is expressed. An unordered window returns `400 bad_request`.

### Calendar

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/calendar` | Required `start_date`, `end_date`; `granularity` day/week/month/year |
| GET | `/calendar/drilldown` | `bucket_start` + `granularity`; returns the bucket plus its detections |

Every bucket in the range is returned, including empty ones, with `state`
(`active` / `quiet` / `unobserved`), per-day coverage counts from source availability, and six
metrics: detections, MODIS, VIIRS, FRP sum, FRP max and high-confidence count. Filters are the same
as `/fires` (`bbox`, `sensor`, `satellite`, `min_frp`, `daynight`, `min_confidence`, `synthetic`).

### Analytics and anomalies

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/analytics/summary` | Required `start_date`/`end_date`; totals, daily series, top cells, breakdowns |
| GET | `/anomalies` | Required `start_date`/`end_date`; robust-z scoring with a short-history fallback |
| GET | `/harmonization/matches.csv` | CSV export of matches with both observations' provenance |
| POST | `/admin/ingestion/run-all` | Same window for every registered source, one result per source |

`/analytics/summary` returns every day in the range (zeros included), the peak day, rankings on a
fixed 2° grid (cells, never countries), sensor/confidence/day-night splits and satellite/product
counts. `/anomalies` compares each observed day with the median of the preceding
`baseline_days` observed days and scores the deviation as `(x − median) / (1.4826 × MAD)`.
If MAD is zero the standard deviation is used as the scale. When there is not enough preceding
history the engine falls back to a leave-one-out baseline over the evaluated window
(`method.baseline_source = within_window`, needs `min_window_days`, default 4) and says so;
with too few days even for that it returns `status: insufficient_history` and `requirements`.

### Harmonization

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/harmonization/summary` | Sensor totals, match counts, events, last run and its scope |
| GET | `/harmonization/matches` | `status`, `min_score`, pagination; full score components |
| GET | `/harmonization/matches/{id}` | Evidence for one pair |
| GET | `/harmonization/events` | Estimated events with extent and FRP aggregates |
| POST | `/harmonization/run` | Body: `synthetic?`, `bbox?`, `start_date?`, `end_date?`, thresholds, `run_events` |
| GET | `/harmonization/jobs`, `/jobs/{id}` | Algorithm run history and status |
| GET | `/harmonization/status` | Engine versions, defaults and disclaimers |

### Ingestion administration

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/admin/ingestion/run` | `source_code`, `start_date`, `end_date` (≤5 days), `bbox?` or `tile?`; optional harmonization/events |
| GET | `/admin/ingestion/jobs` | Recent runs with counts and query parameters |
| GET | `/admin/ingestion/sources` | Registered state, observations, last run and error |
| GET | `/admin/ingestion/tiles` | `world` plus deterministic global tiles |
| POST | `/admin/ingestion/availability` | Coverage window → per-date status |

### Dashboard

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard` | Detection totals by sensor, FRP sum, match counts, events, freshness |

Without `FIRMS_MAP_KEY`, `POST /admin/ingestion/run` returns `503 unavailable` with a hint — it never
simulates a retrieval.

## Example requests

```bash
curl -s http://127.0.0.1:8200/api/v1/system/status | jq '.data'
curl -s -i http://127.0.0.1:8200/ready
curl -s http://127.0.0.1:8200/api/v1/fires | jq '.error.details.planned_for_phase'   # "Phase 2"
```

Planned query shapes once implemented (from the specification):

```
GET /api/v1/fires?bbox=-5,4,15,14&start_date=2026-01-01&end_date=2026-01-31&sensor=VIIRS
GET /api/v1/calendar/yearly?region_id=NG&year=2026&metric=raw_detections
```

## Access control

No authentication exists yet (Phase 8). The console must therefore be bound to localhost or a
trusted network. Expensive endpoints — historical ingestion, harmonization runs, report generation
— will be restricted to `ADMIN`/`ANALYST` roles when auth lands.
