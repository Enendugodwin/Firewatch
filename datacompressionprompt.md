# FIREWATCH X — Complete Data Architecture, Transient Processing, Compression, Analytics and Cloud Integration

## 1. PROJECT OBJECTIVE

Upgrade the existing FIREWATCH X application to create a scalable, storage-efficient and high-performance global fire intelligence platform using NASA MODIS and VIIRS hotspot observations.

The implementation must address five interconnected objectives:

1. Efficient data compression and long-term storage.
2. Automated transient data ingestion and processing.
3. High-performance harmonisation and analytical processing.
4. Fast geographical searches, historical calendars and anomaly detection.
5. Local-first development with optional Cloudflare R2 and PostgreSQL cloud deployment.

The existing database contains approximately 11.34 million hotspot observations, with substantial storage consumption from `fire_observations` and `raw_observations`.

The target initial cloud allocation is:

| Infrastructure | Capacity |
|---|---:|
| Cloudflare R2 | 25 GB |
| PostgreSQL | 1 GB |
| Local storage | Available local disk |
| Analytical engine | DuckDB |
| Processing | Python and Polars |

Do not rebuild the application unnecessarily. Inspect the existing FIREWATCH X repository, preserve its functional features and optimise the current implementation.

The final application must process large historical NASA datasets without loading the entire dataset into memory or requiring all observations to be stored in PostgreSQL.

---

# 2. TARGET ARCHITECTURE

Implement the following architecture:

NASA FIRMS
    |
    v
DATA AVAILABILITY CHECK
    |
    v
TRANSIENT INGESTION ENGINE
    |
    v
TEMPORARY RAW STORAGE
    |
    v
DATA VALIDATION
    |
    v
NORMALISATION
    |
    v
DEDUPLICATION
    |
    v
MODIS / VIIRS HARMONISATION
    |
    v
ANALYTICAL PROCESSING
    |
    +--------------------------+
    |                          |
    v                          v
HARMONIZED OBSERVATIONS    ANALYTICS ENGINE
    |                          |
    v                          v
PARQUET + ZSTD             STATISTICS / ANOMALIES
    |                          |
    v                          v
LOCAL STORAGE / R2         POSTGRESQL
    |                          |
    +------------+-------------+
                 |
                 v
          OUTPUT VERIFICATION
                 |
                 v
       DELETE TEMPORARY RAW DATA
                 |
                 v
          UPDATE MANIFESTS
                 |
                 v
             FIREWATCH X

DuckDB queries the retained Parquet observations.

PostgreSQL serves application metadata, precomputed statistics, calendar records, regional baselines and anomaly results.

FastAPI routes requests to the appropriate data source.

The frontend receives only the records and aggregates required for each interaction.

---

# WORKSTREAM 1 — TRANSIENT DATA INGESTION AND PROCESSING

## 3. IMPLEMENT AN AUTOMATED TRANSIENT INGESTION ENGINE

Build a dedicated ingestion and processing engine that downloads NASA FIRMS observations, processes them in controlled batches, saves the required outputs and deletes temporary raw downloads after successful verification.

Support:

- MODIS Terra.
- MODIS Aqua.
- VIIRS Suomi-NPP.
- VIIRS NOAA-20.
- VIIRS NOAA-21.

Support both historical ingestion and scheduled incremental ingestion.

The ingestion engine must not require the complete historical archive to be downloaded before processing begins.

Process observations in manageable source, date and geographical partitions.

## 4. PROCESSING LIFECYCLE

Every ingestion job must follow this lifecycle:

### Stage 1: Data availability discovery

Before downloading data:

1. Check NASA FIRMS product availability.
2. Identify the requested date range.
3. Identify available sensors and satellite products.
4. Identify missing or unavailable dates.
5. Create ingestion partitions.
6. Check whether the partition has already been successfully processed.
7. Skip previously completed partitions unless explicitly reprocessing.

Maintain the distinction between:

- Available data.
- Available data with zero observations.
- Missing data.
- Data not yet available.
- Failed requests.
- Incomplete processing.

Never interpret a missing day as zero fire activity.

### Stage 2: Temporary download

Download the selected NASA data into a dedicated temporary workspace.

Example:

