# Scientific validation

The platform is only credible if its numbers reconcile with the observations behind them and if gaps
are labelled as gaps. This document records what is verified and what each later phase must prove.

## Verified in Phases 1–3

| Check | Method | Result |
| --- | --- | --- |
| No fabricated observations | Every pending route returns `501` with an envelope and no `items`/`features` | Pass |
| Freshness is measured, not implied | `/system/status` derives it from `max(acquired_at)` and run records | Pass |
| Module readiness cannot be overstated | Only delivered modules report `ready` in the registry | Pass |
| Migrations reversible and dialect-portable | upgrade → downgrade → upgrade on SQLite; PostGIS guarded | Pass |
| Seed idempotent | seed twice → 8 sources, no duplicates | Pass |
| Coordinate validation | Out-of-range latitude/longitude rejected, not clamped | Pass |
| Timestamp handling | `acq_date`+`acq_time` → exact UTC instant; impossible times rejected | Pass |
| Confidence semantics preserved | MODIS 0–100 kept with an application band; VIIRS categorical kept, `raw = NULL` | Pass |
| Channels not conflated | MODIS 4 µm and VIIRS `bright_ti4` labelled distinctly and never equated | Pass |
| Non-fire anomalies flagged | FIRMS `type` ≠ 0 → `suspected_non_fire` | Pass |
| Fingerprint identity | Stable across identical rows; distinct on 1-minute/time change | Pass |
| Deduplication | Re-ingesting the same window inserts 0 new rows; raw payloads not rewritten | Pass |
| Resumable backfill | Succeeded partitions skipped on re-run | Pass |
| FIRMS retries | 503/429/transport retried with backoff; 403 not retried | Pass |
| Key hygiene | MAP_KEY redacted from logs, errors and stored URLs | Pass |
| Availability semantics | Coverage window → `available` inside, `before_coverage`/`not_yet_available` outside, never zero | Pass |
| Cross-family only | No same-sensor pair is ever scored | Pass |
| Score components | Temporal/spatial/footprint values, weights and note persisted per pair | Pass |
| Threshold ordering | probable > possible ≥ store enforced; weak pairs not stored | Pass |
| Idempotent association | Re-running produces the same pair count, no duplicates | Pass |
| Event provenance | Each event links its member observations; counts reconcile | Pass |
| Event FRP labels | Maximum and aggregate stored and reported separately | Pass |
| Idempotent clustering | Re-running produces the same event count | Pass |
| Scope recorded | Every algorithm run stores bbox and dates; the UI states them | Pass |
| Provenance isolation | Synthetic and real observations are never harmonized together | Pass |
| UI surfaces the empty state | Tests assert the reason comes from the API, not a placeholder | Pass |
| Aggregation reconciles | Cell counts sum to the total and split correctly by sensor | Pass |
| Aggregation respects filters | `sensor=MODIS` yields zero VIIRS counts; confidence ladder applied | Pass |
| Zoom threshold | Aggregation below z6, bounded points above it; trimming reported | Pass |
| Map never bulk-exports | Point requests are capped and labelled `truncated` | Pass |
| Gazetteer safety | Coordinate parsing rejects out-of-range pairs; no result is invented | Pass |

Totals: **102 backend tests, 14 frontend tests**, Ruff and mypy clean, strict TypeScript build.

## Case study: availability was a range, not a list

The first live check returned `available: 0, missing: 4` for dates that demonstrably had
detections. The FIRMS endpoint returns:

```
data_id,min_date,max_date
VIIRS_SNPP_NRT,2026-08-01,2026-10-30
```

The parser had assumed a list of dates, so every requested day was marked missing. That is precisely
the failure the specification warns about — a gap silently rendered as "no fire". The parser now
reads the coverage window, classifies dates inside it as observed, and labels dates outside it
`before_coverage` / `not_yet_available`. Tests pin both shapes (window and legacy list) and the
classification of out-of-range days.

The same live check confirmed the SP/NRT distinction the platform must preserve: `MODIS_SP` covered
through 2026-08-31 while `MODIS_NRT` covered 2026-10-30, so a recent date is genuinely
`not_yet_available` for standard processing.

## Live verification (2026-10-30)

| Step | Result |
| --- | --- |
| Availability, `VIIRS_SNPP_NRT` | coverage 2026-08-01 → 2026-10-30 |
| Ingestion, Nigeria bbox 2.5,4.0,14.7,13.9, 2026-10-29 → 30 | VIIRS 3,617 rows; MODIS_NRT 483 rows |
| Deduplication | Re-running the VIIRS window inserted 0 new rows |
| Harmonization (scoped) | 4,100 observations → 659 candidate pairs, 29 probable, 157 possible |
| Event grouping (scoped) | 587 estimated events, 158 seen by both sensors |
| Store total | 87,578 detections, 0 synthetic |

### Calendar verification (2026-10-31)

| Check | Result |
| --- | --- |
| Range coverage | 7-day request returned 7 buckets (3 active, 4 unobserved) |
| Reconciliation | Sum of bucket detections equals the range total (133,237) |
| Sensor split | Per-bucket MODIS + VIIRS equals bucket detections |
| Coverage states | Days before ingestion are `unobserved`, not zero; `empty` availability yields `quiet` |
| Drill-down | Bucket 2026-10-29 returns 55,612 detections; the first page matches the bucket metrics |
| Query cost | Day-level aggregation dropped from ~12.6 s to ~0.5 s after removing the wide subquery |

### Map verification (2026-10-31)

| Check | Result |
| --- | --- |
| World view | 57 cells covering 87,578 detections at 22.5° grid |
| Zoomed view (Lagos) | 9 individual detections in the viewport, each inspectable |
| Inspection | Click returns coordinates, UTC time, confidence 81 (high), brightness 325.8 K, FRP 22.01 MW from the stored record |
| Basemap failure | Data layers and inspection continue without tiles |

## Required before a later-phase claim

| Validation | Criterion |
| --- | --- |
| Calendar reconciliation | Σ daily cells = stored observation count for every metric |
| Missing data | A known-outage day is `no_data`, never `0` |
| Baselines | Recomputing from the same snapshot gives identical median/MAD |
| Anomaly detection | Synthetic spike/shift/flat-baseline/tiny-sample cases classify as expected |
| Match precision/recall | Curated reference pairs; reported precision/recall, rejected pairs explained |
| Exposure distances | Geodesic distance matches an independent library within tolerance |
| Forecasts | Rolling-origin backtest beats the seasonal baseline before any forecast is shown |

## Known limitations

- Association thresholds (0.75/0.55/0.35) and the 180-minute window are **provisional defaults**;
  precision/recall has not been measured against curated reference pairs yet.
- The temporal term uses a quadratic tolerance; it is documented, stored per pair and applied
  identically to every pair, but it is a modelling choice rather than a NASA product.
- Event clustering truncates long observation windows by design (bounded memory). Runs record their
  scope; a global multi-year clustering pass needs a different strategy.
- CI runs on SQLite, so PostGIS behaviour (spatial indexes, geodesic SQL) is not exercised there.
- MODIS/VIIRS brightness temperatures are not equivalent and must not be compared directly.
- Hotspot counts are detections. Cloud suppresses detections; smouldering fires may be missed;
  industrial and agricultural heat appear as hotspots.

## Reporting rules

Every report must carry: generation timestamp, geographic area, observation period, data sources and
processing versions, methodology, statistical limitations and the observation identifiers behind
each figure.
