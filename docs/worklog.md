# Worklog — FIREWATCH X, day 1 onward

A chronological record of what was built, what was measured, and what was found
to be wrong. The feature docs elsewhere describe *how* things work; this page
records *when* and *with what evidence*, so a later reader can tell a delivered
claim from an intention.

Every entry is anchored to commits on `main`. Numbers are from this workstation
(Windows, 32 GB RAM, portable PostgreSQL 16) and were measured, not projected.
Where something was not measured, the entry says so.

---

## Day 1 — 2026-10-30: foundation and design language

Commits `2deba1f` (03:41), `47032c0` (13:24).

- Phase 1: React/Vite console, FastAPI service, database layer, migrations,
  typed API client, navigation shell, module registry that refuses to report a
  phase as ready before it lands.
- Adopted the **Orbital Intelligence** design language: near-black field
  `#131315`, deep-navy glass, one green accent `#60D58B`, Newsreader display /
  Inter interface / JetBrains Mono measurements. Fire severity keeps a separate
  amber-orange-red scale so chrome never looks like hazard.
- Moved development ports off the usual 5173/8100 to **5273** (web) and
  **8200** (API), which they still use.

Evidence: `docs/architecture.md`, `docs/design.md`, `README.md` design section.

## Day 2 — 2026-10-31: ingestion through calendar (phases 2–5)

Commits `d4b53e5`, `ce106ce`, `8f92623`, `ad71038`, `a6d5ec5`, `fb87364`,
`6d648ab`.

- NASA FIRMS client with retries/backoff, `Retry-After`, redacted key, honest
  failure modes; resumable ingestion keyed by `(source, tile, date_start)`;
  separate MODIS and VIIRS normalisation with raw payloads retained.
- Availability model: a day inside a product's coverage is *observed*, even with
  no detections; outside coverage it is `before_coverage` / `not_yet_available`.
  Missing is never zero.
- Harmonisation (`S = w_t·T + w_g·G + w_f·F`) with probable / possible /
  rejected and full score components; spatiotemporal event grouping.
- Global fire map: MapLibre globe, viewport aggregation (never the whole table),
  four themes, filters, search, per-detection provenance.
- Calendar: day/week/month/year buckets with coverage states and drill-down.

First live verification (recorded in `README.md`): 4,100 observations in scope →
659 candidate pairs (29 probable, 157 possible) → 587 estimated events, 158 seen
by both sensors.

## Day 3 — 2026-11-01: from demo to instrument

Seventeen commits, `b9b827e` through `76bd312`.

- **Moved the live store to PostgreSQL 16** (`b9b827e`); SQLite stays the
  zero-setup path for tests. Bulk ingestion switched to `COPY`.
- Aggregation rollups (`5730807`): day- and cell-level precomputation so
  analytics stopped re-scanning 11.3 M rows per request.
- Cloud preparation (`22faa20`): storage interface (local + S3/R2), Parquet
  export with Zstandard, size + SHA-256 verified sync, readiness page.
- Calendar intelligence and anomalies marked directly in the grid
  (`13ad502`, `e8d8459`); regional trend/seasonality engine (`76bd312`).
- Reports, regions, exposure, deterministic assistant, hardening and deployment
  docs (`f71fa38`).
- `start.bat` / `stop.bat` with a WMI-detached launcher (`237f998`).
- Resumable 60-day backfill with a partition-based progress bar (`cc2e609`).
- Calendar reworked into a real month grid + month picker (`6c61734`, `3e061fc`).

Evidence: `docs/delivery_report.md`, `datastructure.md`, `docs/operations.md`.

## Day 4 — 2026-11-02: performance and scientific honesty

Commits `9455d55`, `9acb5c8`, `d9dd1f7`.

- Map latency and resource pressure cut; rollups made incremental.
- Month-vs-median headline added to regional intelligence.
- Map loading cues; harmonised composite series exposed alongside the raw series;
  reference-fire validation page and `docs/validation/reference_fires.md`.
- Colour accessibility reviewed for the harmonised series.

## Day 5 — 2026-11-03: archive scale, and an honest diagnosis

Commits `3e96087`, `04c35fe`, `732b139`, `60d5b9c`, `e244ccd`, `1e76b21`.

### The "empty archive" was a coverage bug