```text
firewatch/
└── temporary/
    └── jobs/
        └── job_id/
            ├── source_manifest.json
            ├── modis.csv
            ├── viirs_snpp.csv
            ├── viirs_noaa20.csv
            ├── viirs_noaa21.csv
            └── processing.log
```

Requirements:

- Use bounded download batches.
- Validate download responses.
- Handle empty datasets.
- Handle rate limiting.
- Retry temporary failures.
- Preserve failed downloads for recovery.
- Prevent simultaneous jobs from overwriting each other's files.

Temporary data must never be accessible through the public frontend.

### Stage 3: Data validation

Validate the downloaded records before processing.

Check:

- File structure.
- Expected columns.
- Sensor and product identity.
- Latitude and longitude.
- Acquisition date and time.
- FRP values.
- Brightness measurements.
- Confidence fields.
- Satellite identifiers.
- Processing collection/version.
- Duplicate records.
- Malformed rows.

Record rejected rows and their rejection reasons.

Do not silently discard invalid observations.

### Stage 4: Normalisation

Convert source records into the FIREWATCH X canonical observation schema.

Preserve:

- Observation ID.
- Source ID.
- Source record ID.
- Source product.
- Sensor.
- Satellite.
- Latitude.
- Longitude.
- Acquisition timestamp in UTC.
- Original confidence.
- Confidence category.
- Brightness temperature.
- Brightness channel.
- FRP.
- Scan and track.
- Day/night.
- Processing version.
- Quality flags.
- Ingestion timestamp.
- Synthetic-data indicator.

Do not conflate MODIS and VIIRS confidence semantics or brightness channels.

### Stage 5: Deduplication

Implement idempotent deduplication.

Use the existing source fingerprint approach based on canonical source fields.

Maintain uniqueness at the appropriate source/product level.

Support re-ingestion of overlapping NASA windows without creating duplicate observations.

Record:

- Records received.
- Records inserted.
- Existing duplicates.
- Records rejected.
- Records changed by updated source collections.

If NASA provides corrected observations or new processing versions, support controlled replacement or versioned reprocessing rather than silently overwriting historical information.

---

# 5. MODIS / VIIRS HARMONISATION

Harmonisation must execute as part of the ingestion pipeline.

Implement the documented FIREWATCH X matching methodology.

Compare observations using:

- Spatial distance.
- Temporal difference.
- Observation footprint where available.
- Sensor characteristics.
- Observation quality.
- Spatial resolution.

Preserve original sensor-specific observations.

Create separate harmonization outputs.

Classify candidate associations as:

- Probable match.
- Possible match.
- Unmatched.
- Rejected.

Store:

- Observation A identifier.
- Observation B identifier.
- Temporal difference.
- Spatial distance.
- Footprint overlap where available.
- Association score.
- Matching components.
- Matching status.
- Algorithm version.

Do not interpret the association score as the probability that two detections represent the same physical fire unless independently calibrated.

Do not remove detections simply because they are geographically close.

## 5.1 Cross-day harmonisation

The processing engine must account for observations acquired near day boundaries.

Do not assume that independently processing each UTC day will always identify all relevant cross-sensor matches.

Implement configurable overlapping temporal windows for candidate matching.

For example, observations near the end of one day may need to be compared with observations from the beginning of the next day.

Support late-arriving observations and recalculation of affected matching partitions.

Historical event grouping must not be fragmented simply because processing was performed in daily batches.

---

# 6. ANALYTICS EXECUTION

After normalisation and harmonisation, execute the analytical pipeline.

Generate the following outputs.

### Daily analytics

- Global detection count.
- MODIS detection count.
- VIIRS detection count.
- Harmonized detection statistics.
- Country-level detections.
- Regional detections.
- Daily average FRP.
- Daily aggregate FRP.
- Confidence distribution.
- Day/night distribution.
- Sensor distribution.
- Data completeness.

### Monthly and yearly analytics

- Monthly detection trends.
- Annual detection trends.
- Seasonal activity.
- Year-over-year comparisons.
- Sensor-specific historical comparisons.
- Regional activity rankings.
- Historical FRP changes.

### Spatial analytics

- Daily H3 cell activity.
- Monthly H3 cell activity.
- Geographic hotspot density.
- Regional activity summaries.
- Spatial concentration changes.

### Intelligence analytics

- Historical anomalies.
- Seasonal anomalies.
- Spatial anomalies.
- Unusual FRP activity.
- Sensor-specific anomalies.

