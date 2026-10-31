# Synthetic fixture — NOT NASA DATA

These CSVs are hand-written to exercise the pipeline: two cross-sensor clusters,
one isolated low-confidence detection, one non-vegetation thermal anomaly
(FIRMS `type=2`, other static land) and a spread of confidence values.

They are loaded only by `scripts/ingest_fixture.py`, are stored with
`is_synthetic = true`, and are surfaced in the UI behind a "DEMO DATA" banner.
They must never be presented as observed fire activity.
