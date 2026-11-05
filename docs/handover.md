# Handover — FIREWATCH X

Everything a teammate needs to run, operate, extend and deploy the platform.
Last updated **2026-11-05** from commit `8840aaa` (CI green).

> Do not put secrets in this file or anywhere in git. `.env` is ignored; hand it
> over out-of-band (password manager or encrypted transfer).

## 1. What this is

FIREWATCH X is a NASA FIRMS fire-intelligence platform: ingestion, sensor
normalisation, MODIS/VIIRS harmonisation, event clustering, a global map, a
coverage-aware calendar, analytics, anomalies, regions, exposure, reports, a
deterministic assistant, and an authenticated admin console.

Current store on the original workstation:

| Item | Value |
| --- | --- |
| Canonical detections | 5,206,277 |
| Raw payloads | 5,206,277 (same 30-day window) |
| Database size | ~8.5 GB (PostgreSQL 16) |
| Coverage | 2026-08-01 → 08-05 (partial) and 2026-09-02 → 2026-11-03 NRT, plus two fixture months |
| Tests | 241 backend / 76 frontend |
| CI | GitHub Actions: backend, frontend, compose validation |

Repository: <https://github.com/Enendugodwin/Firewatch> (branch `main`).

## 2. Access and secrets

### Accounts

An administrator already exists: **`admin@firewatch.local`**. Its password was
delivered separately; **rotate it on first sign-in** (Admin Portal → Operator
accounts → Reset password). Create a named account for each teammate from the
same page:

- `admin` — everything: accounts, ingestion, deletion, keys, retention.
- `analyst` — ingestion, harmonization, history, regions; no account or delete
  controls.
- `viewer` — read-only.

All passwords are Argon2id hashes; sessions are server-side and revocable.
Sign in at `/login`. The Admin Portal is hidden from unauthenticated visitors.

### Environment file

Copy `.env.example` to `.env` and fill in. Relevant keys:

```env
ENVIRONMENT=local              # production enforces ADMIN_TOKEN
DATABASE_URL=postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch
FIRMS_MAP_KEY=...              # or save it from the Admin Portal
ADMIN_TOKEN=...                # break-glass credential; required in production
CORS_ORIGINS=http://127.0.0.1:5273
RATE_LIMIT_PER_MINUTE=0        # set 120 for public deployments
INGESTION_STATEMENT_TIMEOUT_MS=900000
```

Cloud-only: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `CLOUD_DATABASE_URL`.

## 3. Run it locally (Windows)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, and the
portable PostgreSQL 16 binaries at `C:\Users\<you>\pgsql\pgsql`.

```powershell
cd C:\Users\<you>\NASA
Copy-Item .env.example .env       # then edit
.\start.bat                       # PostgreSQL:5433, API:8200, web:5273
.\stop.bat
```

Logs and PID files are under `logs/`. First run installs backend/frontend
dependencies. If PostgreSQL is managed separately:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_postgres.ps1 -Port 5433
cd backend
uv sync --group dev
uv run alembic upgrade head
uv run python -m scripts.seed_sources
uv run uvicorn app.main:app --port 8200
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # proxies /api to 127.0.0.1:8200
```

### Containers

```bash
cp .env.example .env      # set POSTGRES_PASSWORD, FIRMS_MAP_KEY, ADMIN_TOKEN
docker compose up --build
```

API on `:8200`, web on `:8088`. The API container waits for the database, runs
migrations, seeds the source registry and serves. See `docs/deployment.md`.

## 4. Code map

```
backend/
  app/main.py                 app factory, lifespan, CORS, rate limit
  app/core/                   config, logging, errors, cache, security, modules
  app/api/v1/                 system, dashboard, fires, calendar, analytics,
                              anomalies, regions, exposure, reports, assistant,
                              harmonization, history, admin, admin_settings,
                              raw_archive, auth
  app/services/               ingestion, harmonization, events, rollups,
                              reports, assistant, auth, ingestion_deletion,
                              raw_archive, app_settings
  app/db/models/              observations, ingestion, harmonization, regions,
                              exposure, auth, app_settings, raw_exports
  app/storage/                local + S3/R2 providers, dataset sync
  migrations/versions/        Alembic chain 0001 → 0016
  scripts/                    operational CLIs (see §6)
  tests/                      241 pytest tests (SQLite by default)
frontend/
  src/pages/                  one page per module + Admin + Login
  src/components/admin/       ServiceControls (accounts, ingestion, history,
                              maintenance)
  src/components/map/         MapLibre layers, filters, aggregation hook
  src/lib/                    API clients, query hooks, formatters
docs/                         architecture, methodology, operations, cloud,
                              performance, worklog, this handover