Do not calculate every analytical metric from scratch on every application request.

Use incremental aggregation and reusable analytical intermediate results.

---

# 7. ANOMALY DETECTION IN THE PROCESSING PIPELINE

Execute anomaly detection after the relevant daily and regional aggregates have been generated.

Use existing historical baselines.

Implement:

- Robust Z-score using MAD.
- Rolling historical comparisons.
- Seasonal baselines.
- Historical quantiles.
- FRP anomaly analysis.
- Spatial anomaly analysis.
- Optional Isolation Forest.

Each anomaly must contain:

- Region identifier.
- Analysis period.
- Metric.
- Observed value.
- Expected value.
- Historical baseline.
- Deviation score.
- Severity.
- Sample count.
- Data completeness.
- Detection method.
- Algorithm version.
- Supporting evidence.

Do not generate authoritative emergency claims from satellite detection statistics.

Anomaly results must be analytical indicators with explanatory evidence.

If the available historical baseline is insufficient, record the limitation instead of generating an unsupported anomaly.

Recalculate affected anomaly records when historical corrections or new observations change the relevant baseline.

---

# 8. DURABLE OUTPUT STORAGE

After processing, save the required information in the configured permanent storage destinations.

## 8.1 Harmonized observations

Store individual harmonized observations in Apache Parquet.

Use Zstandard compression.

Preserve all required canonical fields and original provenance.

## 8.2 Analytical records

Store compact analytical records in PostgreSQL.

Populate:

- daily_activity
- monthly_activity
- yearly_activity
- country_fire_statistics
- regional_fire_statistics
- cell_activity
- regional_baselines
- anomalies
- ingestion_runs
- ingestion_partitions
- source_availability
- dataset_catalog
- algorithm_runs

## 8.3 Harmonisation outputs

Store cross-sensor associations and event membership records in an efficient structure.

Keep compact metadata in PostgreSQL.

Use Parquet for larger matching or event-observation datasets if their growth makes relational storage unsuitable.

Preserve the existing observation identifiers.

## 8.4 Data manifests

For every processed partition, create a manifest containing:

- Dataset identifier.
- Original NASA source.
- Sensor and satellite.
- Source product.
- Observation date range.
- Geographical coverage.
- Input record count.
- Accepted record count.
- Rejected record count.
- Duplicate count.
- Harmonized record count.
- Output file locations.
- Output file sizes.
- Output SHA-256 checksums.
- Schema version.
- Harmonisation version.
- Analytics version.
- Processing start time.
- Processing completion time.
- Job status.

Manifests must allow FIREWATCH X to identify exactly which data has been processed.

---

# 9. MANDATORY VERIFICATION BEFORE RAW DATA DELETION

This is a critical requirement.

Temporary raw data must never be deleted merely because the processing script completed.

Before cleanup, verify:

1. Original download was completed and validated.
2. Normalisation completed successfully.
3. Harmonisation completed successfully or its permitted partial status is documented.
4. Expected output counts have been calculated.
5. Canonical observations were successfully written.
6. Durable Parquet files exist in the configured permanent storage.
7. Parquet file sizes and checksums are valid.
8. The Parquet files can be read back successfully.
9. PostgreSQL analytical transactions committed successfully.
10. Daily and regional aggregates reconcile to the processed observations.
11. Anomaly results were saved where the available baseline supports them.
12. Dataset manifests were successfully recorded.
13. Ingestion and algorithm versions were recorded.
14. The complete processing job is marked as committed.

Only after these requirements pass may the temporary raw downloads and intermediate files be deleted.

For Cloudflare R2, verify the remote object itself. Do not rely only on a successful upload response.

Where possible, verify SHA-256 by reading the uploaded object or using a verified object checksum. Do not assume the ETag is always a SHA-256 digest, particularly for multipart uploads.

Use staged outputs and write the final dataset manifest only after all required outputs have been verified.

If any critical verification fails:

- Preserve temporary raw files.
- Preserve intermediate outputs needed for recovery.
- Mark the job as failed or partially completed.
- Record the failure reason.
- Allow recovery and resumption.
- Avoid duplicate database records or Parquet files.

---

# 10. TRANSIENT STORAGE MANAGEMENT

Create a separate temporary storage manager.

