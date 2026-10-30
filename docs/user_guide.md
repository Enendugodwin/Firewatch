# User guide

## What you are looking at

FIREWATCH X is a global fire-intelligence console. In the current build (Phase 1) you are seeing
the operational shell: navigation, system status, configuration and the data-source registry. No
satellite observations have been ingested, so modules show an empty state rather than placeholder
numbers.

## Layout

- **Sidebar** — eleven destinations in five groups: Monitoring, History, Science, Intelligence,
  System. Each item shows a coloured dot: green = operational, cyan = in progress, grey = scaffolded.
  Collapse it with the chevrons button; on mobile it becomes a drawer.
- **Header** — breadcrumb, module search, observation period, data-freshness indicator, notices,
  theme toggle, profile.
- **Workspace** — the active module.
- **Status bar** — phase, selected period, source count, database dialect, live UTC clock, API
  version and the NASA disclaimer.

## Keyboard

| Keys | Action |
| --- | --- |
| `Ctrl`/`Cmd` + `K` | Open the module palette |
| `/` | Open the palette (when not typing in a field) |
| `↑` / `↓` | Move through palette results |
| `Enter` | Go to the highlighted module |
| `Esc` | Close the palette or the mobile drawer |

## Observation period

The period control in the header sets the range every module will query once data exists: last 24
hours, 7, 30 or 90 days, or a custom start/end date. All dates are UTC. The selection persists
between visits and is echoed in the status bar.

The period is a query parameter today and a real filter in Phase 2+. It never changes what is
displayed without the API returning matching observations.

## Data freshness

The header pill reads from `/api/v1/system/status`, not from page reloads:

| Label | Meaning |
| --- | --- |
| **No NASA data** | No observations are stored. Typical for a fresh install or a missing FIRMS key |
| **Current / Delayed / Stale** | Age of the newest stored observation, once ingestion runs |
| **API offline** | The backend is unreachable; all figures are withheld |

Click it for the reason, source count, key state, database state and last ingestion time.

## Notices

The bell lists derived system notices: missing FIRMS key, no ingested data, unreachable database,
missing PostGIS extension and the current delivery phase. These are statements about *system state*,
not fire alerts. Alerts about fire activity require verified data and arrive later.

## Modules and what "scaffolded" means

Each module page shows its status from the backend registry:

- **Scaffolded** — route, layout and API contract exist; no analysis yet.
- **In progress** — partially implemented in the current phase.
- **Operational** — implemented and covered by tests.

Every scaffolded page lists the capabilities planned for it, the API endpoints it will use (all
currently returning `501 not_implemented`), and the prerequisites before it can display data. This
is deliberate: the console never shows a number it cannot trace to stored NASA observations.

## Settings & administration

- **Data sources** — the eight NASA FIRMS products (four standard-processing, four near-real-time)
  with their ingestion state. All are `not_ingested` until Phase 2.
- **Required configuration** — which environment variables are present, with the exact form each
  takes. `FIRMS_MAP_KEY` is backend-only.
- **Capabilities** — authoritative flags for authentication, rate limiting, ingestion, spatial
  queries, reports and the AI assistant.
- **Deployment notes** — the security posture: no authentication yet, bind to localhost or a
  trusted network.

## Reading fire data correctly (for when data arrives)

- A hotspot count is a count of **detections**, not of fires. One fire can appear many times across
  overpasses and sensors.
- MODIS and VIIRS see the world differently: 1 km versus 375 m pixels, different algorithms,
  different confidence semantics. Their totals are not interchangeable.
- Cloud, smoke and small fires affect detection. A quiet day is not proof of no fire.
- Proximity analysis is geographic screening, not threat assessment.
- Always attribute: NASA FIRMS (MODIS Terra/Aqua, VIIRS Suomi-NPP / NOAA-20 / NOAA-21).

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| "API offline" pill | Backend not running or wrong port | Start `uvicorn` on 8100; check `VITE_PROXY_TARGET` |
| Empty tables in Settings | API unreachable or migration not applied | Run `alembic upgrade head` |
| "No NASA data" | Expected before Phase 2, or no `FIRMS_MAP_KEY` | Set the key in `backend/.env` / root `.env` |
| Port already in use | Another service on 8000/5173 | Use 8100 for the API; Vite is pinned to 5173 |
