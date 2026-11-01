# Delivery report — cloud preparation and performance

Summary of the work delivered on top of the existing FIREWATCH X codebase. Measurements are from
this workstation (Windows, 32 GB RAM, portable PostgreSQL 16 + DuckDB + Polars), not projections.

## 1. Assessment of the existing system

What was already sound and was kept: scope-enforced ingestion, per-sensor normalisation with raw
provenance, harmonisation with an inspectable score, availability tracking (missing ≠ zero), the
map, calendar, analytics and anomaly engine, and the module registry that refuses to claim ready
before a phase lands.

What the audit found:

| Problem | Evidence |
| --- | --- |
| Every analytics call re-scanned the table | 11.3 M rows, `count/group by` = 15–26 s per request |
| Calendar/anomaly/report each recomputed the same daily aggregation | 6–8 scans per view |
| Empty days and gaps were correctly modelled, but the rollup granularity was absent | no precomputed statistics |
| No storage abstraction | datasets only existed inside PostgreSQL |
| No dataset export or deployment path | nothing could leave the workstation |
| Bulk ingestion could stall the UI | SQLite lock contention, since removed by PostgreSQL + WAL |

## 2. Architecture now

```
React (Vite)  ──HTTP──►  FastAPI (app/api/v1)
                              │
              ┌───────────────┼─────────────────┐
              ▼               ▼                 ▼
      PostgreSQL 16     app/storage/       app/services/
      observations,     LocalStorage       ingestion, harmonisation,
      harmonisation,    S3Storage (R2)     calendar, analytics, anomalies,
      rollups, jobs                        reports, datasets, sync
                              │
                              ▼
                     Parquet (Polars/zstd) ──► DuckDB (offline analytics)
```

Deployment modes are configuration only: `DEPLOYMENT_MODE`, `STORAGE_MODE`, `DATABASE_MODE`.

## 3. Repository additions

```
backend/app/storage/{base,local,s3,__init__}.py   storage interface + adapters
backend/app/services/datasets.py                  Parquet export, inventory, manifests
backend/app/services/sync.py                      preview, verified upload, resume, report
backend/app/services/parquet_query.py             DuckDB reads (UTC-pinned)
backend/app/api/v1/infrastructure.py              status, export, datasets, sync, verify
backend/scripts/storage_sync.py                   CLI: export / scan / preview / sync
backend/scripts/backfill.py, backfill_status.py   resumable 60-day ingest + progress bar
backend/migrations/versions/0005..0007_*.py       covering index + two rollups
frontend/src/pages/CloudReadinessPage.tsx         readiness dashboard
frontend/src/lib/infrastructureApi.ts             typed client
docs/cloud.md, docs/operations.md, datastructure.md
```

## 4. Storage abstraction

`StorageProvider` exposes upload, download, delete, exists, metadata, list, checksum, capacity,
used bytes, signed URLs and `verify(size, checksum)`. Two adapters: filesystem (atomic rename,
traversal guard, disk capacity) and S3-compatible (R2, MinIO, AWS; multipart uploads, checksum in
object metadata, presigned URLs, bucket test). Application code never imports boto3 outside
`app/storage/s3.py`.

## 5. Cloudflare R2 preparation

Credentials come from `R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET_NAME`;
the endpoint is derived from the account id unless `R2_ENDPOINT_URL` is set. `STORAGE_MODE=r2`
without credentials fails loudly; `local` never needs them. `POST /infrastructure/storage/test`
checks the bucket, and the readiness page runs it behind a button. Capacity is compared against
`R2_ALLOCATION_BYTES` (25 GB default) using the sum of listed objects.

## 6. Dataset export and synchronisation

Detections export to Parquet (Zstandard, explicit schema, one file per month, JSON sidecar with
coverage/rows/checksum/versions). Synchronisation is preview → guard → upload → **verify size and
SHA-256** → manifest. It is idempotent (matching objects are skipped), resumable (a failed object is
retried on the next run), never deletes local files, and is blocked rather than exceeding the
allocation.

## 7. Performance work and measurements

| Change | Effect |
| --- | --- |
| `daily_activity` rollup (1,646 rows) | calendar 9.8 s → **0.05 s**; anomalies 13.3 s → **0.05 s** |
| `cell_activity` rollup (116k rows) | analytics 26 s → **0.24 s**; report 34 s → **0.17 s** |
| Analytics collapsed from six scans to one | fewer queries, same numbers |
| Reports reuse the analytics series for anomalies | one scan instead of two |
| Covering index on UTC day + dimensions | index-only aggregation, migration 0005 |
| Parquet + DuckDB | 1.12 M rows → 41.3 MB; `count(*)` 0.007 s, sensor totals 0.012 s |
| Export throughput | 1,120,880 rows → 41.3 MB in **29 s** |
| Parquet vs PostgreSQL for the same rows | 41 MB vs ≈ 1.86 GB (1,660 B/row) — ~40× smaller |

Parquet counts match PostgreSQL **day by day** (UTC) — verified after pinning DuckDB's time zone.

## 8. Ingestion and analysis changes

- Bulk ingestion runs one request per product with a **determinate progress bar**, per-source
  results, and a single harmonisation pass at the end.
- A 60-day backfill is 12 five-day partitions per source, resumable and idempotent; failures are
  counted and retried (`scripts/backfill.py`, `scripts/backfill_status.py`).
- The anomaly engine uses a preceding-history baseline when available and labels the short-history
  fallback when not; a zero MAD falls back to standard deviation; negative deviations are reported
  as `below_baseline`, never as fire anomalies.
- Calendar and analytics read the rollups; `bbox`/`min_frp` requests deliberately fall back to the
  live scan so filtered answers stay exact.

## 9. Tests

- Backend: **169 passed** (storage round-trip, traversal guard, sync idempotence, allocation block,
  checksum change detection, Parquet export + DuckDB read, infrastructure API, calendar months,
  anomaly baselines, bulk ingestion, CSV exports, reports/regions/exposure/assistant).
- Frontend: **54 passed** across 9 files; `tsc --noEmit` clean; production build OK.
- Ruff and mypy (79 files) clean.

## 10. Resource notes

- Ingestion peaks around 350 MB RAM per worker while normalising a 300 k-row window; the API stays
  responsive because the heavy work happens in the ingestion process.
- Export streams one month at a time; peak memory during the 1.12 M-row export was ≈ 600 MB.
- PostgreSQL is 18 GB for 11.34 M detections; Parquet equivalents are roughly 420 MB for the same
  data.

## 11. Known limitations

- No API authentication; keep the service on localhost or behind an authenticating proxy.
- Rate limiting is per process (`RATE_LIMIT_PER_MINUTE`), not distributed.
- R2 capacity is measured from listings; the provider exposes no quota.
- Nothing is deleted automatically, including the raw payload archive (~40% of the database).
- The final two-month archive export to Parquet has not been run in full (7-day slice verified);
  the same command scales to the full range.
- Cloud PostgreSQL is configured but not exercised against a hosted instance in this environment.

## 12. How to run

Local: `start.bat` (PostgreSQL + API + web), `stop.bat`. Full instructions in
[docs/operations.md](operations.md); storage, sync and R2 setup in [docs/cloud.md](cloud.md).