Use an isolated directory for each job.

Support:

- Temporary download files.
- Extracted files.
- Normalised processing batches.
- Intermediate harmonisation outputs.
- Temporary DuckDB files.
- Temporary export files.

Delete successful intermediate files automatically.

Preserve failed-job workspaces until recovery or an administrator-approved cleanup.

Implement configurable temporary storage limits.

Do not allow multiple processing jobs to consume all available disk space.

Track:

- Temporary storage consumed.
- Number of active jobs.
- Number of failed jobs.
- Files awaiting cleanup.
- Temporary files older than the configured threshold.
- Storage reclaimed after cleanup.

Temporary data and permanent Parquet datasets must use different storage directories and permissions.

---

# 11. RAW DATA RETENTION MODES

Support two explicit raw-data retention policies.

### MODE A — TRANSIENT RAW PROCESSING

Default for cost-efficient ingestion.

- Download original NASA data temporarily.
- Validate and process it.
- Retain normalised and harmonized observation records.
- Retain processing provenance and manifests.
- Generate analytical outputs.
- Delete temporary raw downloads after verification.

This mode preserves the processed observation history but does not guarantee the ability to reconstruct the exact original NASA response.

### MODE B — HISTORICAL SOURCE ARCHIVAL

Optional for scientific reproducibility.

- Download NASA raw data temporarily.
- Process and harmonise it.
- Archive the original source files or equivalent original source rows in compressed storage.
- Verify the archive.
- Retain archive checksums and source metadata.
- Delete the temporary working copy only after archival verification.

Allow the administrator to select a mode globally or for specific source products.

Do not maintain duplicated JSONB raw payloads in PostgreSQL and Parquet.

---

# 12. FAILURE RECOVERY AND INCREMENTAL PROCESSING

Implement a persistent processing state machine.

Suggested states:

DISCOVERED
DOWNLOADING
VALIDATING
NORMALISING
DEDUPLICATING
HARMONISING
ANALYSING
WRITING_OUTPUTS
VERIFYING_OUTPUTS
COMMITTING
CLEANUP_PENDING
SUCCEEDED
FAILED
PARTIAL

Persist job state in PostgreSQL.

A worker restart must not cause an already completed batch to be downloaded and processed again unnecessarily.

Support:

- Checkpoints.
- Retries.
- Resume operations.
- Idempotent outputs.
- Failure logs.
- Partial completion.
- Reprocessing selected dates.
- Reprocessing selected sensors.
- Corrected NASA data.
- Algorithm version upgrades.

If one sensor product fails but another completes, record the partial state accurately. Do not mark the entire observation date as complete without explaining the missing source.

For cross-sensor matching, allow matching jobs to run after the required overlapping observation partitions become available.

---

# WORKSTREAM 2 — COMPRESSION AND DATA STORAGE

## 13. PARQUET COMPRESSION

Use Apache Parquet with Zstandard compression.

Start with ZSTD level 3.

Benchmark against Snappy and gzip-compressed CSV using representative real NASA data.

Measure:

- Original file size.
- Compressed file size.
- Compression ratio.
- Compression duration.
- Decompression duration.
- Query performance.
- Memory consumption.

Use appropriate types:

- Float64 for latitude and longitude.
- UTC timestamps.
- Nullable integers for numeric confidence fields.
- Float32 or Float64 for FRP and temperatures after precision validation.
- Dictionary encoding for repeated sensor, source, satellite and category fields.

Preserve scientifically relevant precision.

## 14. PARQUET ORGANISATION

Use the following general structure:

```text
firewatch-data/
│
├── observations/
│   ├── sensor=MODIS/
│   │   └── year=YYYY/month=MM/
│   └── sensor=VIIRS/
│       └── satellite=SNPP/year=YYYY/month=MM/
│
├── raw_archive/
│
├── harmonized/
│   └── year=YYYY/month=MM/
│
├── matches/
│
├── events/
│
├── analytics/
│   ├── daily/
│   ├── monthly/
│   ├── yearly/
│   ├── regional/
│   ├── country/
│   └── anomalies/
│
├── spatial/
│   ├── h3_daily/
│   ├── h3_monthly/
│   └── map_tiles/
│
└── manifests/
```

Avoid excessive small files.

Target Parquet files of approximately 128–512 MB where practical.

