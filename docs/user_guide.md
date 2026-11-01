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

## Ingestion console

**Settings → Ingestion console** retrieves a bounded window from NASA FIRMS:

1. Choose a product (`MODIS_NRT`, `VIIRS_SNPP_NRT`, …). Standard Processing products are for
   historical analysis and usually lag weeks; NRT is for current monitoring.
2. Pick a start and end date — at most five days per request, because that is the API limit.
3. Optionally set a bounding box (`west,south,east,north`) to limit volume; without one the whole
   globe is requested, which can mean tens of thousands of rows per day.
4. Run it. The result shows received / inserted / rejected counts and how many partitions were
   completed or skipped.

The console is disabled when `FIRMS_MAP_KEY` is unset; the panel explains why rather than pretending
to retrieve. Recent runs below it list every attempt with its counts and status.

## Global Fire Map

The map is the Phase 4 workspace.

- **Zoom matters.** Below zoom 6 the map shows gridded cells: each dot is a number of detections
  in that cell, not a fire. Past zoom 6 it shows individual detections. The status strip tells you
  which mode you are in and how many detections are in view.
- **Colour** encodes FRP (yellow → orange → red). Dot outlines identify the sensor: blue for MODIS,
  green for VIIRS. Cells are coloured by detection density.
- **Themes**: *Daylight* (default, bright earth), *Terrain* (warm sepia land), *Paper* (near-white,
  for screenshots and print) and *Orbital* (dark field for night work). A theme changes the field,
  the basemap tone, the detection palette and the sensor outlines together, so contrast holds in
  every mode.
- **Filters**: MODIS/VIIRS toggles, minimum FRP, confidence floor, day/night, optional density
  heatmap, optional basemap.
- **Search**: type a country, a city or `lat,lon` and press Enter to fly there. The list offers
  alternative matches.
- **Inspect**: click any detection to open the panel with coordinates, UTC acquisition time,
  sensor and satellite, raw confidence plus category, brightness and channel, FRP, scan/track,
  day/night, product/version and the observation fingerprint. Thermal anomalies flagged by FIRMS
  as non-fire (volcano, static land, offshore) say so explicitly.
- **Period**: the header date range applies to the map, as it does everywhere else.

## Burning Calendar

The calendar answers "how much burning, when?" over the stored history.

- **Granularity**: Day, week, month or year. Buckets always cover the whole selected period, with
  no gaps: a day without detections still appears.
- **Months**: in Day view a month strip lists every month that holds data, with `‹ ›` to step
  through them and *Header range* to return to the header period. Selecting a month scopes the grid,
  the stat tiles and the drill-down to that month.
- **Layout**: months render as wall-calendar grids (Monday-first, whole weeks, day numbers plus the
  count per day). Selecting a cell opens the drill-down in a right-hand drawer so the grid keeps the
  full width.
- **Empty periods are labelled.** `quiet` means a source observed that period and reported no
  detections — a real zero. `unobserved` (hatched) means no availability was recorded, so it is
  not zero and is never counted as activity.
- **Metric**: detections, FRP (summed over detections), or high-confidence detection count.
- **Drill down**: select any cell or bar to see the detections behind it — time, sensor,
  confidence, FRP — and click one for its full stored provenance. Buckets larger than 200
  detections show the most recent rows and say so.
- **Export**: the drill-down and the query table both offer CSV downloads of the exact scope.
- **Scope**: counts are detections, not fires, for the period selected in the header.

### Trends, anomalies and seasonality

Below the calendar, one panel answers "is activity changing, was any day unusual, and does the year
have a seasonal shape?" It recomputes over the same window and filters as the grid, shows a
**loading cue with placeholders** while the calculation runs, and states what it could not measure.

- **Trend**: a Theil–Sen slope over observed days, shown per day and per 30 days, with direction
  (`rising`, `falling`, `flat`), a first-to-last ratio and a confidence level. Missing days break the
  sparkline instead of being drawn as zero. Fewer than ten observed days says so and shows no slope.
