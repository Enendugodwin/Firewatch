# Cloud readiness

**Status: ready to deploy.** The application, schema, build, tests, write guard
and backup/restore path are in place. Two operator-supplied items remain before
the first public deployment: Cloudflare R2 credentials and the production
domain/TLS configuration.

Verified on 2026-11-04 against the live PostgreSQL store (13.3 M canonical
detections).

## Gates

| Gate | State | Evidence |
| --- | --- | --- |
| Authentication & RBAC | **Done** | Argon2id accounts, admin/analyst/viewer roles, server-side sessions (`app/services/auth.py`, `tests/test_auth.py`). Admin Portal has an operator sign-in page. |
| Administrative writes protected | **Done** | Session role **or** `ADMIN_TOKEN` (`app/core/security.py`); production with neither returns `503`. Tests in `tests/test_admin_auth.py`. |
| Secrets stay server-side | **Done** | FIRMS key stored in `app_settings`, returned masked only. `ADMIN_TOKEN` never sent to the browser by the API; archive downloads send it as a header. |
| Raw payloads excluded from cloud export | **Done** | Parquet exports use `EXPORT_COLUMNS` (no `source_payload`); `tests/test_cloud_infra.py` pins it. Retention keeps raw local. |
| Database migrations | **Done** | `backend/docker/entrypoint.sh` runs `alembic upgrade head` before serving, with retries. |
| Container build | **Done** | `backend/docker/Dockerfile` (Python 3.12, uv lockfile), `frontend/Dockerfile`, `docker-compose.yml`. |
| CI | **Done** | `.github/workflows/ci.yml`: ruff, mypy, pytest; frontend typecheck, vitest, build. |
| Backup | **Done** | `scripts/backup_database.py` (custom-format dump + SHA-256 sidecar). |
| Restore drill | **Passed** | 2.77 GB dump restored into a scratch database; row counts matched exactly (observations, raw, matches, cells, daily rollup, events). |
| Health checks | **Done** | `/health`, `/ready` (database aware); compose health checks for db, redis, api, web. |
| Rate limiting | **Done** | Per-client token bucket with `Retry-After`/`X-RateLimit-*`; enable with `RATE_LIMIT_PER_MINUTE=120`. |
| Reports & exports | **Done** | PDF, CSV, GeoJSON, JSON, Markdown; methodology and limitations in every format. |
| AI assistant | **Done** | Deterministic tool-style answers over stored data; no invented measurements. |
| HTTPS / domain | **Operator** | Terminate TLS at the load balancer or reverse proxy; set `CORS_ORIGINS` to the exact origin. |
| Cloudflare R2 | **Operator** | Code path implemented (`app/storage/s3.py`); credentials absent on this workstation, so a live upload has not been exercised. |

## Before the first public deploy

1. **Set secrets.** In the cloud environment (not in git):
   ```env
   ENVIRONMENT=production
   ADMIN_TOKEN=<long random value>   # or create an admin account below
   DATABASE_URL=postgresql+psycopg://...
   CORS_ORIGINS=https://console.example.com
   FIRMS_MAP_KEY=<key>
   ```
   `ENVIRONMENT=production` with an empty `ADMIN_TOKEN` disables every
   administrative write, by design.

2. **Create an administrator.** Either keep `ADMIN_TOKEN` as the break-glass credential or, preferably, bootstrap an account:
   ```bash
   python -m scripts.create_admin --email admin@example.com
   ```
   Then add analyst/viewer accounts from `POST /api/v1/auth/users`.

3. **Configure R2.** `STORAGE_MODE=r2`, `R2_ACCOUNT_ID`,
   `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`,
   `R2_ENDPOINT_URL`. Then run one sync from the Cloud Readiness page (or
   `POST /api/v1/infrastructure/sync`) and verify the manifest checksum in the
   bucket. Only Parquet analysis datasets are uploaded.

4. **TLS and origin.** Point the console at the API (same origin through the
   reverse proxy is simplest), set `CORS_ORIGINS`, and enable
   `RATE_LIMIT_PER_MINUTE` (e.g. 120).

5. **Schedule backups.** Run `python -m scripts.backup_database` nightly, copy
   the `.dump` and `.sha256` pair off the host, and restore into a scratch
   database weekly with `scripts/restore_database.py`.

6. **Migrate.** `docker compose up --build` runs migrations automatically. For a
   managed database, run `alembic upgrade head` as a release step.

## What is deliberately local-only

- **Raw payloads.** Recreatable from FIRMS; pruned on a 90-day policy after a
  checksummed export.
- **Process-local caches.** The API is designed for one worker; running several
  workers is safe for correctness but each keeps its own short-lived cache.
- **Ingestion jobs.** Long history runs execute in the API process (thread pool).
  For a multi-instance deployment, run a single API instance or move jobs to the
  worker service.

## Known scientific limits (unchanged by hosting)

- Detections are thermal anomalies, not confirmed fires.
- Burned-area agreement is not measured (needs an external MCD64A1/GFED table).
- 2026-08-06 → 08-31 is not ingested; the calendar shows it as unobserved, not
  as zero.