Start by benchmarking row groups of 100,000–250,000 records.

Use partition pruning and sorting by acquisition time and/or spatial identifier.

---

# WORKSTREAM 3 — POSTGRESQL AND DUCKDB

## 15. POSTGRESQL OPTIMISATION

The 1 GB production PostgreSQL database must contain:

- User accounts.
- Application configuration.
- Geographic metadata.
- Sensor metadata.
- Dataset manifests.
- Ingestion job records.
- Processing history.
- Daily statistics.
- Monthly statistics.
- Yearly statistics.
- Regional statistics.
- Historical baselines.
- Anomaly records.
- Compact harmonisation metadata.

Do not retain all individual hotspot observations in production PostgreSQL.

Investigate the current 11.34 million row duplication between `fire_observations` and `raw_observations`.

Migrate and verify the data before removing any redundant structures.

Optimise indexes, storage types and aggregation tables.

Use Alembic migrations and transactional upserts.

## 16. DUCKDB QUERY ENGINE

Use DuckDB for detailed observation queries against Parquet datasets.

Use Polars for efficient transformations and data preparation.

Implement:

- Date-range filtering.
- Sensor filtering.
- Satellite filtering.
- Geographical filtering.
- FRP filtering.
- Confidence filtering.
- Historical comparisons.
- Cross-sensor analysis.
- CSV exports.
- GeoJSON exports.

Use predicate pushdown, projection pushdown, partition pruning and controlled query concurrency.

Support local Parquet queries and remote R2 queries where supported.

Never download the entire R2 dataset merely to answer a small geographical query.

---

# WORKSTREAM 4 — ADVANCED ANALYTICS AND QUERY PERFORMANCE

## 17. INCREMENTAL HISTORICAL ANALYTICS

Implement precomputed analytics for:

- Global daily activity.
- Global monthly activity.
- Annual activity.
- Seasonal activity.
- Country activity.
- Regional activity.
- Sensor-specific activity.
- H3 spatial activity.
- Fire radiative power.
- Historical anomalies.

When new observations are processed, update only affected daily, monthly and spatial partitions.

Do not rebuild the entire historical calendar after every ingestion.

Distinguish zero detections from unavailable data.

Maintain separate MODIS and VIIRS figures and clearly labelled combined detection counts.

## 18. SPATIAL QUERY OPTIMISATION

Replace dependence on the existing 2-degree grid alone with hierarchical H3 spatial aggregation.

Maintain configurable spatial resolutions.

At low map zoom:

- Return spatial aggregate cells.
- Return detection counts and FRP summaries.
- Avoid returning every hotspot coordinate.

At medium zoom:

- Retrieve more detailed spatial activity.

At high zoom:

- Return individual observations from Parquet.

Use viewport-based requests, caching and request cancellation.

Do not load millions of hotspot coordinates into browser memory.

## 19. API QUERY ROUTING

Use FastAPI to route queries.

PostgreSQL handles:

- Dashboard.
- Historical calendar.
- Yearly comparisons.
- Regional summaries.
- Anomaly records.
- Historical baselines.
- Ingestion status.

DuckDB handles:

- Individual hotspot searches.
- Custom date and sensor filters.
- Detailed geographical queries.
- FRP filtering.
- Observation-level comparisons.
- CSV and GeoJSON exports.

Large exports and analyses must use background jobs.

Return a job identifier and expose processing status.

---

# WORKSTREAM 5 — LOCAL AND CLOUD INTEGRATION

## 20. LOCAL-FIRST ARCHITECTURE

Support three modes:

LOCAL:
All data processing and storage take place locally.

HYBRID:
Data is processed locally and selected datasets are synchronised to Cloudflare R2 and production PostgreSQL.

CLOUD:
The application and selected datasets are hosted online.

Use the same storage abstractions and query interfaces across all modes.

## 21. CLOUDFLARE R2

Implement the S3-compatible storage adapter.

Support:

- Uploads.
- Downloads.
- File metadata.
- Checksums.
- Multipart uploads.
- Resumable transfers.
- Dataset manifests.
- Storage monitoring.
- Selective synchronisation.

Never expose R2 credentials in the frontend.

Never delete local datasets automatically after synchronisation.

## 22. CLOUD SYNCHRONISATION

Build a Cloud Deployment Manager.

