# Historical backfill

## Why the archive was empty before

The standard-processing (SP) products always had history available:

| Product | Coverage reported by FIRMS (2026-11-03) |
| --- | --- |
| `MODIS_SP` | 2000-11-01 → 2026-08-31 |
| `VIIRS_SNPP_SP` | 2012-01-20 → 2026-07-31 |
| `VIIRS_NOAA20_SP` | 2018-04-01 → 2026-07-31 |
| `VIIRS_NOAA21_SP` | 2023-03-01 → 2026-07-31 |

The earlier "SP returns zero rows" was not an API failure. The requests asked for
September–November 2026, which is *after* the SP coverage end. The API answers
those requests with a header-only 200, which ingestion recorded as `empty` — and
`empty` means "observed, no detections", not "not processed". That mislabelling
made unprocessed days look quiet in the calendar.

Fixes:

* `scripts/backfill_history.py` reads coverage first and clamps the window to it.
* `app/services/ingestion.py` verifies coverage before recording `empty` for an SP
  product, and records `not_yet_available` otherwise.
* `scripts/repair_availability.py` relabelled 213 existing out-of-coverage rows
  (one per SP source per day, 2026-09-02 → 2026-11-02).

## What is ingested

A *global* multi-decade backfill is not practical on a workstation: the global
MODIS archive alone is on the order of 10^8 detections and terabytes of raw
payloads. History is therefore built for documented fire regions
(`app/services/historical_backfill.py`):

| Key | Region | Bounding box |
| --- | --- | --- |
| `amazon` | Amazon arc of deforestation | -70, -12, -50, 2 |
| `kalimantan` | Central Kalimantan | 108, -6, 120, 4 |
| `mediterranean` | Mediterranean basin | -8, 34, 30, 46 |
| `australia` | South-east Australia | 138, -40, 155, -24 |
| `california` | California and the south-west | -124, 32, -114, 42 |

Days outside the ingested regions remain `unobserved` in the calendar — never
`quiet` and never zero. Adding a region is a catalogue entry plus a rerun; it does
not change the schema.

## Measured results

`python -m scripts.backfill_history --region amazon --start 2016-01-01 --end 2024-12-31 --sources MODIS_SP`

* 658 requests, 1,220,982 records received, **1,205,718 inserted**, 0 rejected.
* **55.8 minutes** wall clock, including two incremental rollup refreshes.
* Years now present for the Amazon box: 2016–2024 (MODIS), with 2026 global from
  the NRT products.

VIIRS history for the same region is ingested with `--sources VIIRS_SNPP_SP`; the
VIIRS archive is several times denser, so expect a longer run and roughly 5–8 GB
of additional storage per region.

## Resumability

Every request is an ingestion partition keyed by `(source, tile_key, date_start)`.
Re-running the same command skips completed partitions, so an interrupted
backfill resumes without duplicating rows. `--limit-requests` exists for pilots.

## What this does not do

* It does not download the global archive. Regions outside the catalogue have no
  historical series.
* It does not merge sensors. MODIS and VIIRS remain separate series; the
  harmonised calendar subtracts associated VIIRS detections (see
  `docs/methodology.md`).
* A backfilled year is complete only if all its days were covered. The regional
  and calendar engines still refuse to call a trend significant without eight
  complete years.