```

Invariants that must not be broken:

- Counts are **detections**, not fires; MODIS and VIIRS counts are separate.
- A day with no availability data is **unobserved**, never zero.
- Synthetic fixture rows are labelled and never mixed with real data.
- The map never downloads the full dataset; it uses rollups/live viewport queries.
- Raw payloads are local-only; cloud exports carry analysis only.
- Nothing is deleted without a preview and, for raw exports, a checksum receipt.

## 5. Data and schema

Migrations are the source of truth. Current head: `0016_auth_rbac`.
Highlights:

- `fire_observations` — canonical detections (`run_id` links provenance).
- `raw_observations` — immutable source payloads; pruned on a 90-day policy.
- `observation_matches` — scored MODIS↔VIIRS associations (`match_day` indexed).
- `cell_activity` — day × 2° cell × sensor rollup, including `matched_viirs` and
  `harmonized` counts used by the map.
- `daily_activity` — day × sensor × confidence × day/night × satellite rollup.
- `ingestion_runs` / `ingestion_partitions` — audit and resumable windows.
- `users` / `auth_sessions` — Argon2id accounts and hashed session tokens.
- `raw_exports` — export receipts (range, rows, SHA-256) that gate deletion.

## 6. Operating runbooks

All commands run from `backend/` with `$env:PYTHONPATH='.'` on PowerShell.

| Task | Command / UI |
| --- | --- |
| Ingest a window | Admin → Ingestion control (≤ 5 days) or `POST /api/v1/admin/ingestion/run` |
| Ingest all sources | Admin → Ingestion control → Run all sources |
| Check availability | Admin → Ingestion control → Check availability |
| Historical backfill | Admin → Historical backfill (datasets, region, dates) |
| Harmonize | Admin → Analysis maintenance → Run harmonization |
| Rebuild rollups | Admin → Analysis maintenance → Rebuild rollups |
| Clear caches | Admin → Analysis maintenance → Clear caches |
| Delete one run | Admin → Ingested data → Delete data (preview first) |
| Raw retention | `python -m scripts.retention --apply` (dry run without `--apply`) |
| Delete before a cutoff | `python -m scripts.cleanup_before --before YYYY-MM-DD --apply --vacuum` |
| Export raw range | Admin → Export a range (CSV.GZ + SHA-256 receipt) |
| FIRMS key | Admin → NASA FIRMS MAP_KEY |
| Users/roles | Admin → Operator accounts |
| Backup | `python -m scripts.backup_database --output-dir <dir>` |
| Restore drill | `python -m scripts.restore_database --file <dump> --target-url <scratch DB>` |
| Create admin | `python -m scripts.create_admin --email you@example.com` |
| Source registry | `python -m scripts.seed_sources` |
| Storage report | `python -m scripts.storage_report` |
| History status | `python -m scripts.backfill_status` |

### Deletion semantics

Deleting an ingestion run removes its canonical rows, raw payloads, matches,
event memberships (and now-empty events), availability for its window,
harmonization coverage and resumable partitions, then rebuilds the affected
rollups. The run row is kept with status `deleted` for audit. The window can be
ingested again.

### Backups

`backup_database.py` writes a custom-format dump plus a `.sha256` sidecar.
`restore_database.py` verifies the checksum and refuses to overwrite the live
database unless `--force` is given. A full restore drill has been verified
against this store. Schedule nightly backups and copy the pair off-host.

## 7. Verification

```powershell
cd backend
uv run pytest -q                 # 241 tests
uv run ruff check .
uv run mypy app

cd frontend
npm run typecheck
npm test                         # 76 tests
npm run build
```

Health: `GET /health`, `GET /ready`. Capabilities and module status:
`GET /api/v1/system/status`, `GET /api/v1/system/modules`.

CI runs the same checks on every push (`.github/workflows/ci.yml`) plus
`docker compose config --quiet`.

## 8. Known gaps and next steps

1. **Cloudflare R2** — code path implemented but not exercised live (no
   credentials here). First cloud task: set R2 env vars, run one sync, verify a
   dataset checksum in the bucket.
2. **TLS/domain** — terminate TLS at a proxy/load balancer; set `CORS_ORIGINS`;
   enable `RATE_LIMIT_PER_MINUTE=120`.
3. **August 2026 gap** — 2026-08-06 → 08-31 is unobserved. The calendar shows it
   as a gap; backfill it from Admin → Historical backfill if needed.
4. **Burned-area calibration** — not measured; requires an external MCD64A1/GFED
   table. Do not claim accuracy without it.
5. **Single-process assumptions** — response caches and long jobs run in the API
   process. For multiple API instances, move history jobs to the worker service
   or run one API instance.
6. **Auth scope** — reads are public by design; writes require a role. If the
   whole console must be private, add an auth gate for reads as well.

## 9. Incident notes (already fixed; don't reintroduce)

- A **60 s `statement_timeout`** applies to reads. Bulk ingestion raises it per
  window via `INGESTION_STATEMENT_TIMEOUT_MS`; without that, large VIIRS windows
  500 at insert.
- Partitions are keyed by `(source, tile, date_start)`. Resume also checks
  `date_end`; a one-day run must not mark a four-day window complete.
- `observation_matches.match_day` is NOT NULL. Every insert path (single range and
  daily-range) must set it; the single-range path once missed it and Re-run
  Associations returned 500.
- Two simultaneous harmonization runs used to collide on the unique match pair
  index. Passes are serialized; the loser gets **409**.
- Deleting observations with cascading FKs can re-scan unindexed
  `event_observations`. The run-deletion service and `delete_history.py` use
  temp tables and suspend FK triggers in one transaction.
- The harmonized map used to bypass the rollup and hit the 60 s cap. It now
  reads `cell_activity.harmonized` (world view ≈ 50 ms).
- Vite dev caching: after changing `src/`, a normal refresh is enough; if the
  page looks stale, restart `npm run dev`.

## 10. First-day checklist for the new owner

- [ ] Clone the repo and create `.env` from `.env.example`.
- [ ] `.\start.bat`; open `http://127.0.0.1:5273`.
- [ ] Sign in, rotate the admin password, create named analyst/viewer accounts.
- [ ] Run the backend and frontend test commands in §7.
- [ ] Open Admin → Ingestion control and check availability for one source.
- [ ] Read `docs/architecture.md`, `docs/methodology.md`, `docs/operations.md`,
      `docs/cloud_readiness.md`.
- [ ] Take a fresh backup and restore it into a scratch database (§6).
- [ ] Confirm whether R2 credentials and the production domain are available;
      if not, that is the first blocking item for cloud.
