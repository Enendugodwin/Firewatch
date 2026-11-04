# Accuracy and consistency

Generated: 2026-11-04

Two questions are kept apart. **Corroboration** asks how often the two sensors agree on the same hotspot. **Burned-area agreement** is a rank correlation and is only reported when a burned-area table is supplied.

## Cross-sensor corroboration

| Reference region | MODIS | VIIRS | VIIRS with a MODIS association | Share |
| --- | ---: | ---: | ---: | ---: |
| Amazon fires, eastern Pará (2026-09-01 → 2026-10-31) | 14,898 | 164,275 | 19,786 | 12.0% |
| Central Kalimantan fires (2026-09-01 → 2026-10-31) | 29,954 | 435,330 | 52,801 | 12.1% |

A low share is not an error: VIIRS detects smaller and cooler fires than MODIS, so many VIIRS-only detections are expected. The share is a consistency measure, not an accuracy score, and it moves with the association thresholds.

## Burned-area agreement: not measured

No burned-area table was supplied, so no agreement figure is reported. The honest next step is to download MODIS MCD64A1 (or GFED) for each reference region and rerun with `--burned-area`; inventing a figure from the platform's own data would be circular.