It must:

1. Scan local datasets.
2. Compare local manifests against cloud manifests.
3. Identify missing or changed files.
4. Calculate expected upload size.
5. Check available storage.
6. Allow selective dataset deployment.
7. Upload the selected datasets.
8. Verify uploaded objects.
9. Synchronise analytical database records.
10. Verify cloud availability.
11. Record deployment history.

If the 25 GB R2 allocation is insufficient, block the upload and explain the storage requirement.

---

# WORKSTREAM 6 — MONITORING AND ADMINISTRATION

## 23. DATA PIPELINE DASHBOARD

Create a dedicated dashboard showing:

- Active ingestion jobs.
- Current processing stage.
- Downloaded observations.
- Validated observations.
- Rejected observations.
- Duplicate observations.
- Harmonized observations.
- Generated anomalies.
- Parquet files generated.
- Processing speed.
- RAM consumption.
- CPU consumption.
- Temporary disk consumption.
- Successful cleanup operations.
- Failed processing jobs.
- Last successful ingestion.

Allow administrators to inspect each job and view its execution logs.

Provide controls to:

- Start historical ingestion.
- Start incremental ingestion.
- Retry failed jobs.
- Resume interrupted jobs.
- Reprocess selected partitions.
- Run harmonisation.
- Rebuild selected aggregates.
- Inspect and verify outputs.
- Manage temporary files.

## 24. STORAGE DASHBOARD

Display:

- Local dataset size.
- R2 usage.
- Remaining R2 capacity.
- PostgreSQL usage.
- Parquet compression ratio.
- Number of retained observations.
- Temporary storage.
- Files awaiting cleanup.
- Dataset growth.

Use configurable warnings at 70%, 85% and 95% capacity.

Never automatically delete permanent historical observations.

---

# WORKSTREAM 7 — VALIDATION AND TESTING

## 25. TRANSIENT PIPELINE TESTS

Test:

- NASA download success.
- Empty source responses.
- Invalid source responses.
- Validation failures.
- Duplicate observations.
- Partial downloads.
- Failed uploads.
- Database commit failures.
- Parquet corruption.
- Interrupted processing.
- Resumed processing.
- Temporary file cleanup.
- Cross-day harmonisation.
- Late-arriving observations.
- Reprocessing after methodology changes.

Explicitly test that raw data is never deleted before durable outputs and metadata are verified.

## 26. STORAGE AND QUERY TESTS

Test:

- ZSTD compression.
- Parquet read/write accuracy.
- Local storage.
- R2 storage.
- DuckDB date queries.
- Spatial queries.
- H3 aggregation.
- PostgreSQL aggregation.
- Large CSV exports.
- Historical calendar generation.

## 27. SCIENTIFIC VALIDATION

Ensure:

- MODIS/VIIRS sensor identity is preserved.
- Confidence values are correctly interpreted.
- FRP units are preserved.
- Coordinates and UTC timestamps are correct.
- Observation IDs and source fingerprints remain consistent.
- Duplicate records are not counted twice.
- Zero observations are distinguishable from unavailable data.
- Harmonisation results are reproducible.
- Anomaly outputs expose their baselines and evidence.
- All synthetic records remain explicitly labelled.

---

# WORKSTREAM 8 — SAFE MIGRATION

## 28. MIGRATE THE EXISTING 11.34 MILLION OBSERVATIONS

Migration must be staged.

1. Back up PostgreSQL.
2. Profile actual table and index sizes.
3. Select one representative month of data.
4. Export the month into Parquet.
5. Benchmark compression and queries.
6. Validate every record and important measurement.
7. Test the complete transient processing lifecycle.
8. Migrate the remaining observation partitions in batches.
9. Switch the application query layer to DuckDB.
10. Validate historical calendars, maps and exports.
11. Retire redundant PostgreSQL payloads and tables only after acceptance testing.

Preserve observation UUIDs and source fingerprints.

Do not attempt to migrate all records in one massive RAM-consuming operation.

---

# WORKSTREAM 9 — PERFORMANCE BENCHMARKS

## 29. REQUIRED MEASUREMENTS

Benchmark the original and new architecture using representative real datasets.

Test at 100,000, 1 million and 10 million observations where feasible.

Report:

