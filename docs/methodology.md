# Methodology

This document states the methods FIREWATCH X will apply and, for each, whether it is implemented
today. Phase 1 ships no analytical computation: everything below marked *planned* is a
specification, not a claim of results.

## 1. Normalisation (Phase 2 — planned)

Each FIRMS record becomes a canonical observation (`docs/data_dictionary.md`) with:

1. Coordinate validation — latitude ∈ [-90, 90], longitude ∈ [-180, 180], no null island unless the
   provider says so.
2. Timestamp validation — parse `acq_date` + `acq_time` (HHMM, UTC) into a timezone-aware instant;
   reject impossible times rather than coercing them.
3. Numeric validation — FRP ≥ 0 or explicitly null; brightness temperature within a sane range for
   the channel.
4. Schema validation against the source adapter's expected columns; unknown columns retained.
5. Deduplication on source identity (product + source record id, or a documented fingerprint).
6. Quality flags recorded, never silently dropped.

MODIS and VIIRS adapters are separate: field names, confidence encodings and brightness channels
differ by product, so a single generic mapper is not used.

## 2. Cross-sensor harmonization (Phase 3 — planned)

Raw observations are **not** merged. Distinct concepts are preserved:

```
raw satellite observation  →  probable cross-sensor match  →  estimated fire event
```

Candidate association compares observations from different sensor families within a time window:

- Temporal similarity `T`
- Geodesic proximity `G` (metres, not degrees)
- Footprint overlap `F`, where pixel scan/track geometry permits it

Association score: `S = wₜ·T + wₛ·G + w_f·F`, weights configurable and stored with the run.

Classification thresholds produce `probable`, `possible`, `unmatched` or `rejected`. The score is an
association score, not the probability that two detections are the same physical fire. Every pair
keeps its components so a user can inspect *why* a match was produced.

Event grouping (optional, DBSCAN first) clusters observations in space and time and records:

- member observation ids, first/last detection, extent, sensor coverage
- aggregate and maximum FRP, **labelled separately**
- observation count, clustering parameters, methodology version

Events are estimates. They never imply continuous monitoring between satellite overpasses.

## 3. Calendar metrics (Phase 5 — planned)

The burning calendar exposes six independent metrics, never one blended number:

1. Raw MODIS detections
2. Raw VIIRS detections
3. Combined raw detections
4. Probable cross-sensor match groups
5. Estimated fire events
6. Aggregate FRP

Each cell carries a completeness status so that **missing data ≠ zero activity**. FIRMS availability
and missing-date services determine whether a day is genuinely quiet or simply unobserved. Clicking
a cell drills into the underlying observations.

## 4. Baselines (Phase 6 — planned)

Baselines are computed per region, metric and sensor. Comparisons must be seasonal: January activity
is never compared with a July baseline where seasonality is strong.

Supported baseline types: rolling 30/90-day, same period in previous years, day-of-year seasonal,
monthly historical. A minimum sample count is required before any anomaly may be declared.

## 5. Anomaly scoring (Phase 6 — planned)

Robust standardized deviation:

```
MAD  = median(|xᵢ − median(X)|)
Z_r  = (x − median(X)) / (1.4826 × MAD)
```

Zero or near-zero MAD, small samples and missing days are handled explicitly (no division by zero,
no alert from an empty baseline). Classifications are severity bands, not wildfire probabilities.
Isolation Forest is an optional secondary model, never the sole basis for an alert.

Every anomaly record exposes: region, metric, observation period, baseline period, observed value,
expected value, deviation score, sample size, method, model version, evidence ids and completeness.

## 6. Exposure screening (Phase 6 — planned)

Detection points are compared with infrastructure and settlement datasets using PostGIS geodesic
distance. Results are reported in configurable bands (0–1 km, 1–5 km, 5–10 km, 10–25 km) and
labelled **geographic screening**. A nearby hotspot may be an agricultural burn, an industrial heat
source or a false positive; proximity is not threat, spread or impact.

## 7. Uncertainty and language

- Counts are detections, not fires.
- Sensor totals are not interchangeable.
- Absence of a detection is not absence of fire.
- No forecast may claim to predict the location or spread of a future fire; only expected activity.
- AI-generated prose may summarise measurements but never overwrite or invent them.
