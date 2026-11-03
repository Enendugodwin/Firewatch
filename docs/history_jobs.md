# Running large datasets over long date ranges

Three ways to start the same job; all of them execute
`app/services/history_runner.py`, so the API, the CLI and a Python caller cannot
drift apart.

| Entry point | Use it for |
| --- | --- |
| `history_runner.run_history(request)` | a script, a notebook or a test |
| `python -m scripts.history run ...` | a terminal session on the host |
| `POST /api/v1/history/jobs` | the console or any HTTP client |

## The request

A request is a **dataset**, a **date range** and optionally a **region**:

```python
from datetime import date
from app.services.history_runner import HistoryRequest, run_history

request = HistoryRequest(
    datasets=("modis_history", "viirs_snpp_history"),
    start=date(2016, 1, 1),
    end=date(2024, 12, 31),
    region="amazon",          # or bbox="-70,-12,-50,2"
    harmonize=True,           # run the association pass over the same span
    refresh_every=100,        # roll up every 100 windows; 0 = only at the end
)
summary = run_history(request)
```

`run_history` is synchronous. It returns a dict with per-source inserts,
partition counts, failures, the harmonization summary and the duration.

### Datasets

| Key | Products |
| --- | --- |
| `modis_history` | `MODIS_SP` (2000-11-01 onward) |
| `viirs_snpp_history` | `VIIRS_SNPP_SP` (2012-01-20 onward, the long VIIRS record) |
| `viirs_history` | SNPP + NOAA-20 + NOAA-21 standard processing |
| `all_history` | every standard-processing product |
| `nrt` | the four near-real-time products (rolling window) |
| `all_products` | everything |

Datasets are bundles of FIRMS products, not files. Counts are always
*detections*, and MODIS and VIIRS counts are never added as if they measured the
same thing — the harmonized series is the only combined number and it is
documented in `docs/methodology.md`.

### Regions

`region` is a key from the backfill catalogue (`amazon`, `kalimantan`,
`mediterranean`, `australia`, `california`), or pass `bbox=west,south,east,north`.
Omit both for the whole globe. The tile key is stable, so rerunning the same
request resumes its partitions.

## Dates and coverage

A range of any length is split into five-day windows (the FIRMS area-endpoint
maximum). Before any request, coverage is read for every product and the window
is clamped to it:

* the coverage **end** is always respected — asking past it is what used to
  record unprocessed days as `empty`, which the calendar then read as quiet;
* the coverage **start** is only applied to standard-processing products, whose
  earliest date is definitive. A near-real-time window is rolling, so its
  reported minimum is not treated as a floor.

Days outside coverage are reported as `not_yet_available` or `missing`, never as
zero. If coverage cannot be read the plan says `coverage_known: false` and warns;
the ingestion layer still refuses to label uncovered SP days empty.

Check a plan before running it:

```bash
python -m scripts.history plan --datasets modis_history,viirs_snpp_history \
  --start 2016-01-01 --end 2024-12-31 --region amazon --harmonize
```

```
Tile region:amazon (-70.0,-12.0,-50.0,2.0): 1316 request(s), 6576 day(s)
  MODIS_SP           windows= 658 days= 3288 coverage=2000-11-01 .. 2026-08-31
  VIIRS_SNPP_SP      windows= 658 days= 3288 coverage=2012-01-20 .. 2026-07-31
Harmonization span: 2016-01-01 .. 2024-12-31
```

## Resumability and failure behaviour

* Every window is an `ingestion_partitions` row; a completed partition is skipped
  on rerun.
* Harmonization walks one UTC day per transaction and records each day in
  `harmonization_coverage`; reruns skip covered days.
* A failing window is recorded and the run continues. An authentication failure
  aborts immediately, because every remaining window would fail the same way.
* `should_stop` (or the job's cancel flag) is checked between windows and between
  harmonized days; cancelling keeps all completed work.

## Durable jobs (API and `--job`)

A multi-year run can take hours, so it is persisted as a `history_jobs` row and
executed after the HTTP response:

```bash
python -m scripts.history run --datasets modis_history --start 2016-01-01 \
  --end 2024-12-31 --region amazon --harmonize --job
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/history/datasets` | dataset catalogue |
| GET | `/api/v1/history/regions` | backfill regions |
| POST | `/api/v1/history/plan` | windows that would be fetched |
| POST | `/api/v1/history/jobs` | start a job (`202`, returns the row) |
| GET | `/api/v1/history/jobs` | recent jobs |
| GET | `/api/v1/history/jobs/{id}` | status and progress |
| POST | `/api/v1/history/jobs/{id}/cancel` | stop between windows |
| POST | `/api/v1/history/jobs/{id}/resume` | rerun; completed work is skipped |
| GET | `/api/v1/history/jobs/{id}/summary` | final summary |

Only one job may be queued or running at a time; a second request returns `409`.
Starting or resuming a job also requires `FIRMS_MAP_KEY` to be configured.

The job row survives a restart. `resume` sets it back to `queued`; ingestion
partitions and coverage checkpoints make that a continuation, not a restart.

## What this does not do

* It does not download the global multi-decade archive; that is terabytes of raw
  payloads. Choose regions, or accept the narrower history.
* It does not create regional boundaries. `region` maps to the bounding box in
  the catalogue; exact GeoJSON containment remains the regional engine's job.
* It does not merge sensors. Harmonization subtracts associated VIIRS detections
  from the combined count; the raw series stay untouched.
