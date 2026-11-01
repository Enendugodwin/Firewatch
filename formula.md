# formula.md — how MODIS and VIIRS are compared

This document specifies, precisely and reproducibly, the method FIREWATCH X uses to compare
MODIS and VIIRS detections. It documents the **implemented** behaviour of `assoc-v1`
(`backend/app/services/harmonization.py`, geometry in `backend/app/services/geo.py`), not an
intended design.

Two different questions are answered separately below, because they have different answers:

1. **Which detections refer to the same place and time?** — answered with a geometric score (§3–§6).
2. **Do the measured values agree?** — deliberately *not* answered by subtraction or ratio (§7).

The governing rule is the same throughout: **detections are never merged, and no radiometric
value is ever converted into, or compared as if it were, another sensor's value.**

---

## 1. What is compared

| Compared | Not compared |
| --- | --- |
| Position (lat/lon) | Brightness temperature across sensors |
| Acquisition time | FRP across sensors as a calibrated quantity |
| Pixel footprint (`scan`, `track`) | Confidence numbers across sensors |
| Sensor family identity | Same-family duplicates (NRT vs SP) |

**Only observations from different sensor families are compared** — MODIS against VIIRS. Two MODIS
detections are never paired, even if one is NRT and the other SP. Only the coordinate, time and
footprint geometry enter the score; the measured radiometry does not.

---

## 2. Inputs

Each observation contributes six fields to the comparison:

| Field | Source | Notes |
| --- | --- | --- |
| `latitude`, `longitude` | FIRMS row | WGS84, validated at ingest |
| `acquired_at` | `acq_date` + `acq_time` | UTC, timezone-aware |
| `scan_km`, `track_km` | FIRMS `scan` / `track` | Pixel extents; `null` when absent or ≤ 0 |
| `sensor` | Product registry | `MODIS` or `VIIRS` |

`brightness_temperature`, `frp_mw` and `confidence_category` are loaded for display and evidence but
are **not** score inputs.

Observations are ordered by `acquired_at`, filtered to one provenance scope (`is_synthetic`), and
optionally to a bounding box and date window. If the scope exceeds `max_observations = 20 000`, the
**latest** 20 000 rows are kept and a warning is logged — the scope is silently narrowed, which is a
known limitation (§9).

---

## 3. Candidate generation

1. Observations are grouped into **UTC day buckets** by `acquired_at.date()`.
2. Inside a bucket, MODIS and VIIRS are sorted by time. VIIRS timestamps are held in a NumPy array.
3. For each MODIS detection, `np.searchsorted` selects only the VIIRS detections within
   **±180 minutes** — a hard temporal cut-off before any distance is computed.
4. Each surviving pair is measured with the great-circle distance (haversine, mean Earth radius
   6 371 008.8 m). Pairs farther than **2 000 m** are discarded.
5. Surviving pairs are scored (§4) and the result is stored only if `S ≥ 0.35`.

A detection is not forced to a single partner: one MODIS detection may produce several candidate
pairs, and the engine performs no assignment or de-duplication across pairs.

---

## 4. The association score

```
S = (wₜ·T + wₛ·G + w_f·F) / Σw
```

with default weights `wₜ = 0.40`, `wₛ = 0.45`, `w_f = 0.15`. Each component lies in `[0, 1]`.

### 4.1 Temporal similarity `T`

```
T = 1 − (|Δt| / window)²        window = 180 min = 10 800 s
```

Quadratic rather than linear: MODIS and VIIRS overpasses are systematically minutes to hours apart,
so a linear penalty would suppress genuine associations merely because the satellites are not
coincident. The window is still a hard cut-off — beyond ±180 min, `T` is clamped to 0 and the pair
is never considered.

### 4.2 Geographic proximity `G`

```
G = max(0, 1 − d / max_distance)        max_distance = 2 000 m
```

`d` is the haversine distance between the two reported pixel centres.

### 4.3 Footprint overlap `F`

