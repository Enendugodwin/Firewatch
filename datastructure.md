# Data structure

How every downloaded NASA FIRMS detection is stored in FIREWATCH X: the store, the tables, the
fields, the derived rollups, and the rules that keep counts honest.

- **Engine**: PostgreSQL 16, database `firewatch`, schema `public`
- **Data directory**: `C:\Users\user\pgsql\data` (18.9 GB at the time of writing)
- **Connection**: `postgresql+psycopg://firewatch@127.0.0.1:5433/firewatch`
- **Older SQLite snapshot**: `backend/firewatch.db` (642 MB, frozen before the Postgres move)

Nothing is stored as CSV. Each downloaded row becomes one JSON payload in `raw_observations`
(provenance) and one normalised record in `fire_observations` (analysis).

## At a glance

| Object | Kind | Rows | Size |
| --- | --- | ---: | ---: |
| `fire_observations` | table | 11,343,058 | 11 GB |
| `raw_observations` | table | 11,343,058 | 7.1 GB |
| `cell_activity` | materialized view | 116,493 | 12 MB |
| `event_observations` | table | 16,950 | 2.1 MB |
| `observation_matches` | table | 4,648 | 2.8 MB |
| `fire_events` | table | 3,382 | 1.4 MB |
| `daily_activity` | materialized view | 1,646 | 304 kB |
| `source_availability` | table | 455 | 40 kB |
| `ingestion_runs` | table | 294 | 176 kB |
| `ingestion_partitions` | table | 113 | 48 kB |
| `algorithm_runs` | table | 12 | 88 kB |
| `watched_assets` | table | 1 | 8 kB |
| `data_sources` | table | 8 | 56 kB |

## Entity relationships

```
                         data_sources (1)
                          │ id, source_code, sensor, satellite, processing_level
        ┌─────────────────┼──────────────────┬───────────────────────┐
        │                 │                  │                       │
 ingestion_runs (N)  ingestion_partitions  source_availability   raw_observations
   one per request     (source, tile,       (source, day,         1:1 with the canonical
   + counters          date window)          available|empty|      observation, raw payload
        │                                   missing|not_yet)            │
        │                                    │                         │
        └──────────► fire_observations (1) ◄─┘                         │
                       │  the canonical row  ◄──────────────────────────┘
                       │  (source_id + source_record_id is unique)
        ┌──────────────┼────────────────────────────────┐
        │              │                                │
 observation_matches   event_observations          (rollups, derived)
   a_id/b_id ──► fire_observations       │          daily_activity
        │                                │          cell_activity
        └──► fire_events (1) ◄───────────┘
                  │
              algorithm_runs (run_id)  — scope + parameters + stats for any automated pass
```

`watched_assets` (exposure screening) is independent: it holds user-registered places and is
joined to observations only at query time by distance.

## Core table: `fire_observations`

One row per satellite thermal detection. This is the analysis table.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | uuid | no | Primary key |
| `source_id` | uuid → `data_sources.id` | no | Product the row came from |
| `source_code` | varchar(32) | no | Denormalised product code, e.g. `VIIRS_SNPP_NRT` |
| `source_record_id` | varchar(64) | no | Fingerprint of the source row (see below) |
| `run_id` | uuid → `ingestion_runs.id` | yes | Ingestion run that first stored it |
| `sensor` | varchar(16) | no | `MODIS` or `VIIRS` |
| `satellite` | varchar(32) | no | Mission name; FIRMS codes (`N`, `N20`, `N21`, `1`, `2`) are stored as-is and expanded at the API boundary |
| `latitude` | double | no | WGS84 decimal degrees |
| `longitude` | double | no | WGS84 decimal degrees |
| `acquired_at` | timestamptz | no | Acquisition time, UTC |
| `confidence_raw` | integer | yes | MODIS 0–100 confidence; null for VIIRS |
| `confidence_category` | varchar(16) | yes | `low` / `nominal` / `high` |
| `brightness_temperature` | double | yes | MODIS `brightness` (4 µm) or VIIRS `bright_ti4`, kelvin |
| `brightness_channel` | varchar(24) | yes | `modis_brightness_4um` or `viirs_bright_ti4_4um` — channels are never conflated |
| `frp_mw` | double | yes | Fire radiative power, MW |
| `scan_km` | double | yes | Pixel scan size, km |
| `track_km` | double | yes | Pixel track size, km |
| `daynight` | varchar(1) | yes | `D` or `N` |
| `processing_version` | varchar(32) | yes | FIRMS `version`, e.g. `6.1NRT`, `2.0NRT` |
| `source_product` | varchar(32) | no | Product code (same family as `source_code`) |
| `source_payload` | jsonb | no | The FIRMS row as received (column → string) |
| `quality_flags` | jsonb | no | Normaliser version, instrument, derived flags |
| `ingested_at` | timestamptz | no | When this row was written |
| `is_synthetic` | boolean | no | `true` only for labelled fixtures; never mixed with real data in the UI |

