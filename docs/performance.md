# Performance, storage and device safety

Measured on the live store: 12,772,331 observations, PostgreSQL 16 on port 5433,
one API worker. Numbers are wall-clock on this machine, not estimates.

## 1. Map path

The map used to pay a full observation scan for every viewport. Two changes fixed
that:

* the 2° cell rollup is now consulted for map aggregation when the requested cell
  is ≥ 2° and the filters are dimensions the rollup stores (date, sensor, bbox,
  synthetic);
* responses are cached in-process for 20 s (aggregate) / 15 s (GeoJSON) and
  gzip-compressed.

| Request | Before | After |
| --- | --- | --- |
| World aggregate, z2 | ~2 s (full scan) | **163 ms** |
| World aggregate, z5 | ~6 s | **631 ms** |
| Country aggregate, z6 (12° box) | ~12 s | **342 ms** |
| Country aggregate, z7 | ~12 s | **246 ms** |
| GeoJSON 3,000 points, 12° box | 2.5 s / 1.06 MB | 2.5 s first, **cached after**; 1.0 MB, gzip ≈ 250 KB |

The response now states `source: "rollup" | "live"` and the cell size actually
used, so a coarse rollup answer is never disguised as a fine one.

## 2. Rollups are incremental

`daily_activity` and `cell_activity` are ordinary tables (migration `0009`), not
materialized views. `refresh_rollup(since=...)` deletes and recomputes only the
ingested days. The one-time conversion of 11.5 M rows took **35 s**; subsequent
ingestions recompute a five-day window in well under a second.

The cell rollup now carries `sensor`, which is what lets the map honour a MODIS/
VIIRS selection without falling back to a scan.

## 3. API guards

* **GZip** middleware (minimum 1 KB, level 5).
* **Statement timeout 60 s** on every PostgreSQL connection. Every measured read
  is ≤ 0.25 s; the timeout exists so a runaway query fails instead of pinning a
  worker and the device.
* **Short TTL cache** for map responses, with hit/miss/eviction counters exposed
  at `GET /api/v1/admin/performance`.
* `GET /api/v1/admin/performance` reports database size, the 12 largest tables,
  rollup freshness, last ingestion throughput, API RSS/CPU and cache stats, and
  raises warnings (rollup lag, RSS > 900 MB, database > 20 GB).

## 4. Device stability

The machine rebooted twice with bugcheck **`0x0000010E`
(VIDEO_MEMORY_MANAGEMENT_INTERNAL)** and a `dwm.exe` crash before the second
reboot. That is a GPU-driver bugcheck, not an application exception; the map is
the only WebGL workload and it is the likely trigger. Mitigations applied:

* the map caps `pixelRatio` at 1.25 instead of the desktop value (a 4K surface
  multiplied the heatmap cost);
* point requests are capped at 2,000 features (was 5,000);
* the viewport debounce is 260 ms and identical responses are cached, so panning
  no longer issues a fresh 1 MB request per movement;
* rollups and caching remove the repeated 12 s full scans that spiked CPU, disk
  and heat.

These reduce load; they do not replace a GPU driver update. If `0x10E` recurs,
update the display driver and, until then, prefer the aggregated map views.

## 5. Parquet compression

`scripts/benchmark_parquet.py` rewrites 1,000,000 real exported rows with each
codec and verifies the row count round-trips.

| Codec | Size | Ratio vs raw | Write (s) | Read (s) | DuckDB agg (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| zstd | 34.9 MB | 2.42× | 0.30 | 0.06 | 0.014 |
| snappy | 59.9 MB | 1.41× | 0.13 | 0.05 | 0.010 |
| gzip | 35.4 MB | 2.38× | 0.55 | 0.10 | 0.015 |
| uncompressed | 84.4 MB | 1.00× | 0.10 | 0.05 | 0.008 |

ZSTD is the export default: same size as gzip at roughly half the write time and
better query speed than gzip. Parquet is ~35 B/row against ≈1.7 KB/row in
PostgreSQL.

## 6. Storage

`python -m scripts.storage_report` prints database size, per-table heap/index/TOAST
sizes, raw-row counts and the JSONB payload total. The duplicated
`raw_observations.payload` is the largest reclaimable block;
`python -m scripts.prune_raw_payloads --before YYYY-MM-DD` replaces it with a
provenance marker **only** for days covered by a checksummed Parquet export, and
is a dry run unless `--apply` is passed. Rows are never deleted.


## 7. 2026-11-04 optimization pass

Three slow paths were measured and fixed after the August backfill.

* **Harmonized map was blank.** The harmonized view bypassed the cell rollup and
  ran a `NOT IN` scan over every detection; at world zoom it hit the 60 s
  statement cap and returned 500. `cell_activity` now stores `matched_viirs` and
  `harmonized` per day/cell/sensor, rebuilt with the rollups. The live path uses
  `NOT EXISTS` (backed by the existing `observation_b_id` indexes).
* **Calendar matched counts.** `matched_viirs_by_day` summed the cell rollup
  instead of joining millions of match rows.
* **Sensor Intelligence period queries.** `observation_matches.match_day` is
  denormalised at insert and indexed with `match_status`; period counts no longer
  join every match to its observation.
* **Dashboard totals.** Detection totals and the synthetic count come from
  `daily_activity`; the endpoint also caches identical windows for 15 s.

| Request (2026-10-29 ? 11-04) | Before | After |
| --- | ---: | ---: |
| Harmonized world aggregate, z3 | 60 s timeout / blank | **0.03?0.05 s** (rollup) |
| Raw world aggregate, z3 | 0.15 s | **0.20 s** |
| Calendar (7 days) | 1.48 s | **0.05 s** |
| Dashboard overview | 2.16 s | **0.74 s** first, 0.00 s cached |
| Sensor Intelligence matches | 1.73 s | **0.08 s** |
| Sensor Intelligence summary | 1.73 s | **0.28 s** |
| Analytics summary | 0.47 s | **0.23 s** |
| GeoJSON, 2,000 points (large box) | 0.85 s raw / 2.05 s harmonized | unchanged, now uses `NOT EXISTS` |

Harmonized totals reconcile with the harmonized series: for the week the map
shows **781,631** deduplicated detections against **808,966** raw, i.e. 27,335
VIIRS detections already seen by MODIS. The full rollup rebuild over 12.7 M rows
took **146 s**.