Each rectangular pixel is approximated by a circle of equal area:

```
r = √(scan_km · track_km) / 2          (kilometres)
F = clamp(1 − d / (r_MODIS + r_VIIRS) · 1000 , 0, 1)
```

If either footprint is missing or non-positive, `F` is `null` — geometry is never invented.

### 4.4 Renormalisation

When `F` is unavailable, the score is computed over the remaining components only:

```
S = (wₜ·T + wₛ·G) / (wₜ + wₛ)
```

so a missing footprint redistributes its 0.15 rather than silently deflating the score. This has a
consequence that is documented rather than hidden: **a pair with an unknown footprint can score
higher than the same pair with a known, small footprint** (§6, case C).

### 4.5 Classification

| `S` | `match_status` | Stored |
| --- | --- | --- |
| ≥ 0.75 | `probable` | yes |
| ≥ 0.55 | `possible` | yes |
| ≥ 0.35 | `rejected` | yes (kept for inspection) |
| < 0.35 | — | no |

Every stored pair keeps `temporal_delta_seconds`, `spatial_distance_m`, `footprint_overlap`,
`association_score`, the full component payload (including the weights actually used) and
`algorithm_version`.

---

## 5. Why the score is not a probability

`S` is an **association score**: a similarity measure over place and time. It is not the probability
that two detections describe the same physical fire, because:

- the weights and thresholds were not fitted to reference fire perimeters;
- two different fires can lie within 2 km and 3 hours of each other;
- a large fire can produce several detections per sensor, so "the same fire" is not a one-to-one
  relation;
- the footprint term is a circular screening approximation, not a rigorous overlap of sensor
  geometries.

The interface and the API label it as an association score for this reason.

---

## 6. Worked examples

Using the defaults (`window = 10 800 s`, `max_distance = 2 000 m`, weights 0.40/0.45/0.15) and a
MODIS pixel of 1.0 × 1.0 km (`r = 0.500 km`) against a VIIRS pixel of 0.375 × 0.375 km
(`r = 0.1875 km`, so `r_a + r_b = 687.5 m`):

| Case | Δt | d | T | G | F | S | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 300 s | 600 m | 0.9992 | 0.7000 | 0.1273 | **0.7338** | `possible` |
| B | 300 s | 200 m | 0.9992 | 0.9000 | 0.7091 | **0.9111** | `probable` |
| C | 300 s | 600 m | 0.9992 | 0.7000 | `null` | **0.8408** | `probable` |
| D | 5 400 s | 1 500 m | 0.7500 | 0.2500 | 0.0000 | **0.4125** | `rejected` |
| E | 0 s | 0 m | 1.0000 | 1.0000 | 1.0000 | **1.0000** | `probable` |

Case A is the important one: five minutes and 600 m apart still yields only `possible`, because a
375 m VIIRS pixel barely overlaps a 1 km MODIS pixel at that offset. Case C is the renormalisation
effect — dropping the footprint term raises the same pair from 0.7338 to 0.8408. Case D shows that
the 2 km screen admits pairs whose footprints do not overlap at all; they are retained as
`rejected` for inspection rather than discarded.

---

## 7. Why the measured values are not compared directly

MODIS and VIIRS do not measure the same thing in the same way, so their radiometric values are
carried side by side and never subtracted, ratioed or substituted for one another.

| Property | MODIS (MOD14/MYD14) | VIIRS (VNP14IMG) |
| --- | --- | --- |
| Brightness field | `brightness` | `bright_ti4` |
| Channel | ~4 µm band (21/22) | I4 band, ~3.74 µm |
| Stored label | `modis_brightness_4um` | `viirs_bright_ti4_4um` |
| Nominal pixel | 1 km | 375 m |
| Confidence | numeric 0–100 | categorical `l` / `n` / `h` |