- **Anomalies**: the robust-z engine marks every day that exceeds the threshold (|z| ≥ 3), both as
  dots on the sparkline and as a list; selecting an entry jumps the calendar to that month. The
  calendar itself carries the marker too — a coloured dot on the day cell (amber for high, red for
  critical, blue for moderate) and the strongest severity for a week/month/year bar, always named in
  the cell's accessible label. `below_baseline` days are reported but never marked as alerts.
- **Seasonality**: twelve monthly bars. A month is only shaded when at least two years observed it
  on five or more days. With a single year the panel says `single year` and claims no index, peak or
  trough — a profile is not a climatology.
- **Caveat**: the footer repeats the language rules for the current metric (detections are not
  fires; FRP totals depend on the sensor mix).

## Regional Intelligence

Answers "how is fire activity changing in *this* place, and is this time of year
normally like this?" for a country, an imported boundary, or a radius.

- **Regions**: the catalogue is seeded from the offline gazetteer as *approximate
  boxes*, labelled `(approx.)`. Import a GeoJSON boundary or create a radius to get
  exact counts. A polygon's bounding box is only used to prefilter candidates; the
  counts come from the polygon.
- **Analyse period**: the first visit has no statistics. *Analyse period* runs one
  pass over the observations for the header period and stores regional daily
  statistics; every later view reads those rows, so the page stays fast. Nothing is
  estimated before the run — the panel says `not analyzed`.
- **Overview**: detections, coverage (analysed days, not zero-filled), peak month
  and the number of detected anomalies. A peak is only shown when a multi-year
  climatology exists.
- **Monthly seasonality**: twelve bars, each the mean of yearly monthly means. A
  month needs two years of coverage; dashed bars are withheld, and the note says
  why. With one year the status is `single year` and no peak or trough is claimed.
- **Year × month heatmap**: rows are years, columns months; a dashed cell means no
  analysed coverage, never zero.
- **Long-term trend**: Mann–Kendall on complete years with Sen's slope and a
  p-value. Fewer than eight complete years shows `insufficient years`; year-over-year
  changes are still listed without a significance claim.
- **Anomalies**: each month compared with the *same calendar month* in other years.
  Without four other years, no anomaly is claimed.
- **Sensor comparison**: MODIS and VIIRS totals, active days and a monthly
  correlation where both are present. Correlation is agreement in time, not
  calibrated equivalence.
- **Recurring activity cells**: a 0.5° screening grid inside the boundary with
  years-seen and a recurrence share. It is a plain grid, not an H3 index.
- **Export**: *CSV* downloads the monthly and yearly rows for the current region,
  period and sensor.

## Data Query (Intelligence)

The query workspace reads the stored detections directly.

- **Time window**: *From* / *To* (UTC) narrow the search to the minute, with presets for the last
  24 hours, 7 days and 30 days. Leave both empty to use the header period; a window overrides it.
- **Scope**: region (country, city or `lat,lon`), sensor, satellite, minimum FRP, confidence floor,
  day/night and whether labelled synthetic rows are included.
- **Apply**: nothing is fetched while you type; *Apply query* runs it, and the header states how
  many detections match.
- **Results**: totals (detections, MODIS/VIIRS split, FRP sum and peak, high-confidence count) come
  from the same scoped aggregate as the calendar, so the table and the totals cannot disagree.
- **Rows**: the 200 most recent matches; the matched total is exact. Selecting a row opens the
  detection's full provenance in a dialog centred on the screen — press `Esc` or click outside to
  close. Rows are detections, not fires.

## Analytics

Quantitative view of the selected period, computed from the same stored detections as the map.

- **Totals**: detections, active days against calendar days, FRP sum and peak, and the share of
  high-confidence detections.
- **Daily trend**: every day in the period, so a flat stretch is visible next to the peaks.
- **Breakdowns**: sensor (MODIS/VIIRS), day/night and confidence, each reconciling to the totals.
- **Rankings**: the busiest cells on a 2° grid, plus the satellites and products that produced them.
  A cell is an area, not a country.

## Anomaly Detection

Flags days that depart from their own recent history.

- **Method**: robust z-score against the median of the preceding observed days, scaled by
  1.4826 × MAD. One extreme day cannot inflate the baseline.
- **Gaps are excluded**: days without recorded source availability never enter the baseline, so a
  missing day cannot look like a quiet one.