Standard-processing products always had history. The earlier "SP returns zero
rows" came from requesting September–November 2026, *after* the SP coverage end
(MODIS to 2026-08-31, VIIRS SNPP to 2026-07-31, NOAA-20 to 2026-07-31, NOAA-21
to 2026-07-31). FIRMS answers with a header-only 200, which was recorded as
`empty` — "observed, no detections" — making unprocessed days look quiet.

Fixes: coverage is read first and the window clamped; ingestion verifies
coverage before recording `empty`; `scripts/repair_availability.py` relabelled
**213** mislabelled rows.

### Archive built

- Amazon MODIS 2016–2024: **1,205,718 rows in 55.8 min**, 0 rejected
  (`docs/historical_backfill.md`).
- Harmonisation at archive scale: migration `0010_harmonization_coverage`, one
  UTC day per transaction, checkpoint per day (missing row = not scanned).
  2026 pass: 61 days, 11.24 M observations, **2.48 M pairs** (168 k probable,
  788 k possible), 27 min.
- Latitude-banded candidate selection: 376 s → 2.7 s per 130 k-observation day.
- Harmonised calendar metric: raw 11,477,404 / matched 787,585 / harmonized
  10,689,819 (7.3 %) at the time of the run.
- Calendar span raised from 6 to 30 years so nine-year history is visible.
- `scripts/accuracy_report.py` + `docs/validation/accuracy.md`: cross-sensor
  corroboration 12.0 % (Pará) and 12.1 % (Kalimantan). Burned-area agreement
  explicitly **not measured**.

### Reusable long runs

- `app/services/history_runner.py` and `scripts/history.py` (`plan` / `run`),
  durable `history_jobs` rows, dataset presets (`modis_history`,
  `viirs_snpp_history`, `all_history`, `nrt`, `all_products`), API under
  `/history`, docs `docs/history_jobs.md`.
- A `running` job untouched for 900 s is `stale` and resumable; a live one
  cannot be overlapped (`60d5b9c`).
- **Incident:** the first VIIRS run died with
  `QueryCanceled: canceling statement due to statement timeout` because
  `refresh_rollup(since=2016-01-01)` rebuilt nine years in one pass. Fixed by
  `refresh_rollup_range` so only changed days are rebuilt (`e244ccd`).

## Day 6 — 2026-11-04: nine-year archive completed, measured, and removed

Commits `fa6c1df`, plus the deletion itself.

- Resumed VIIRS job `a59dccd8` finished: **1,316 / 1,316 windows, 0 failed**,
  1,414,440 rows in the resumed run. Amazon total **6,001,558** detections
  (MODIS 1,220,350 / VIIRS 4,781,208), wall clock 180.1 min including
  harmonisation.
- Harmonisation of all **3,288 days**: 4,535,583 pairs → 752,355 probable,
  1,820,684 possible, 1,962,544 rejected; **1,458,779** VIIRS detections carry a
  MODIS association (30.5 %); **harmonized total 4,542,779**.
- Accuracy report regenerated unchanged (12.0 % / 12.1 %); burned-area agreement
  still explicitly not measured.
- Summary kept in `docs/validation/amazon_history_2016_2024.md`; the rows were
  then deleted at the owner's request.
- **Incident while deleting:** cascading FK checks re-scanned
  `event_observations` (no index on `observation_id`) once per observation and
  ran for 73 min without finishing. The teardown now materialises ids, hash-
  joins, and suspends FK triggers while deleting children explicitly, in one
  transaction. Result: 5,501,558 observations and 6,001,558 raw rows removed,
  rollups rebuilt over the range, store **33 GB → 19 GB**.
- Verified after: 11,859,005 observations (all 2026), `region:amazon` partitions
  and runs at 0, calendar for 2026-09 still serving, `/health` ok.

## Day 7 — 2026-11-04 (later): retention, admin portal, harmonized map

A second working block on the same day, after the Amazon teardown.

- **Raw payload retention.** New `raw_retention_days` (90), the
  `scripts/retention.py` dry-run/apply/VACUUM command, and an admin endpoint.
  Applied on the live store: **240,953** payload rows before 2026-08-06 deleted
  (2019-12 and 2024-12 fixtures, 2026-08-01→05), `VACUUM FULL` returned
  731 MB (`7,664 MB → 6,933 MB`). Canonical observations stayed at
  **11,944,746**; September raw rows stayed at **5,977,671**.