Different central wavelengths, spectral response functions, saturation behaviour, pixel areas and
retrieval algorithms mean that a few kelvin of difference between the two is expected **for the same
fire**. Treating `brightness_MODIS − bright_ti4_VIIRS` as a measurement would therefore report sensor
differences as fire behaviour. The database keeps `brightness_channel` on every observation precisely
so the two can never be pooled by accident, and the API never exposes a combined brightness value.

The same reasoning applies to fire radiative power:

- FRP is reported in megawatts per **detection**, and a detection covers a different ground area in
  each product (1 km versus 375 m), so per-detection FRP is not a like-for-like quantity.
- Where FRP is aggregated (calendar, dashboard, events), the aggregate is a **sum of reported
  values** over the detections in scope. Mixing sensor families changes the total partly because the
  sensor mix changed, not only because fire activity changed — which is why every aggregate is also
  broken down per sensor (`MODIS`, `VIIRS`, and the combined total are reported separately).
- In a matched pair, `a_frp_mw` (MODIS) and `b_frp_mw` (VIIRS) are shown as two independent
  provenance values in the match record and the CSV export. No ratio or difference is computed.

This is the operational meaning of "counts are detections, not fires; MODIS and VIIRS counts are
never interchangeable."

---

## 8. Event grouping (the only place sensors are brought together)

Pairwise scoring answers "are these two detections close in space and time?". Event grouping
(`events-v1`) answers a different question — "which detections belong to one episode?" — with
spatiotemporal DBSCAN over both families:

```
neighbourhood(a, b)  ⇔  (‖Δxy‖ / 1 500 m)² + (|Δt| / 24 h)² ≤ 1
```

with `min_samples = 2`. Member observations keep their identity; the event records first/last
detection, centroid, extent, observation count, sensor count, and **separate** maximum and aggregate
FRP. An event is an estimate and does not imply continuous monitoring between overpasses.

---

## 9. Known limitations

1. **UTC day buckets.** Candidates are paired only within the same UTC day, so a MODIS detection at
   23:50 and a VIIRS detection at 00:05 the next day are never compared despite being 15 minutes
   apart.
2. **Scope truncation.** Above 20 000 observations, only the latest 20 000 are used. The run records
   a warning, but the resulting associations cover a narrower scope than requested.
3. **Circular footprints.** `r = √(scan·track)/2` preserves area but not shape or orientation, so
   `F` is a screening value.
4. **Renormalisation asymmetry.** Missing footprint data can raise a score (§6, case C). Comparisons
   between runs with different data completeness are therefore not strictly like-for-like.
5. **Uncalibrated weights.** `0.40 / 0.45 / 0.15` and the 0.75 / 0.55 / 0.35 thresholds are
   operational defaults, not fitted or validated probabilities.
6. **No assignment.** One detection may pair with several detections from the other family; there is
   no one-to-one matching and no mutual-best filtering.
7. **Same-family duplicates remain.** NRT and SP versions of the same MODIS detection are separate
   rows and are never compared with each other, because both belong to the same sensor family.
8. **No cross-calibration.** No radiance, brightness-temperature or FRP harmonisation between
   sensors is performed anywhere in the pipeline.

---

## 10. Reproducibility

- Algorithm identifier: `assoc-v1` (stored on every match and on the audit run).
- Parameters: `MatchParameters` defaults, serialised into `algorithm_runs.parameters` together with
  the analysis scope (`bbox`, `start_date`, `end_date`) so any result can be recomputed exactly.
- Stored evidence per pair: temporal delta, distance, footprint overlap, score, status, component
  payload, weights, algorithm version.
- Re-running harmonisation for a scope deletes that scope's previous pairs first, so results cannot
  accumulate stale scores.

Relevant code: `backend/app/services/harmonization.py`,
`backend/app/services/geo.py`,
`backend/tests/test_harmonization.py`.
API: `GET /api/v1/harmonization/matches`, `GET /api/v1/harmonization/matches.csv`,
`POST /api/v1/harmonization/run`, `GET /api/v1/harmonization/status`.
