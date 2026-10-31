# Methodology

Each section states whether the method is implemented today or still a specification. Phase 1
shipped the foundation; Phases 2 and 3 shipped retrieval, normalization, association and event
grouping. Later sections remain planned.

## 1. Retrieval and availability (implemented)

- Area CSV queries of at most five days, over a tile or a custom bounding box.
- Exponential backoff with jitter; `Retry-After` honoured; 4xx auth failures are not retried.
- The MAP_KEY is redacted from every log line, error message and stored URL.
- A 200 with an empty body means *no detections*; an `Invalid MAP_KEY` body is an authentication
  failure. Those are never conflated.
- `data_availability` returns a coverage window (`min_date`, `max_date`). A date inside it is an
  observed day and may legitimately contain zero detections; a date before it is
  `before_coverage`, after it `not_yet_available`. Neither is recorded as zero activity.
- Standard Processing lags NRT by weeks; the platform records the difference instead of hiding it
  (verified: MODIS_SP covered through 2026-08-31 while MODIS_NRT covered 2026-10-30).

## 2. Normalisation (implemented)

Separate adapters per sensor family:

1. Coordinate validation (latitude ±90, longitude ±180); invalid rows are rejected, never repaired.
2. `acq_date` + `acq_time` (HHMM, UTC) parsed into an aware instant; missing or impossible times
   are rejected.
3. Numeric validation; negative FRP is treated as absent rather than negated.
4. MODIS keeps the 0–100 confidence as `confidence_raw` plus an **application** category; VIIRS
   keeps its categorical `l/n/h` mapped to `low/nominal/high` with `confidence_raw = NULL`.
5. Brightness channels are labelled per sensor (`modis_brightness_4um`, `viirs_bright_ti4_4um`) and
   are never compared as if equivalent.
6. FIRMS `type` ≠ 0 is flagged `suspected_non_fire`.
7. Identity is a SHA-256 fingerprint, since FIRMS supplies no row id.

## 3. Cross-sensor association (implemented, `assoc-v1`)

Only observations from **different sensor families** are compared. All components are stored:

```
S = (wₜ·T + wₛ·G + w_f·F) / Σw
T = 1 − (|Δt| / window)²      (quadratic temporal tolerance)
G = 1 − distance / max_distance
F = 1 − distance / (rₐ + r_b) (circular footprint approximation, optional)
```

Defaults: 180-minute window, 2 km screening distance, `wₜ=0.40`, `wₛ=0.45`, `w_f=0.15`,
probable ≥ 0.75, possible ≥ 0.55, stored ≥ 0.35.

Temporal tolerance is quadratic because MODIS and VIIRS overpasses are systematically minutes to
hours apart; a linear penalty suppressed genuine associations purely because satellites are not
coincident. The window remains a hard cut-off. When a footprint is unknown, weights are
renormalised over the available components instead of inventing geometry.

**The score is an association score, not the probability that two detections are the same fire.**
Results are recorded with the algorithm version, the parameters and the analysis scope.

## 4. Event grouping (implemented, `events-v1`)

DBSCAN in a normalised space-time metric: spatial distance (metres) and temporal distance
(seconds) each divided by their epsilon before combining, so one neighbourhood has one definition
in both dimensions. Defaults: 1.5 km, 24 h, ≥ 2 observations. Neighbourhoods are computed in
chunks to bound memory.

Every event keeps its member observation ids, first/last detection, centroid and extent, sensor
count, and **separate** maximum and aggregate FRP. An event is an estimate; it never implies
continuous monitoring between overpasses.

## 5. Calendar metrics (Phase 5 — planned)

Six independent metrics, never one blended number: raw MODIS, raw VIIRS, combined raw, probable
match groups, estimated events, aggregate FRP. Every cell carries completeness so missing data is
not read as zero, and clicking a cell drills into observations.

## 6. Baselines and anomalies (Phase 6 — planned)

Per region, metric and sensor; seasonal by construction (December is never compared with a July
baseline). Rolling 30/90-day, same period in previous years, day-of-year and monthly baselines.
Minimum sample counts are required before any anomaly is declared.

```
MAD = median(|xᵢ − median(X)|)
Z_r = (x − median(X)) / (1.4826 × MAD)
```

Zero MAD and small samples are handled explicitly. Isolation Forest is an optional secondary model,
never the sole basis for an alert. Every anomaly exposes observed/expected values, sample size,
baseline period, method, model version, evidence ids and completeness.

## 7. Exposure screening (Phase 6 — planned)

PostGIS geodesic distance from detections to settlements and infrastructure, reported in
configurable bands (0–1, 1–5, 5–10, 10–25 km) and labelled **geographic screening**. A nearby
hotspot may be an agricultural burn, industrial heat or a false positive; proximity is not threat.

## 8. Language rules

- Counts are detections, not fires.
- Sensor totals are not interchangeable.
- Absence of a detection is not absence of fire.
- Forecasts describe expected activity, never the location or spread of a specific fire.
- AI prose may summarise measurements but never overwrite or invent them.
