# Regional Intelligence

Trend, seasonality and anomaly analysis for any boundary: a country, an imported
administrative polygon, a drawn GeoJSON boundary or a radius.

## 1. Why it does not scan 11.34 million rows

| Path | Cost |
| --- | --- |
| `POST /regions/{id}/analyze` | one bbox-prefiltered observation scan, exact polygon test |
| every read endpoint | a few hundred rows from `regional_daily_statistics` |

The analysis pass writes region × day × sensor rows (`MODIS`, `VIIRS`, `ALL`) plus a
0.5° recurring-activity grid. Opening the page afterwards never touches
`fire_observations`.

Measured on the live store (11.3 M observations, 61 days):

| Step | Result |
| --- | --- |
| Analyse Nigeria (12° box, 68 643 candidates) | 3.7 s |
| Overview (totals + trend + anomalies) | 0.24 s |
| Monthly / yearly / trends / anomalies | 9–10 ms |
| Seasonality | 23 ms |
| Sensor comparison | 19 ms |

## 2. Boundaries and exactness

PostGIS is absent from the portable PostgreSQL build, so:

* boundaries are stored as **GeoJSON** (`geographic_regions.geometry`);
* containment is evaluated with **Shapely** after a SQL bounding-box prefilter;
* the bounding box is only a candidate filter — every published count uses the
  polygon, never the box;
* `boundary_kind` says how much to trust the shape: `polygon` (imported or drawn),
  `circle` (radius buffer), `bbox` (gazetteer rectangle, `is_approximate = true`).

A boundary that crosses the antimeridian is rejected rather than silently merged.
Vertices are capped at 50 000 per region.

## 3. What the engine computes

* **Monthly climatology** — per calendar month, the mean of yearly monthly means
  (so a year with more observed days does not dominate), plus median and p90.
  A month counts only when at least two years each covered ≥ 80% of the requested
  days in that month; peak and trough are withheld until six months qualify.
* **Day-of-year profile** — a ±7-day window across available years.
* **Trend** — Mann–Kendall on complete years (coverage ≥ 90%), with tie correction,
  Sen's slope (median of pairwise slopes), p-value, and lag-1 serial correlation.
  Fewer than eight complete years returns `insufficient_years`; YoY changes are
  still shown without a significance claim.
* **Seasonal trends** — the same test per calendar month where ≥ 5 years exist.
* **Anomalies** — each month compared with the **same calendar month** in other
  years, robust z with a MAD scale; a negative deviation is `below_baseline`.
* **Spatial activity** — detections, FRP and years-seen per 0.5° cell, with a
  recurrence share. H3 is not installed, so this is a plain grid, labelled as such.
* **Sensor comparison** — per-sensor totals and record span, plus a Pearson
  correlation of monthly totals only where both sensors have coverage.
* **Current month vs historical median** — the month at the end of the window is
  compared with the median of the same calendar month in prior years. Needs three
  prior years; otherwise the count is shown without a comparison.

## 4. Scientific guards

* Counts are detections, not fires.
* Combined (`ALL`) series are labelled; they are never substituted for a sensor.
* A day with no detections is a zero only when a source recorded coverage for it.
* A month contributes only above the coverage floor; a partial month is excluded
  from climatology and marked in the heatmap as no coverage.
* Coverage is measured against the requested days inside each month, not the whole
  month, so a six-day request is not penalised as “6 of 31”.
* A sensor gap is never read as a change in fire activity.

## 5. Endpoints

```
GET  /api/v1/regions                     ranking (approximate boxes) + region_id
GET  /api/v1/regions/catalog             selectable regions
POST /api/v1/regions/custom              GeoJSON boundary (Polygon/MultiPolygon/Feature/FeatureCollection)
POST /api/v1/regions/radius              circular region
GET  /api/v1/regions/{id}                boundary metadata (geometry opt-in)
POST /api/v1/regions/{id}/analyze        compute and store regional statistics
GET  /api/v1/regions/{id}/overview
GET  /api/v1/regions/{id}/daily
GET  /api/v1/regions/{id}/monthly
GET  /api/v1/regions/{id}/yearly
GET  /api/v1/regions/{id}/seasonality
GET  /api/v1/regions/{id}/trends
GET  /api/v1/regions/{id}/anomalies
GET  /api/v1/regions/{id}/spatial-activity
GET  /api/v1/regions/{id}/sensor-comparison
GET  /api/v1/regions/{id}/export         monthly + yearly CSV
```

`POST /regions/{id}/export` and an asynchronous export job were specified but are
not implemented: at the current data size the CSV is generated and streamed
synchronously, so there is nothing to poll.

## 6. Tables

* `geographic_regions` — slug, name, level, boundary kind, GeoJSON, bbox, area,
  vertex count, boundary version, source, approximation flag, last analysis.
* `regional_daily_statistics` — region × date × sensor counts, FRP, high-confidence
  count, coverage, algorithm version.
* `regional_cell_statistics` — region × 0.5° cell totals, years seen, first/last year.

Monthly, yearly and seasonal results are derived from the daily rows on read: they
are cheap at this scale and cannot drift from the daily facts.

## 7. Limitations

1. **No bundled administrative polygons.** Countries are approximate gazetteer
   boxes until a GeoJSON boundary is imported; states and provinces require an
   import.
2. **No PostGIS.** Containment is application-side, which bounds a single pass to
   1.5 M candidate rows.
3. **No H3.** The recurring-activity grid is 0.5° equirectangular.
4. **History.** The live store currently holds 61 days, so seasonality is
   `single_year`, trends `insufficient_years` and anomalies `insufficient_history`
   on real data. These gates lift automatically as history accumulates.
5. **Area** is a planar approximation at the polygon's mean latitude, for display.

## 8. Verified live

Nigeria (approximate box), 2026-09-02 → 2026-11-01:

* 68 642 detections, 61/61 days covered, 385 cells;
* seasonality `single_year` (one year of coverage), no peak claimed;
* trend `insufficient_years` (0 complete years);
* sensor comparison `ok` — MODIS 3 074, VIIRS 65 568, monthly r = 0.95.