- Original PostgreSQL storage.
- New Parquet storage.
- Compression ratio.
- Temporary storage peak.
- RAM peak.
- Processing records per second.
- Harmonisation duration.
- Analytics duration.
- Query response times.
- Calendar response time.
- Geographic query response time.
- CSV export duration.
- Cleanup duration.
- R2 storage consumption.

Do not invent performance measurements.

Use benchmarks to select optimal batch sizes, compression levels, file sizes, row groups, worker counts and DuckDB memory limits.

---

# WORKSTREAM 10 — IMPLEMENTATION ORDER

Execute implementation in the following sequence.

### Phase 1 — Existing system assessment
Inspect the repository, current schema, storage usage, queries and processing pipeline.

### Phase 2 — Transient ingestion foundation
Implement temporary workspaces, job states, checkpoints, validation and recovery.

### Phase 3 — Processing and harmonisation
Implement normalisation, deduplication and cross-sensor matching.

### Phase 4 — Permanent output storage
Implement Parquet generation, compression, manifests and output verification.

### Phase 5 — Analytics generation and PostgreSQL population
Generate statistics, anomalies, baselines and spatial summaries.

### Phase 6 — Safe cleanup
Implement deletion of temporary raw downloads only after all mandatory verification succeeds.

### Phase 7 — DuckDB and Polars optimisation
Implement efficient detailed queries and high-performance transformations.

### Phase 8 — PostgreSQL optimisation
Move detailed observations out of PostgreSQL and retain compact analytical tables.

### Phase 9 — Map and API optimisation
Implement H3, spatial aggregation, query routing and caching.

### Phase 10 — Local/cloud storage abstraction
Implement local filesystem and Cloudflare R2 adapters.

### Phase 11 — Cloud synchronisation
Implement selective data transfers, checksums, deployment manifests and recovery.

### Phase 12 — Migration and validation
Migrate all existing observations in controlled batches and validate all output.

### Phase 13 — Documentation and deployment
Complete deployment instructions, testing and operational documentation.

Do not skip stages or delete data to make development easier.

---

# 30. FINAL ACCEPTANCE CRITERIA

The final implementation must demonstrate that:

1. FIREWATCH X operates entirely locally.
2. NASA FIRMS data is ingested in manageable batches.
3. Raw downloads are stored temporarily.
4. Data validation and normalisation are performed automatically.
5. MODIS and VIIRS are harmonised while preserving provenance.
6. Analytics and anomalies are generated automatically.
7. Harmonized observations are saved in compressed Parquet.
8. PostgreSQL is populated with compact analytical results.
9. Parquet outputs and database records are verified.
10. Temporary raw downloads are deleted only after successful verification.
11. Failed processing jobs preserve their source files and can resume.
12. Duplicate records are prevented.
13. Cross-day harmonisation is supported.
14. Historical calendar calculations are incremental.
15. DuckDB can query detailed observations efficiently.
16. The global map uses spatial aggregation at appropriate zoom levels.
17. Cloudflare R2 synchronisation is selective and resumable.
18. Production PostgreSQL stores metadata and precomputed statistics, not the complete observation archive.
19. The application remains compatible with the initial 25 GB R2 and 1 GB PostgreSQL allocations for the selected cloud dataset.
20. Data integrity and scientific correctness are verified using actual NASA observations.

---

# 31. FINAL DELIVERY

At completion, provide:

- Architecture assessment.
- Revised data flow.
- Updated database schema.
- Transient ingestion implementation.
- Job-state and recovery implementation.
- Data validation and harmonisation implementation.
- Parquet compression benchmark.
- Storage migration report.
- DuckDB query implementation.
- Polars processing implementation.
- PostgreSQL optimisation.
- Calendar and anomaly optimisation.
- H3 spatial analysis.
- Cloudflare R2 integration.
- Synchronisation manager.
- Storage and pipeline dashboards.
- Automated test results.
- Before-and-after performance benchmarks.
- Deployment documentation.
- Known limitations.

Do not stop at a plan, diagram or mockup.

Implement working functionality, connect the services, run migrations, execute tests and validate the pipeline with real NASA FIRMS observations.

The final deliverable must be a fully functional, locally operable, cloud-ready FIREWATCH X platform capable of processing extensive MODIS and VIIRS historical data while minimising persistent raw storage, PostgreSQL consumption, processing overhead and analytical query latency.