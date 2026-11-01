# Cloud integration and datasets

FIREWATCH X runs in three modes from one codebase. Only configuration changes between them; no
provider SDK is called outside `app/storage`.

| Mode | Database | Datasets | Needs cloud credentials |
| --- | --- | --- | --- |
| `local` (default) | local PostgreSQL | `./data/firewatch-data` on disk | no |
| `hybrid` | local writes, cloud summaries optional | uploaded by choice | optional |
| `cloud` | production PostgreSQL (`CLOUD_DATABASE_URL`) | Cloudflare R2 | yes |

```env
DEPLOYMENT_MODE=local
STORAGE_MODE=local            # local | r2 | s3
DATABASE_MODE=local           # local | cloud | split
LOCAL_DATA_DIRECTORY=./data
DATABASE_URL=postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch
CLOUD_DATABASE_URL=

R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=
R2_ALLOCATION_BYTES=26843545600
```

With no R2 values the application starts normally, the readiness page reports `no cloud
credentials`, and every sync action is a local no-op. Missing credentials in `STORAGE_MODE=r2`
raise a clear error instead of silently falling back to disk.

## Storage interface

`app/storage/base.py` defines `StorageProvider`: `upload`, `download`, `delete`, `exists`,
`get_metadata`, `list`, `checksum`, `available_bytes`, `used_bytes`, `signed_url`, and
`verify(path, size=…, checksum=…)`.

- `LocalStorage` — atomic copy (`.part` then rename), SHA-256, path-traversal guard, disk capacity.
- `S3Storage` — Cloudflare R2 and any S3 endpoint; multipart uploads via boto3, checksum stored as
  `x-amz-meta-sha256`, presigned download URLs, bucket test.
- `get_storage(settings)` chooses the provider; `storage_report()` returns what the UI shows
  without raising when unconfigured.

## Dataset layout

```
data/firewatch-data/
  raw/                              downloaded source files (temporary tier)
  harmonized/year=YYYY/month=MM/    detections.parquet + detections.meta.json
  harmonized-synthetic/…            labelled fixture exports (never mixed)
  analytics/daily/                  daily_activity.parquet
  manifests/                        latest.json + timestamped manifests
  exports/                          ad-hoc extracts
  temporary/                        staging area
```

Parquet is written by Polars with **Zstandard** compression and an explicit schema (no inference
over millions of rows). One file per month, not per day: enough partitioning to prune, few enough
files to avoid the small-file problem. Each file carries a JSON sidecar with dataset id, sensor,
coverage, record count, size, SHA-256, schema version and processing version; scanning reads the
sidecars, so inventory is instant.

Columns: `id, sensor, satellite, acquired_at (UTC), latitude, longitude, confidence_raw,
confidence_category, brightness_temperature, frp_mw, scan_km, track_km, daynight, source_code,
source_product, processing_version, is_synthetic`.

## Synchronisation

`app/services/sync.py`, exposed through `/api/v1/infrastructure/*` and
`scripts/storage_sync.py`:

1. **Scan** local datasets (sidecars + re-hashed files).
2. **Preview** against the bucket: `missing`, `matched`, `changed`, `size_mismatch`, expected
   upload bytes, remote usage.
3. **Guard**: if `remote_used + planned > allocation`, the sync is `blocked` and **nothing** is
   uploaded or deleted.
4. **Upload** only what differs; each object is then re-checked by size and SHA-256. A failed
   verification is reported as `verification_failed`, never as success.
5. **Record** a manifest (`firewatch-data/manifests/latest.json`) with per-dataset status.

Re-running is idempotent: matched objects are skipped. Local files are never deleted.

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.storage_sync export --start 2026-09-02 --end 2026-10-31
.venv\Scripts\python.exe -m scripts.storage_sync preview
.venv\Scripts\python.exe -m scripts.storage_sync sync
```

### Cloudflare R2 setup

1. Cloudflare dashboard → R2 → **Create bucket** (e.g. `firewatch`).
2. **Manage R2 API tokens** → create a token with Object Read & Write for that bucket.
3. Set `STORAGE_MODE=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
   `R2_BUCKET_NAME` (the endpoint is derived from the account id).
4. `POST /api/v1/infrastructure/storage/test` (or the *Test storage* button) verifies the bucket.
5. `preview`, then `sync`. Objects land under `firewatch-data/…` exactly as on disk.

R2 exposes no quota through the S3 API, so capacity is compared against `R2_ALLOCATION_BYTES`
(25 GB by default) using the sum of listed object sizes.

## PostgreSQL: what stays, what moves

The live PostgreSQL keeps observations (for the map and queries), harmonisation records, ingestion
history, availability, watched assets and the rollup views. For the 1 GB cloud allocation, the
archive belongs in Parquet: `POST /infrastructure/export` writes detections and the daily rollup to
Parquet, and only summaries need to live in cloud PostgreSQL.

## DuckDB and measurements

`app/services/parquet_query.py` reads the exported Parquet with DuckDB (threads capped at 2, time
zone pinned to UTC so day buckets never depend on the workstation).

Measured on this workstation — 7 days, 2026-10-25 → 10-31, 1,120,880 detections:

| Metric | Value |
| --- | --- |
| Export duration | 29 s |
| Parquet size | 41.3 MB (Zstandard) |
| Same rows in PostgreSQL | ≈ 1.86 GB (1,660 B/row) |
| DuckDB `count(*)` | 0.007 s |
| DuckDB per-sensor totals | 0.012 s |
| Per-day counts vs PostgreSQL | identical, day by day (UTC) |

The full two-month store (11.34 M detections) exports to roughly 420 MB of Parquet against 18 GB
in PostgreSQL — about a 40× reduction, because row overhead, UUID storage and the raw payload
archive disappear.

## Known limitations

- No authentication on the API/web UI; bind to localhost or put an authenticating proxy in front.
- Rate limiting is in-process (`RATE_LIMIT_PER_MINUTE`), per API instance.
- R2 capacity is measured from object listings, not a provider quota.
- Deletes are never automatic: reclaiming space is an explicit operator action.
- `raw_observations` retains every source payload; that archive is ~40% of the database and can be
  dropped if provenance is not required.
