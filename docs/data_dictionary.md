# Data dictionary

## Implemented tables

### `data_sources`

Registry of satellite products the platform may retrieve (seeded from
`app/services/sources.py`).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key (`uuid` on PostgreSQL, `CHAR(32)` elsewhere) |
| `source_code` | `VARCHAR(32)` | Unique FIRMS product code, e.g. `VIIRS_NOAA20_SP` |
| `sensor` | `VARCHAR(16)` | `MODIS` or `VIIRS` |
| `satellite` | `VARCHAR(32)` | `Terra/Aqua`, `Suomi-NPP`, `NOAA-20`, `NOAA-21` |
| `processing_level` | `VARCHAR(16)` | `SP` (standard processing) or `NRT` |
| `active` | `BOOLEAN` | Retrieval permitted |

### `fire_observations` — canonical detection

One row per satellite thermal detection. Original measurements are never overwritten by derived
fields.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key |
| `source_id` | UUID FK | → `data_sources` |
| `source_code` | `VARCHAR(32)` | Product code, denormalised for fast filtering |
| `source_record_id` | `VARCHAR(64)` | Fingerprint (see below) |
| `run_id` | UUID FK NULL | → `ingestion_runs` that produced the row |
| `sensor`, `satellite` | `VARCHAR` | Sensor family and platform |
| `latitude`, `longitude` | `DOUBLE` | WGS84 decimal degrees |
| `acquired_at` | `TIMESTAMPTZ` | UTC acquisition instant |
| `confidence_raw` | `INTEGER` | MODIS 0–100; `NULL` for categorical VIIRS |
| `confidence_category` | `VARCHAR(16)` | Source category (`low`/`nominal`/`high`) |
| `brightness_temperature` | `DOUBLE` | Source channel value |
| `brightness_channel` | `VARCHAR(24)` | e.g. `modis_brightness_4um`, `viirs_bright_ti4_4um` |
| `frp_mw` | `DOUBLE` | Fire Radiative Power, MW |
| `scan_km`, `track_km` | `DOUBLE` | Pixel dimensions |
| `daynight` | `CHAR(1)` | `D` / `N` |
| `processing_version` | `VARCHAR(32)` | Product version, retained |
| `source_product` | `VARCHAR(32)` | FIRMS source code |
| `source_payload` | JSONB | Untouched original row |
| `quality_flags` | JSONB | Interpretation metadata (see below) |
| `ingested_at` | `TIMESTAMPTZ` | When FIREWATCH X stored it |
| `is_synthetic` | `BOOLEAN` | True only for labelled fixture rows |

Unique: `(source_id, source_record_id)`. Indexes: `acquired_at`, `(sensor, acquired_at)`,
`(latitude, longitude)`, `is_synthetic`.

**`quality_flags` keys**: `normalizer`, `bright_t31_kelvin` / `bright_ti5_kelvin`,
`confidence_interpretation` (MODIS bands are an application interpretation, not NASA's),
`confidence_source` (VIIRS categorical), `firms_type`, `firms_type_label`, `suspected_non_fire`
(true when FIRMS `type` ≠ 0 — volcano, static land, offshore), `instrument`.

**`source_record_id`**: FIRMS publishes no per-row identifier, so identity is a SHA-256 over
product, sensor, satellite, coordinates (5 dp), acquisition instant, brightness, FRP, scan/track
and confidence. Rounding deduplicates repeats of the same detection while distinct detections
differ in time, position or radiometry.

### `raw_observations`

Immutable retrieved payload with `content_hash`, `retrieved_at`, `run_id` and `is_synthetic`.
Unique on `(source_id, source_record_id)`, so re-ingestion never rewrites history.

### `ingestion_runs`

One row per retrieval job: `status` (`running`/`succeeded`/`partial`/`failed`), timestamps,
`records_received`/`inserted`/`rejected`, `error_message`, `query_parameters` (tile, bbox, dates,
synthetic) and `is_synthetic`.

### `ingestion_partitions`

Resumable unit of work: `(source_id, tile_key, date_start)` unique, plus `date_end`, `status`,
`records_received`, `attempts`, `error_message`. A succeeded partition is skipped on re-run.

### `source_availability`

One row per `(source_id, observation_date)`: `status` ∈ `available` (inside the provider coverage
window — an *observed* day, possibly with zero detections), `missing`, `empty`, `before_coverage`,
`not_yet_available`, `unknown`. This is what prevents a gap from reading as quiet conditions.

### `observation_matches`

Scored association between two observations from different sensor families.

| Column | Notes |
| --- | --- |
| `observation_a_id`, `observation_b_id` | FKs to `fire_observations` (unique pair) |
| `temporal_delta_seconds`, `spatial_distance_m` | Measured separation |
| `footprint_overlap` | 0–1 circular-footprint approximation, `NULL` when unknown |
| `association_score` | `S` in [0, 1] — an association score, not a probability of identity |
| `match_status` | `probable` / `possible` / `rejected` |
| `components` | JSONB: temporal/spatial/footprint values, weights, model note |
| `algorithm_version` | e.g. `assoc-v1` |

### `fire_events` and `event_observations`

Estimated events from spatiotemporal clustering: first/last detection, centroid, bounding box,
`observation_count`, `sensor_count`, `maximum_frp_mw` and `aggregate_frp_mw` (labelled separately),
clustering method/parameters and methodology version. `event_observations` is the many-to-many link
that preserves every member observation.

### `algorithm_runs`

Audit trail for harmonization and event grouping: `kind`, `status`, `parameters` (including the
analysis `scope`: bbox and dates), `stats`, `algorithm_version`, `is_synthetic`,
`error_message`.

### `geographic_regions`

Selectable analysis boundary: `slug`, `name`, `level` (country/state/province/custom/radius),
`boundary_kind` (`polygon` / `circle` / `bbox`), `geometry` (GeoJSON MultiPolygon — PostGIS is not
installed), `bbox_*`, `area_km2` (planar approximation), `vertices`, `boundary_version`, `source`,
`is_approximate`, `last_analyzed_at`, `last_analysis_algorithm`.

### `regional_daily_statistics`

One region × date × sensor (`MODIS`, `VIIRS`, `ALL`): `detection_count`, `frp_sum_mw`,
`frp_max_mw`, `high_confidence_count`, `coverage` (sources observed/missing), `algorithm_version`,
`computed_at`. Unique on `(region_id, activity_date, sensor)`.

### `regional_cell_statistics`

Region × 0.5° cell: `detection_count`, `frp_sum_mw`, `frp_max_mw`, `years_with_detections`,
`first_year`, `last_year`, `algorithm_version`. A plain screening grid, not H3.

## Planned tables

| Table | Purpose |
| --- | --- |
| `daily_fire_statistics` | Per region/date/sensor aggregates with completeness (superseded by `regional_daily_statistics`) |
| `regional_baselines` | Mean, median, SD, MAD, quantiles, model version |
| `anomalies` | Observed vs expected, deviation score, evidence, method |
| `infrastructure_assets`, `exposure_assessments` | Assets and geodesic distance results |
| `users`, `saved_regions`, `alerts`, `reports`, `audit_logs` | Platform records |

## Conventions

- **UTC everywhere.** `TIMESTAMPTZ` storage, UTC rendering, explicit labels.
- **Provenance is mandatory.** Derived rows keep their source observations and algorithm version.
- **Missing ≠ zero.** Availability is stored per date; aggregates never silently fill gaps.
- Constraint naming follows `NAMING_CONVENTION` in `backend/app/db/base.py` so migrations diff and
  downgrade deterministically.
