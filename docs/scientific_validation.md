# Scientific validation

The platform is only credible if its numbers reconcile with the observations behind them. This
document records what is verified today and what each later phase must prove before its output is
presented as analysis.

## Verified in Phase 1

| Check | Method | Result |
| --- | --- | --- |
| API never serves fabricated observations | `test_errors.py` asserts every pending route returns `501` with an error envelope and **no** `items`/`features` payload | Pass |
| Data freshness is reported, not implied | `test_system.py` asserts `freshness = "no_data"`, `observations_stored = null`, and a reason that names the missing key | Pass |
| Module status cannot overstate readiness | `test_system.py` asserts no module is `ready` after Phase 1 and only `settings` is `in_progress` | Pass |
| Source catalogue is complete and honest | 8 FIRMS products, all `not_ingested` | Pass |
| Migrations are reversible and dialect-portable | upgrade → downgrade → upgrade on SQLite; PostGIS statement guarded | Pass |
| Seed is idempotent (no duplicate sources) | seed twice, assert 8 rows | Pass |
| Secrets are not required to boot | API starts and `/ready` succeeds with an empty `FIRMS_MAP_KEY` | Pass |
| Request correlation | `X-Request-ID` echoed or generated, present in error bodies | Pass |
| UI reports empty state instead of mock statistics | `app.test.tsx` asserts "no fire activity to display" and the API-provided reason | Pass |

Totals: **23 backend tests, 7 frontend tests**, plus Ruff and mypy clean, and a strict TypeScript
build.

## Required before an analytical claim

| Validation | Criterion |
| --- | --- |
| Coordinate handling | Known fixtures map to the correct latitude/longitude; no axis swap; poles and antimeridian behave |
| Timestamp handling | `acq_date` + `acq_time` convert to UTC exactly; no local-time drift; day boundaries correct |
| Deduplication | Ingesting the same window twice yields identical row counts |
| Cross-sensor matching | Curated reference pairs: no automatic equivalence, precision/recall reported, rejected pairs explained |
| Calendar reconciliation | Σ daily cells = stored observation count for every metric; spot-check a day against raw records |
| FRP aggregation | Units in MW, aggregation labelled (sum vs maximum), no mixing of aggregate and peak |
| Missing data | A known-outage day is `no_data`, never `0` |
| Baselines | Recomputing from the same snapshot produces identical medians/MAD |
| Anomaly detection | Synthetic cases (spike, seasonal shift, flat baseline, tiny sample) classify as expected; zero MAD handled |
| Exposure distances | Geodesic distance matches an independent library within tolerance; antimeridian cases pass |
| Forecasts | Rolling-origin backtest beats the seasonal baseline before any forecast is surfaced |

## Fixtures

Synthetic fixtures are permitted for edge cases — duplicate rows, missing days, sensor outage,
extreme FRP, date-boundary errors — but must live in test directories only, be clearly labelled
synthetic, and never be reachable from a production data path or displayed as NASA observations.

## Known limitations

- No observations ingested: every statistical module is unimplemented, so no scientific result has
  been produced or claimed.
- SQLite in CI means spatial behaviour (PostGIS functions, GiST index performance) is not yet
  exercised; container-based PostgreSQL testing is required from Phase 2.
- MODIS/VIIRS brightness-temperature channels are not equivalent; any cross-sensor temperature
  comparison must be labelled as such or avoided.
- Hotspot counts are detections. Cloud cover suppresses detections; small or smouldering fires may
  be missed; industrial and agricultural heat appear as hotspots.

## Reporting

Once analytics exist, every report must carry: generation timestamp, geographic area, observation
period, data sources and processing versions, methodology, statistical limitations and the
observation identifiers behind each figure.