- **Export-before-delete portal.** `raw_exports` records the range, rows, size
  and SHA-256 of a CSV.GZ archive. Deletion of a range requires that checksum
  and refuses if the row count changed. Exports cover at most 62 days and only
  payloads older than 5 days, so live ingestion is never captured mid-flight.
  New pages: `/admin` (portal) with inventory, exports, retention and the FIRMS
  key; API under `/api/v1/admin/raw/*`.
- **FIRMS key in the portal.** `app_settings` stores the MAP_KEY server-side;
  the value is write-only over the API and reads return a masked fingerprint.
  Startup reloads it, `build_client()` picks it up from the process settings, and
  `POST /admin/settings/firms/test` verifies it against FIRMS availability.
- **Harmonized map view.** A map toggle (and filter checkbox) requests
  `harmonized=true`. The backend excludes VIIRS detections with a
  probable/possible MODIS association from both GeoJSON and viewport
  aggregation, so the map totals match the harmonized-series definition. Rollup
  cells cannot express the exclusion, so harmonized requests always use the
  live scan and the response says `source: live`.
- **Cloud boundary.** Added a guard test that the Parquet export columns contain
  no raw payload; `docs/cloud.md` states that only analysis is uploaded and raw
  payloads are recreatable and pruned locally.
- **Overlapping harmonization runs fixed.** A second Re-run Associations request
  could collide on `uq_observation_matches_pair` and return a 500. Passes are now
  serialized behind a process lock plus a PostgreSQL transaction advisory lock,
  and a rejected pass returns **409** with *"A harmonization run is already in
  progress"*. Reproduced with two concurrent requests (500 + 200), verified
  after the fix (409 + 200).
- **Performance pass.** The harmonized map view was blank because it bypassed
  the cell rollup and hit the 60 s statement cap; `cell_activity` now stores
  matched/harmonized counts and the world view is **0.03?0.05 s**. Calendar
  matched counts read the rollup (**1.48 ? 0.05 s**), match rows carry an
  indexed `match_day` (**matches 1.73 ? 0.08 s**), dashboard totals come from
  `daily_activity` (**2.16 ? 0.74 s**, cached 15 s), and the harmonization summary reads rollup sensor totals (**1.73 ? 0.28 s**). The map accepts
  `?harmonized=1` so the view is shareable, and a dedicated screenshot was added.
- **Sensor Intelligence period scoping.** The page used to show whole-store detection totals
  beside matches from the last run. `/harmonization/summary`, `/matches`, `/matches.csv` and
  `/events` now accept `start_date`/`end_date`; the page passes the header period and says so,
  and the CSV export inherits it. Reversed periods return 422. Verified live for 2026-10-29 ?
  2026-11-04: **808,966** detections, **87,271** stored match rows, **3,088** events.
- **Incident: bulk ingestion 500s.** A global four-day VIIRS window (~324k rows)
  exceeded the 60 s `statement_timeout` applied to every PostgreSQL connection and
  surfaced as *Internal server error* from `/admin/ingestion/run`. Fixed by applying
  `SET LOCAL statement_timeout` per ingest window (`INGESTION_STATEMENT_TIMEOUT_MS`,
  default 15 min); the interactive read cap stays at 60 s.
- **Incident: resume keyed only on the window start.** A one-day run could mark a
  four-day window starting on the same day as succeeded and skip three days. The
  resume check now requires the stored `date_end` to match the window.
- **August 2026 retry.** Re-ran the failed VIIRS windows for 2026-08-01 ? 08-04:
  SNPP, NOAA-20 and NOAA-21 all succeeded (188,523 / 324,254 / 314,808 received),
  adding **807,176** canonical detections; bulk rollups refreshed. Store now
  **12,772,331** observations, **12,533,378** raw payloads, **21 GB**.
- **Cloud gate.** Administrative writes now require `X-Admin-Token` when
  `ADMIN_TOKEN` is configured; `ENVIRONMENT=production` with no token refuses
  writes (`503`) instead of exposing ingestion and deletion. The Admin Portal
  stores the token in the tab's session storage; `apiFetch` attaches it.
- **CI and disaster recovery.** `.github/workflows/ci.yml` runs ruff, mypy,
  pytest, vitest, typecheck and build. `scripts/backup_database.py` writes a
  custom-format dump plus SHA-256 sidecar; `scripts/restore_database.py` verifies
  the checksum and refuses to overwrite the live database. Drill: a **2.77 GB**
  dump restored into a scratch database with exact row counts on
  observations, raw, matches, cells, daily rollup and events; scratch database
  dropped afterwards.
