# Amazon archive, 2016–2024 (ingested, harmonized, then removed)

This page records the Horizon 1 scale run before its rows were deleted to
reclaim disk. It is the durable summary: the observations themselves are no
longer in the store.

## What was ingested

Both sensors for the `region:amazon` tile (`-70,-12,-50,2`), one window per
run, resumable through `ingestion_partitions`:

| Year | MODIS_SP | VIIRS_SNPP_SP |
| ---: | ---: | ---: |
| 2016 | 113,366 | 435,207 |
| 2017 | 147,803 | 581,805 |
| 2018 | 85,033 | 327,963 |
| 2019 | 127,197 | 491,350 |
| 2020 | 132,862 | 566,694 |
| 2021 | 105,879 | 406,104 |
| 2022 | 159,688 | 618,783 |
| 2023 | 131,275 | 508,611 |
| 2024 | 217,247 | 844,691 |
| **Total** | **1,220,350** | **4,781,208** |

- 6,001,558 observations, 0 rejected, 1,316 / 1,316 windows successful,
  0 failed partitions.
- Detection days: 3,286 of 3,288 calendar days; the two without any detection
  are recorded as observed-but-empty, never as zero.
- Wall clock: 180.1 min for the resumed ingestion + harmonization job; the
  original MODIS half took 55.8 min on its own.

## Harmonization

One UTC day per transaction, tracked in `harmonization_coverage` (missing row =
not scanned, not "no duplicates"):

| | |
| --- | ---: |
| Days scanned | 3,288 |
| Candidate pairs | 4,535,583 |
| Probable associations | 752,355 |
| Possible associations | 1,820,684 |
| Rejected pairs | 1,962,544 |
| VIIRS detections with a MODIS association | 1,458,779 |
| **Harmonized total** (MODIS + VIIRS − associated VIIRS) | **4,542,779** |

Association share: 1,458,779 / 4,781,208 = **30.5 %** of VIIRS detections have a
probable or possible MODIS association on the same UTC day. This is a
consistency measure between sensors, not an accuracy score. A VIIRS detection
can produce more than one pair, which is why distinct matched VIIRS
(1,458,779) is smaller than probable + possible pairs (2,573,039).

## Cross-sensor corroboration (separate, 2026 reference windows)

`docs/validation/accuracy.md` reports the fixed 2026 reference windows
(Amazon/Pará 12.0 %, Central Kalimantan 12.1 %). Those are short, dense
two-month windows and are not comparable with the nine-year archive share
above; both are "share of VIIRS with a MODIS association", measured over
different periods.

## Burned-area agreement

Still **not measured**. It needs an external MCD64A1 or GFED table; a figure
derived from the platform's own detections would be circular.

## Removal

The footprint was deleted with `scripts/delete_history.py --tile-key
region:amazon --apply`, which removes associations, event memberships,
availability rows, observations, raw payloads, coverage checkpoints,
partitions and runs, then rebuilds only the affected rollup days. The global
2026 ingest and the fixture rows were not touched.
