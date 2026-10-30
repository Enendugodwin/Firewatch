# Data dictionary

## Implemented (Phase 1 migration `0001_foundation`)

### `data_sources`

Registry of the satellite products the platform is allowed to retrieve. Seeded idempotently by
`backend/scripts/seed_sources.py` from `app/services/sources.py`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key (`GUID`; native `uuid` on PostgreSQL, `CHAR(32)` elsewhere) |
| `source_code` | `VARCHAR(32)` | Unique FIRMS product code, e.g. `VIIRS_NOAA20_SP` |
| `sensor` | `VARCHAR(16)` | `MODIS` or `VIIRS` |
| `satellite` | `VARCHAR(32)` | `Terra/Aqua`, `Suomi-NPP`, `NOAA-20`, `NOAA-21` |
| `processing_level` | `VARCHAR(16)` | `SP` (standard processing) or `NRT` (near-real-time) |
| `description` | `VARCHAR(255)` | Human-readable purpose |
| `active` | `BOOLEAN` | Whether retrieval is permitted |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | Server-maintained |

Indexes: unique `source_code`, B-tree on `processing_level`. `alembic_version` tracks revisions.

## Canonical observation schema (Phase 2, not yet created)

Every source record is transformed into one canonical shape while original values are retained.

| Canonical field | Meaning |
| --- | --- |
| `source_id` | Original source identifier / fingerprint |
| `sensor` | `MODIS` or `VIIRS` — never merged |
| `satellite` | Terra, Aqua, SNPP, NOAA-20, NOAA-21 |
| `latitude`, `longitude` | Decimal degrees, WGS84 |
| `location` | `GEOGRAPHY(Point, 4326)` (PostGIS) |
| `acquired_at` | UTC acquisition timestamp |
| `confidence_raw` | Original numeric confidence, unconverted |
| `confidence_category` | Original source category (`low`/`nominal`/`high`, `l`/`n`/`h`, etc.) |
| `brightness_temperature` | Source channel value; **not** cross-sensor comparable |
| `brightness_channel` | Which channel the value came from |
| `frp_mw` | Fire Radiative Power, megawatts |
| `scan_km`, `track_km` | Pixel dimensions |
| `daynight` | `D` / `N` where supported |
| `processing_version` | Product version (e.g. MODIS C61) |
| `source_product` | FIRMS source code |
| `source_payload` | Untouched original record (JSONB) |
| `quality_flags` | Validation and quality metadata |
| `ingested_at` | When FIREWATCH X stored it |

Rules:

- Original measurements are preserved even when no common field exists.
- `confidence_raw` and `confidence_category` keep their source semantics. Any application-level
  quality class is labelled a **harmonized interpretation**, not NASA's confidence.
- Uniqueness is enforced on the source record identity, with a documented fallback fingerprint when
  the provider supplies none.

## Planned tables

| Table | Purpose |
| --- | --- |
| `raw_observations` | Immutable retrieved payloads + retrieval metadata |
| `ingestion_runs` | Per-run status, counts, query parameters, errors |
| `observation_matches` | Cross-sensor associations: deltas, distances, score, status, algorithm version |
| `fire_events` | Estimated events: extent, observation count, sensor count, FRP aggregates, clustering parameters |
| `event_observations` | Many-to-many event ↔ observation with provenance |
| `geographic_regions` | Countries, admin areas, custom areas as PostGIS geometry |
| `daily_fire_statistics` | Per region / date / sensor: raw counts, match groups, events, FRP, completeness |
| `regional_baselines` | Baseline windows with mean, median, SD, MAD, quantiles, model version |
| `anomalies` | Observed vs expected, deviation score, method, evidence, investigation state |
| `infrastructure_assets`, `exposure_assessments` | Assets and geodesic distance results with dataset attribution |
| `users`, `saved_regions`, `alerts`, `reports`, `audit_logs`, `data_quality_checks` | Platform records |

Partitioning of `fire_observations` is deferred until measured volumes justify it; the
specification is explicit that partition strategy should follow data, not guesswork.

## Conventions

- **UTC everywhere.** Storage is `TIMESTAMPTZ`; the UI renders UTC and labels it.
- **No floats for identity.** Coordinates are doubles; identifiers are UUIDs or source strings.
- **Provenance is mandatory.** Every derived row keeps a pointer to its source observations and the
  algorithm/model version that produced it.
- **Constraint naming** follows the `NAMING_CONVENTION` in `backend/app/db/base.py` so Alembic
  diffs and downgrades stay deterministic.