- **Tests:** backend **236**, frontend **74**; ruff and mypy clean; production
  frontend build succeeded. Two pre-existing test issues were repaired along the
  way: the harmonization scope test now waits for the scope payload instead of
  matching the header date twice, and jsdom's canvas stub no longer produces an
  unhandled error.

## Day 8 ? 2026-11-05: auth, rate limiting, report formats, data deletion

- **Authentication & RBAC.** `users` + `auth_sessions`; Argon2id hashes, roles
  `admin` / `analyst` / `viewer`, HttpOnly session cookies, login/logout/me and
  user administration. The Admin Portal has an operator sign-in page; the
  break-glass `X-Admin-Token` still works. Capability reports now say
  `authentication: true`.
- **Rate limiting** was already implemented; the capability flag is now honest
  and the cloud runbook enables it (`RATE_LIMIT_PER_MINUTE=120`).
- **Reports & exports.** PDF (reportlab), CSV (daily series with methodology
  comments), GeoJSON (top cells with methodology in the collection properties),
  JSON and Markdown. Every format carries the methodology and limitations.
- **Assistant.** The deterministic, database-backed assistant is reported as
  available; it never invents measurements.
- **Admin data deletion.** `/admin/ingestion/runs/{id}/preview` shows what a run
  owns; `.../delete` removes canonical + raw rows, matches, event memberships,
  availability, coverage and partitions, rebuilds rollups, and keeps the run row
  marked `deleted` for audit. The Admin Portal lists runs with this action.
- **Admin console completed.** Accounts/roles, ingestion (single window, all sources,
  availability), historical backfill jobs (start/cancel/resume), harmonization,
  rollup rebuilds, cache reset, ingestion-run preview/delete, FIRMS key and raw
  retention now live in one console.
- **Portal gating and close-out.** The Admin Portal link and route require an
  authenticated administrator; the delivery meter was removed from the sidebar
  and every module now reports `ready` (12 of 12). First admin created with
  `scripts/create_admin`.
- **Handover:** `docs/handover.md` records access, secrets policy, local/container setup,
  the code map, runbooks, verification, incidents and a first-day checklist.
- **Harmonized map legibility.** Because only ~3?4% of detections are duplicates, raw and
  harmonized cell colours are usually identical. Cells that lost duplicates now get an amber
  outline and the status strip reports the removed count; the aggregate response carries
  `matched_viirs` per cell.
- **Tests:** backend **241**, frontend **76**; auth, report formats and deletion
  covered, plus frontend login and ingestion-run deletion preview.

## Where the evidence lives

| Claim | Evidence |
| --- | --- |
| Phase delivery | `README.md` roadmap, `docs/delivery_report.md` |
| Decisions and non-negotiables | `docs/architecture.md`, `docs/design.md` |
| Schema and stored model | `datastructure.md`, `docs/data_dictionary.md` |
| Harmonisation formula and thresholds | `docs/methodology.md` |
| Archive coverage and measured ingest | `docs/historical_backfill.md` |
| Long-run jobs | `docs/history_jobs.md`, `/api/v1/history` |
| Cross-sensor corroboration | `docs/validation/accuracy.md` |
| Nine-year Amazon run and its removal | `docs/validation/amazon_history_2016_2024.md` |
| Everything at commit level | `git log --date=short` (36 commits, 2026-10-30 → 2026-11-04) |

## Known gaps at the end of day 6

These are deliberately listed here so nobody reads the delivery report as a
claim that they are done:

- No CI pipeline and no automated backup/restore drill.
- Authentication exists (`backend/app/auth.py`) but is not enforced; the console
  must stay on localhost/firewalled.
- Real Cloudflare R2 upload/verification has not been exercised (no credentials
  on this host).
- Burned-area calibration needs an external MCD64A1/GFED table; the Planetary
  Computer STAC endpoint failed DNS from this host.
- Nothing has been pushed to `Enendugodwin/Firewatch`: the `firewatch_deploy`
  key is not registered on GitHub.
- The map uses a 0.5° screening grid rather than H3, and boundaries are GeoJSON
  + Shapely rather than PostGIS, because neither extension is installed here.
