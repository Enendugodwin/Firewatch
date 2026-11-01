# Operations

Everything the platform needs on one workstation: database, storage growth, backups and the
GitHub hand-off.

## Database

The API runs on **PostgreSQL 16**; SQLite remains the zero-setup option for tests and CI
(`DATABASE_URL` unset). Both dialects are exercised: migrations are dialect-aware and the
analytical queries isolate their two real differences (integer casting and UTC day bucketing)
in `app/db/dialect.py`.

### Local PostgreSQL (Windows, no admin rights)

The EDB "binaries" zip runs without installation or a service:

```powershell
# once: unpack the EDB binaries zip
#   https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip
#   -> C:\Users\<you>\pgsql\pgsql

powershell -ExecutionPolicy Bypass -File backend\scripts\start_postgres.ps1
# stop with backend\scripts\stop_postgres.ps1
```

The script initialises `~\pgsql\data` on port **5433** with a `trust` rule bound to
`127.0.0.1` and creates the `firewatch` role. Then:

```powershell
createdb -h 127.0.0.1 -p 5433 -U firewatch firewatch
cd backend
$env:DATABASE_URL = "postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m scripts.copy_to_postgres `
    --source "sqlite+pysqlite:///./firewatch.db" `
    --target $env:DATABASE_URL
```

Set the same `DATABASE_URL` in `.env` and restart the API. `system/status` then reports
`database.dialect = postgresql`.

Notes:

- PostGIS is optional. The foundation migration creates the extension only when the server
  offers it, and the capability report keeps saying "not built" otherwise.
- The local cluster is a normal user process: it does not survive a reboot. Run the start
  script (or register it as a scheduled task) before starting the API.
- SQLite connections now use WAL and a 30 s busy timeout, which removes the "database is
  locked" failures seen when the UI polled during a bulk ingestion. On PostgreSQL the
  problem does not exist.

## Backfilling more than five days

The API caps one request at five days, so a long backfill is a resumable loop of
five-day partitions:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.backfill --start 2026-09-02 --end 2026-10-31
# live progress bar, derived from completed partitions
.venv\Scripts\python.exe -m scripts.backfill_status --start 2026-09-02 `
    --end 2026-10-31 --watch
```

`backfill` prints one line per (source, window) with rows inserted and an ETA, and
skips partitions that already succeeded. `backfill_status` shows the same view as
a progress bar and is safe to run while the backfill is working.

## Storage growth

Measured on this workstation: **371,276 detections** occupy **588 MB** in PostgreSQL
(1,660 bytes per detection, indexes and raw payloads included) and 642 MB in SQLite.

At a full near-real-time day (MODIS + VIIRS Suomi-NPP + NOAA-20 + NOAA-21, ≈142,000
detections/day):

| Horizon | Detections | PostgreSQL |
| --- | --- | --- |
| 1 day | ~142,000 | ~0.24 GB |
| 7 days | ~1.0 M | ~1.7 GB |
| 30 days | ~4.3 M | **~7.1 GB** |
| 90 days | ~12.8 M | ~21 GB |

At the observed 5-day average (≈74,000 detections/day, three products) 30 days is ≈3.7 GB.
Add roughly 1 GB of transient WAL during a large ingestion (PostgreSQL checkpoints release
it). Most of the footprint is provenance: `fire_observations` 341 MB and `raw_observations`
232 MB for the same rows. Dropping the raw payload archive would cut about 40%.

## Backups

```powershell
# logical backup (schema + data)
& "$env:USERPROFILE\pgsql\pgsql\bin\pg_dump.exe" -h 127.0.0.1 -p 5433 -U firewatch `
    -Fc firewatch > firewatch-$(Get-Date -Format yyyyMMdd).dump

# restore
& "$env:USERPROFILE\pgsql\pgsql\bin\pg_restore.exe" -h 127.0.0.1 -p 5433 -U firewatch `
    -d firewatch --clean --if-exists firewatch-20261101.dump
```

## Deployment

`docker-compose.yml` runs PostgreSQL (PostGIS image), Redis, the API, a Celery worker and the web
build. The API has an HTTP healthcheck against `/ready` (database reachability) and the web service
probes itself; both are gated behind `service_healthy` dependencies.

Without Docker, run the API and the Vite/dev server directly (see the quick start) and point
`DATABASE_URL` at PostgreSQL as described above. `/health` is liveness, `/ready` is readiness, and
`/api/v1/system/status` reports phase, dialect and data freshness.

## Security posture

- Structured security headers on every response; API responses are `no-store`.
- Optional per-client rate limiting (`RATE_LIMIT_PER_MINUTE`, off by default) returning `429` with
  `Retry-After` and `X-RateLimit-*` headers.
- `CORS_ORIGINS` is an explicit allow-list; the browser never holds the FIRMS key.
- The web GUI has no authentication of its own: bind it to localhost or put it behind an
  authenticating proxy before exposing it.

## Pushing to GitHub

The repository has no remote yet. Create the GitHub repo (empty, no README), then:

```powershell
cd C:\Users\user\NASA
git remote add origin git@github.com:<account>/<repo>.git
git branch -M main
git push -u origin main
```

The SSH key `~/.ssh/id_ed25519_github` authenticates as **Enendugodwin**. A deploy key is
scoped to a single repository, so either add that public key as a deploy key with write
access on the new repo, or use an account key.

Before the first push, confirm nothing sensitive is staged:

```powershell
git status --short
git ls-files | Select-String -Pattern '\.env$|\.db$|\.dump$'
```

`.gitignore` already excludes `.env*` (except `.env.example`), databases, logs, artifacts,
`node_modules/` and `frontend/dist/`.
