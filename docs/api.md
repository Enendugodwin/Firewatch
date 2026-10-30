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
| Dashboard | `/dashboard` | 4 |
| Fires | `/fires`, `/fires/geojson` | 2 / 4 |
| Calendar | `/calendar` | 5 |
| Harmonization | `/harmonization/summary`, `/harmonization/matches` | 3 |
| Anomalies | `/anomalies` | 6 |
| Regions | `/regions` | 6 |
| Exposure | `/exposure` | 6 |
| Reports | `/reports` | 7 |
| Assistant | `POST /assistant/chat` | 7 |
| Admin | `/admin/ingestion/jobs` | 2 |
| Auth | `POST /auth/login` | 8 |

## Example requests

```bash
curl -s http://127.0.0.1:8100/api/v1/system/status | jq '.data'
curl -s -i http://127.0.0.1:8100/ready
curl -s http://127.0.0.1:8100/api/v1/fires | jq '.error.details.planned_for_phase'   # "Phase 2"
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