### `source_record_id`

A 32-character SHA-256 prefix of the canonical source fields (coordinates, time, satellite,
FRP, scan/track, confidence). Re-ingesting the same window reproduces the same id, so
`unique (source_id, source_record_id)` makes ingestion idempotent without losing provenance.

### `quality_flags` example

```json
{
  "instrument": "MODIS",
  "normalizer": "normalize-v1",
  "bright_t31_kelvin": 294.39,
  "confidence_interpretation": "application bands applied to NASA MODIS 0-100 confidence",
  "firms_type": "0",
  "firms_type_label": "vegetation_fire",
  "suspected_non_fire": false
}
```

`firms_type` non-zero marks a thermal anomaly FIRMS attributes to a volcano, static land or an
offshore source; it is flagged, never dropped.

### `source_payload` example (MODIS NRT)

```json
{
  "latitude": "-5.36661", "longitude": "-48.96713",
  "brightness": "306.13", "scan": "3.51", "track": "1.76",
  "acq_date": "2026-09-16", "acq_time": "2324",
  "satellite": "Terra", "instrument": "MODIS",
  "confidence": "62", "version": "6.1NRT",
  "bright_t31": "294.39", "frp": "29.53", "daynight": "N", "type": "0"
}
```

## Provenance tables

### `raw_observations`

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | uuid | Primary key |
| `run_id` | uuid → `ingestion_runs.id` | Run that retrieved it |
| `source_id` | uuid → `data_sources.id` | Product |
| `source_record_id` | varchar(64) | Same fingerprint as the canonical row |
| `content_hash` | varchar(64) | Hash of the payload, for change detection |
| `payload` | jsonb | The original FIRMS row |
| `retrieved_at` | timestamptz | Retrieval time |
| `is_synthetic` | boolean | Fixture marker |

`unique (source_id, source_record_id)`. Delete this table to halve storage; the analysis table
keeps working.

### `ingestion_runs`

One row per request: `status` (`running`/`succeeded`/`failed`), `started_at`, `completed_at`,
`records_received`, `records_inserted`, `records_rejected`, `error_message`,
`query_parameters` (jsonb: tile, bbox, dates, source, synthetic), `is_synthetic`.

### `ingestion_partitions`

Resumable unit of work: `(source_id, tile_key, date_start)` unique, `date_end`, `status`
(`pending`/`succeeded`/`failed`), `records_received`, `attempts`, `completed_at`. A 60-day
backfill is 12 five-day windows per source; completed partitions are skipped on re-run.

### `source_availability`

Which dates a product actually observed — the reason a missing day is never shown as zero.

`unique (source_id, observation_date)`; `status ∈ {available, empty, missing, not_yet_available}`.

### `data_sources`

The registry: `source_code`, `sensor`, `satellite`, `processing_level` (`SP`/`NRT`),
`description`, `active`.

## Harmonisation tables

