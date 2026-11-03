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

The full specification — candidate generation, every component, worked examples, the radiometric
comparison policy and the known limitations — is in [`formula.md`](../formula.md).

### 3.1 Harmonised series (implemented, `harmonized-series-v1`)

The association engine answers "are these the same hotspot?"; the harmonised series turns that
into one consistent count per day without editing the raw data:

```
harmonized = MODIS + VIIRS − matched_VIIRS
```

`matched_VIIRS` is the number of distinct VIIRS detections with at least one probable or possible
MODIS association on the same UTC day. Raw sensor series remain unchanged; days without associations
return their raw count and the response says so. This is a documented de-duplication, not a
calibrated fire count, because the association score is not a probability of identity.

## 4. Event grouping (implemented, `events-v1`)

DBSCAN in a normalised space-time metric: spatial distance (metres) and temporal distance
(seconds) each divided by their epsilon before combining, so one neighbourhood has one definition
in both dimensions. Defaults: 1.5 km, 24 h, ≥ 2 observations. Neighbourhoods are computed in
chunks to bound memory.

Every event keeps its member observation ids, first/last detection, centroid and extent, sensor
count, and **separate** maximum and aggregate FRP. An event is an estimate; it never implies
continuous monitoring between overpasses.

## 5. Calendar metrics (implemented)

Independent metrics, never one blended number: raw MODIS, raw VIIRS, combined raw, **harmonized**,
probable match groups, estimated events, aggregate FRP. Every cell carries completeness so missing
data is not read as zero, and clicking a cell drills into observations.

`harmonized` is computed per bucket as `detections - matched_viirs`, where `matched_viirs` counts
distinct VIIRS detections that have a probable or possible MODIS association on the same day,
under the same filters. It is the same definition as `/harmonization/series`, so the calendar and
the series cannot disagree. Days that have not been scanned for associations keep their raw count;
the response notes this rather than implying a complete de-duplication.

### 5.1 Association coverage checkpoints (implemented)

The in-app pass remains a single-scope recompute with a safety cap. The archive pass
(`scripts/harmonize_history.py`) walks one UTC day per transaction and records each processed day in
`harmonization_coverage` (day, scope, synthetic, observations, pairs, status counts). A missing row
means "not processed", which is different from "processed and nothing matched". Reruns skip covered
days unless `--force` is set.

## 6. Baselines, anomalies, trends and seasonality (implemented)

Per region, metric and sensor. Minimum sample counts are required before any anomaly is declared,
and missing days are excluded rather than counted as zero.

```
MAD = median(|xᵢ − median(X)|)
Z_r = (x − median(X)) / (1.4826 × MAD)
```

For each evaluated day the baseline is the median of the preceding `baseline_days` **observed** days
(default 30). When that history is too short, the engine falls back to a leave-one-out baseline over
the window and labels it `within_window`; with too few days even for that it returns
`insufficient_history` instead of a score. Zero MAD is handled by a standard-deviation fallback, and
a constant baseline is reported as `unknown_scale` rather than ranked.

The fire calendar adds two companion analyses, each with its own gate (`services/trends.py`,
`calendar-intel-v1`):

- **Trend** — Theil–Sen slope over observed days, expressed per day and per 30 days, with a
  direction band (a 5% move over 30 days is `flat`), a first-to-last level ratio and a
  low/medium/high confidence based on sample count and coverage. The median of pairwise slopes is
  used because a single extreme day would drag a least-squares line. Fewer than 10 observed days
  returns `insufficient_history`.
- **Seasonality** — per calendar-month means across years, where a month's value is the mean of its
  *yearly monthly means* so a year with more observed days does not dominate. A month counts only
  with at least two years that each observed it on ≥ 5 days. With one year the profile is shown as
  `single_year` and no index, peak or trough is claimed; with partial coverage it is `partial` and
  peak/trough are withheld until ≥ 9 months qualify.

Isolation Forest remains an optional secondary model, never the sole basis for an alert. Every
anomaly exposes observed/expected values, sample size, baseline period, method, model version,
evidence ids and completeness.

## 7. Regional analysis (implemented)

Regional statistics are computed once per region and period, then stored
(`regional_daily_statistics`, `regional_cell_statistics`). Reads never scan the
observation table.

- **Exactness** — a SQL bounding-box prefilter selects candidates; Shapely
  `contains_xy` applies the actual polygon. The box never produces a published
  count. Boundaries are stored as GeoJSON because PostGIS is absent.
- **Coverage** — a month contributes to climatology only when ≥ 80% of the
  *requested* days in that month are covered; a year is complete at ≥ 90%.
- **Trend** — Mann–Kendall with tie correction on complete years, p-value from the
  normal approximation, Sen's slope as the median of pairwise slopes, and lag-1
  serial correlation reported because the test assumes independence. Fewer than
  eight complete years returns `insufficient_years`.
- **Seasonality** — mean of yearly monthly means, with median and p90; the index is
  the month mean over the mean of usable months. Peak and trough require six
  qualifying months and two years.
- **Anomalies** — each month against the same calendar month in other years, robust
  z with `1.4826 × MAD`; a negative deviation is `below_baseline`.
- **Spatial** — a 0.5° equirectangular grid (H3 is not installed), with
  years-seen and a recurrence share over the analysed span.
- **Sensors** — per-sensor series and monthly Pearson correlation where both have
  coverage; combined series are labelled and never assumed interchangeable.



## 8. Exposure screening

PostGIS geodesic distance from detections to settlements and infrastructure, reported in
configurable bands (0–1, 1–5, 5–10, 10–25 km) and labelled **geographic screening**. A nearby
hotspot may be an agricultural burn, industrial heat or a false positive; proximity is not threat.

## 9. Language rules

- Counts are detections, not fires.
- Sensor totals are not interchangeable.
- Absence of a detection is not absence of fire.
- Forecasts describe expected activity, never the location or spread of a specific fire.
- AI prose may summarise measurements but never overwrite or invent them.