- **Short history**: with fewer days than the preceding-history window needs, the engine compares
  each day with the other observed days in the window, labels it *short-history baseline*, and
  switches automatically once enough history exists.
- **No history, no claim**: below the short-history minimum the page shows the guard (available vs
  required days) rather than inventing anomalies.
- **Severity**: moderate z ≥ 3, high z ≥ 4, critical z ≥ 5, with a plain-language explanation per
  flagged day.

## Ingestion (Settings)

- **Run window** retrieves one product for the selected dates.
- **Run all sources** runs the same window for every registered product in one call, sequentially, and
  returns one result per source. A failing product does not stop the others; its error is listed.
- After either action every view refreshes — map, calendar, analytics, anomalies, query and the
  source registry — because ingestion invalidates the whole cache rather than a hand-picked subset.

## Exporting matches

On **Sensor Intelligence → Cross-sensor associations**, *Export CSV* downloads the current filter
(all / probable / possible / rejected) as a self-describing file: score, temporal delta, distance,
both observations' ids, sensors, satellites, coordinates, acquisition times, FRP, confidence,
algorithm version and creation time.

## Reports

*Reports* builds a briefing for the header period: totals, daily series, ranked cells, sensor mix,
stored matches/events, coverage and anomalies. **Markdown** and **JSON** buttons download exactly
that document. Nothing in it is model-written.

## Regional Intelligence

Countries are ranked by detections for the period. A region is the **approximate centroid box**
from the offline gazetteer (±6°), not an administrative boundary — neighbouring countries can
overlap, and the page says so.

## Exposure Analysis

Register the places you care about (name, coordinates, category), then screen them: the page shows
how many detections fell within 50 km, the strongest FRP and the nearest detection. There is no
bundled population or infrastructure dataset, so this is proximity, not a risk score.

## AI Assistant

Ask "how many detections in Nigeria?", "top activity cells", "compare MODIS and VIIRS", "any
anomalies?" and similar. Answers are computed from the same aggregates as the screens; each reply
states its intent, scope and that the method is deterministic.

## Sensor Intelligence

This is the Phase 3 workspace and the technical centrepiece of the first milestones.

- **Detection totals** cover everything stored (whole world, all time), split by sensor family.
- **Cross-sensor matches** count probable + possible associations; the hint breaks it down.
- **Associations table** lists candidate pairs (always MODIS ↔ VIIRS). Each row shows the score,
  the time difference and the geographic distance. Click a row to inspect its evidence.
- **Match evidence** panel shows the score, temporal/geographic/footprint components as bars, the
  weights note, both observations (coordinates, time, FRP, confidence), and the observation
  identifiers. The panel states that the score is *not* a probability of physical identity.
- **Estimated fire events** lists clusters with centroid, observation count, sensor count, peak FRP
  and the detection window. An event is an estimate, not a confirmed fire.
- **Re-run associations** recomputes against the period selected in the header and records a new
  algorithm run. The note under the tiles states which scope the results cover.

Everything is labelled when it comes from the synthetic fixture: a "Demo data only" banner appears
on every view that can show fixture rows.

## Reading fire data correctly

- A hotspot count is a count of **detections**, not of fires. One fire can appear many times across
  overpasses and sensors.
- MODIS and VIIRS see the world differently: 1 km versus 375 m pixels, different algorithms,
  different confidence semantics. Their totals are not interchangeable.
- Cloud, smoke and small fires affect detection. A quiet day is not proof of no fire.
- A day outside a product's coverage window is labelled `before_coverage` / `not_yet_available`, not
  zero activity.
- Proximity analysis is geographic screening, not threat assessment.
- Always attribute: NASA FIRMS (MODIS Terra/Aqua, VIIRS Suomi-NPP / NOAA-20 / NOAA-21).

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| "API offline" pill | Backend not running or wrong port | Start `uvicorn` on 8200; check `VITE_PROXY_TARGET` |
| Empty tables in Settings | API unreachable or migration not applied | Run `alembic upgrade head` |
| "No NASA data" | Expected before Phase 2, or no `FIRMS_MAP_KEY` | Set the key in `backend/.env` / root `.env` |
| Port already in use | Another service on 8000/5273 | Use 8200 for the API; Vite is pinned to 5273 |