| Table | Grain | Key columns |
| --- | --- | --- |
| `observation_matches` | one scored cross-sensor pair | `observation_a_id`, `observation_b_id`, `association_score` 0–1, `match_status` (`probable`/`possible`/`rejected`), `temporal_delta_seconds`, `spatial_distance_m`, `footprint_overlap`, `components` (jsonb), `algorithm_version` |
| `fire_events` | one estimated event (cluster of detections) | `first_detected_at`, `last_detected_at`, centroid, bounding box, `observation_count`, `sensor_count`, `maximum_frp_mw`, `aggregate_frp_mw`, `clustering_method`, `clustering_parameters`, `run_id` |
| `event_observations` | join table | `event_id`, `observation_id` |
| `algorithm_runs` | one automated pass | `kind`, `status`, `parameters`, `stats`, `algorithm_version`, `is_synthetic` |

Matches compare different sensor families only; an association score is not a probability that
two detections are the same fire.

## Exposure table

`watched_assets`: `name`, `category`, `latitude`, `longitude`, `created_at`. Screening measures
distance from each asset to detections — no population or infrastructure data is bundled.

## Derived objects (materialized views)

| View | Grain | Used by |
| --- | --- | --- |
| `daily_activity` | UTC day × sensor × confidence × day/night × satellite × product × synthetic | calendar, analytics series, anomaly engine, reports |
| `cell_activity` | UTC day × 2° cell × synthetic | analytics ranking |

Both are refreshed `CONCURRENTLY` after ingestion. They are **bypassed** when a request carries a
`bbox` or a per-detection `min_frp`, because those cannot be answered from the rollup.

## Indexes

| Index | Columns | Why |
| --- | --- | --- |
| `pk_fire_observations` | `id` | Identity |
| `uq_fire_observations_source_record` | `(source_id, source_record_id)` | Idempotent ingestion |
| `ix_fire_observations_acquired_at` | `acquired_at` | Date-range scans |
| `ix_fire_observations_sensor_acquired` | `(sensor, acquired_at)` | Sensor-filtered ranges |
| `ix_fire_observations_position` | `(latitude, longitude)` | Bounding-box filters |
| `ix_fire_observations_synthetic` | `is_synthetic` | Keeping fixtures out |
| `ix_fire_observations_daily_cover` | `(utc_day, sensor, confidence, daynight, satellite, source_code) INCLUDE (frp_mw)` | Index-only daily aggregation |
| `uq_daily_activity_key` / `ux_cell_activity_key` | rollup keys | `REFRESH … CONCURRENTLY` |

## Counting rules

1. **Detections, not fires.** Every count on the platform is a number of thermal detections.
2. **MODIS and VIIRS are never summed as if interchangeable** — totals are reported separately
   and then combined only as "detections".
3. **Missing ≠ zero.** A day with no rows is `quiet` only if `source_availability` shows a source
   observed it; otherwise it is `unobserved`.
4. **Fixtures are labelled.** `is_synthetic = true` rows are excluded from every default query
   and marked in the UI when included.

## Typical queries

```sql
-- per product and day
SELECT source_code, CAST((acquired_at AT TIME ZONE 'UTC') AS date) AS day, count(*)
FROM fire_observations
WHERE acquired_at >= '2026-09-02' AND acquired_at < '2026-11-01'
GROUP BY 1, 2 ORDER BY 1, 2;

-- one detection with provenance
SELECT id, sensor, satellite, acquired_at, latitude, longitude, frp_mw,
       confidence_category, quality_flags, source_payload
FROM fire_observations WHERE id = '<uuid>';

-- availability for a product
SELECT observation_date, status FROM source_availability
WHERE source_id = (SELECT id FROM data_sources WHERE source_code = 'VIIRS_SNPP_NRT')
ORDER BY observation_date DESC LIMIT 10;
```

## Storage footprint

At 11.34 M detections: `fire_observations` 11 GB, `raw_observations` 7.1 GB, rollups ~12 MB,
the rest < 10 MB — 18 GB total. Roughly 1,660 bytes per detection, indexes included; the raw
payload archive is about 40% of that and can be dropped if provenance is not required.
