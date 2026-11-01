# FIREWATCH X — Cloud Integration Preparation, Data Analysis and Performance Optimisation

## PROJECT OBJECTIVE

Upgrade the existing FIREWATCH X application in two major areas:

**WORKSTREAM 1: CLOUD INTEGRATION PREPARATION**

Prepare the application for deployment using Cloudflare R2 (initial allocation: 25 GB) and PostgreSQL (initial allocation: 1 GB), while retaining the ability to operate entirely on a local computer.

The application must support local, hybrid and cloud deployment configurations without requiring major code changes between environments.

**WORKSTREAM 2: ADVANCED DATA ANALYSIS AND HIGH-PERFORMANCE PROCESSING**

Redesign and optimise the NASA FIRMS ingestion, MODIS/VIIRS harmonisation, data analysis, historical calendar and anomaly detection pipelines.

The objective is to process extensive historical datasets efficiently, minimise memory and storage consumption, improve analytical speed and make the application responsive even when working with millions of hotspot observations.

Do not build a new application from scratch. Inspect and improve the existing FIREWATCH X codebase while preserving all working features.

---

# WORKSTREAM 1: CLOUD INTEGRATION PREPARATION

## 1. Architecture and environment separation

Implement a cloud-ready architecture with three operational modes.

### LOCAL MODE

The entire application operates on the user's computer.

- Local PostgreSQL.
- Local Parquet data storage.
- Local DuckDB analytical engine.
- Local processing workers.
- Local FastAPI backend.
- Local React frontend.
- No requirement for Cloudflare credentials.

Historical data ingestion, harmonisation and analytics must work locally.

### HYBRID MODE

The application supports a combination of local processing and cloud infrastructure.

- Large historical datasets can remain local.
- Selected datasets can be uploaded to Cloudflare R2.
- Analytical summaries can be synchronised to cloud PostgreSQL.
- New observations can be processed locally or remotely.
- The application can access locally retained and cloud-hosted datasets through a common data access layer.

### CLOUD MODE

The application operates online.

- Cloudflare R2 stores selected raw, processed and harmonized datasets.
- Production PostgreSQL stores application records and analytical summaries.
- Backend API runs on a persistent hosting service.
- Background workers execute scheduled ingestion and processing.
- Frontend is deployed separately.
- Users can access the platform through the public application.

Switching between modes must be controlled through configuration, not hardcoded application logic.

## 2. Storage abstraction layer

Create a unified storage interface so that application services do not depend directly on a particular storage provider.

Implement the following storage providers:

- Local filesystem storage.
- S3-compatible object storage.
- Cloudflare R2 storage.

Required operations:

- Upload file.
- Download file.
- Delete file.
- Check whether a file exists.
- Retrieve file metadata.
- Calculate available storage where supported.
- List datasets.
- Verify checksums.
- Generate temporary signed download URLs.

Use an adapter pattern.

Example:

```python
class StorageProvider:
    def upload(self, source, destination):
        raise NotImplementedError

    def download(self, source, destination):
        raise NotImplementedError

    def exists(self, path):
        raise NotImplementedError

    def delete(self, path):
        raise NotImplementedError

    def get_metadata(self, path):
        raise NotImplementedError

    def calculate_checksum(self, path):
        raise NotImplementedError
```

Implement separate local and R2 adapters.

The rest of the application must interact with the storage interface rather than directly calling provider-specific SDKs.

## 3. Cloudflare R2 preparation

Prepare Cloudflare R2 integration using its S3-compatible API.

Environment variables:

```env
STORAGE_MODE=local

R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=

DATABASE_MODE=local
LOCAL_DATA_DIRECTORY=./data
DATABASE_URL=
CLOUD_DATABASE_URL=
```

Credentials must remain server-side.

Implement connection testing and configuration validation.

The application must work normally when R2 credentials are absent and `STORAGE_MODE=local`.

Do not require cloud access merely to start the application.

## 4. Dataset organisation

Standardise local and cloud dataset structures.

```text
firewatch-data/
│
├── raw/
│   ├── modis/
│   ├── viirs_snpp/
│   ├── viirs_noaa20/
│   └── viirs_noaa21/
│
├── harmonized/
│   ├── year=YYYY/
│   │   └── month=MM/
│
├── analytics/
│   ├── global/
│   ├── country/
│   ├── regional/
│   ├── daily/
│   ├── monthly/
│   ├── yearly/
│   └── anomalies/
│
├── manifests/
│
├── exports/
│
└── temporary/
```

Use Parquet with Zstandard compression for large analytical datasets.

Partition datasets by sensor, year and month where appropriate.

Avoid excessive partitioning that creates thousands of tiny files.

Consolidate small files into larger analytical files when practical.

## 5. Cloud synchronisation manager

Develop a dedicated Cloud Synchronisation Manager.

It must compare local datasets against cloud datasets and identify:

- Files available locally but missing in R2.
- Files already synchronised.
- Files with modified contents.
- Files with different checksums.
- Files requiring replacement.
- Files selected for deployment.

Generate a deployment manifest containing:

- Dataset identifier.
- Original source.
- Sensor.
- Date coverage.
- Partition information.
- Record count.
- File size.
- SHA-256 checksum.
- Schema version.
- Processing version.
- Local storage location.
- Cloud object location.
- Synchronisation status.

Support:

1. Scan local datasets.
2. Preview deployment.
3. Select datasets.
4. Calculate expected upload size.
5. Check remaining cloud capacity.
6. Upload selected datasets.
7. Resume failed uploads.
8. Verify uploaded objects.
9. Update cloud metadata.
10. Generate a synchronisation report.

Implement multipart uploads for large files where appropriate.

Synchronisation must be idempotent.

Never assume that an upload succeeded merely because an upload request returned without an exception. Verify the remote object and its expected size and checksum.

Never delete local datasets after synchronisation.

## 6. PostgreSQL cloud preparation

Support separate local and production database connections.

Use SQLAlchemy and Alembic migrations.

Implement:

- Environment-specific connection configuration.
- Connection pooling.
- Database migration execution.
- Schema version tracking.
- Batch imports.
- Transactional upserts.
- Duplicate prevention.
- Data integrity checks.

PostgreSQL must primarily contain:

- User and authentication records.
- Geographic region metadata.
- Sensor metadata.
- Dataset manifests.
- Processing history.
- Ingestion job records.
- Harmonisation metadata.
- Daily statistics.
- Monthly statistics.
- Yearly statistics.
- Regional statistics.
- Historical baselines.
- Anomaly records.
- Application settings.

Do not transfer millions of individual hotspot observations into PostgreSQL.

Detailed hotspot observations should remain in Parquet storage.

Optimise the production schema for the initial 1 GB allocation.

## 7. Cloud deployment readiness dashboard

Create a new section:

**Infrastructure → Cloud Readiness**

Display:

- Current deployment mode.
- Local storage usage.
- R2 storage consumption.
- R2 remaining capacity.
- Local database size.
- Production database size.
- Pending files.
- Files already uploaded.
- Failed synchronisation jobs.
- Number of records awaiting transfer.
- Estimated deployment size.
- Last successful synchronisation.

Create actions:

- Test R2 connection.
- Test PostgreSQL connection.
- Scan local datasets.
- Preview cloud deployment.
- Select datasets.
- Synchronise datasets.
- Synchronise database.
- Verify deployment.
- View deployment history.

Warn before any operation that might exceed the allocated storage.

Do not automatically delete historical records to create storage space.

---

# WORKSTREAM 2: DATA ANALYSIS AND HIGH-PERFORMANCE PROCESSING

## 8. Audit and benchmark the existing processing engine

Before changing the analytical implementation, inspect the existing pipeline.

Identify:

- Slow ingestion operations.
- Repeated downloads.
- Unnecessary data transformations.
- Full-dataset reads.
- Excessive memory consumption.
- Repeated database queries.
- Repeated calculations.
- Inefficient Parquet partitioning.
- Duplicate records.
- Slow map queries.
- Slow calendar generation.
- Inefficient anomaly detection.

Create a performance baseline.

Measure:

- Records processed per second.
- Processing duration per day of data.
- Peak RAM consumption.
- CPU utilisation.
- Temporary disk usage.
- Parquet file size.
- Analytics query duration.
- Database query duration.
- API response time.

Implement measurable improvements and record before-and-after results.

Do not invent performance improvements or report unmeasured benchmark results.

## 9. High-performance ingestion engine

Redesign the ingestion engine to process NASA FIRMS data in manageable batches.

Support:

- MODIS Terra.
- MODIS Aqua.
- VIIRS Suomi-NPP.
- VIIRS NOAA-20.
- VIIRS NOAA-21.

Implement the following capabilities:

### Incremental ingestion

Only retrieve new or previously unavailable observations.

Avoid repeatedly downloading historical data.

Track ingestion checkpoints by sensor, date and product.

### Parallel processing

Support controlled parallel processing of independent date and sensor partitions.

Use configurable worker counts.

Avoid launching more parallel tasks than available CPU and memory resources can safely support.

### Streaming and chunked processing

Never load the complete historical dataset into RAM.

Use Polars lazy and streaming operations where supported.

Read only the required columns.

Process large files in manageable batches.

### Failure recovery

Maintain checkpoints.

Allow failed batches to resume.

Use idempotent writes.

Prevent duplicate ingestion after interrupted operations.

### Temporary data management

Download raw NASA files into temporary storage.

After successful processing:

1. Validate downloaded data.
2. Normalise the schema.
3. Harmonise observations.
4. Generate analytical outputs.
5. Save harmonized Parquet files.
6. Upload outputs to the configured storage provider.
7. Verify file integrity.
8. Commit analytical database records.
9. Record processing metadata.
10. Delete temporary raw files.

If any critical stage fails, retain the temporary data and allow processing to resume.

---

## 10. Data processing and analytical engine

Use an optimised combination of:

- Python.
- Polars.
- DuckDB.
- NumPy.
- SciPy.
- GeoPandas.
- Shapely.
- PyProj.

Use Polars for efficient transformations and columnar data processing.

Use DuckDB for analytical SQL queries against partitioned Parquet datasets.

Use GeoPandas and spatial libraries only when spatial operations require them.

Avoid converting large Polars or DuckDB datasets unnecessarily into Pandas DataFrames.

Apply:

- Predicate pushdown.
- Projection pushdown.
- Partition pruning.
- Lazy execution.
- Batch processing.
- Efficient data types.
- Reusable analytical intermediate results.
- Query result caching.

Ensure the engine can analyse selected remote Parquet partitions without downloading the entire dataset.

Use local temporary copies only where necessary.

Manage query concurrency and temporary storage.

## 11. MODIS and VIIRS harmonisation improvements

Preserve the scientific methodology.

The objective is to create a consistent analytical time series without hiding the sensor of origin.

Maintain both original and harmonized representations.

For every observation, preserve:

- Observation identifier.
- Original sensor.
- Satellite platform.
- Acquisition date and time.
- Latitude and longitude.
- Original confidence value.
- Confidence category.
- Brightness temperature.
- Fire radiative power.
- Scan and track dimensions where available.
- Spatial resolution.
- Processing collection/version.
- Data quality flags.

Implement cross-sensor association using configurable spatial and temporal criteria.

Record:

- Matched observations.
- Possible matches.
- Unmatched observations.
- Rejected candidate matches.
- Matching score.
- Distance.
- Time difference.
- Methodology version.

Do not treat a matching score as a statistical probability unless the model has been independently calibrated.

Do not automatically remove detections solely because they are geographically close.

Preserve raw sensor-specific counts and harmonized analytical counts separately.

Implement reproducible harmonisation runs.

## 12. Historical burning activity calendar optimisation

The calendar must not calculate its historical results from millions of individual detections on every page load.

Create a precomputation engine.

Generate:

- Daily statistics.
- Monthly statistics.
- Yearly statistics.
- Seasonal statistics.
- Country-level statistics.
- Regional statistics.
- Sensor-specific statistics.
- Harmonized activity statistics.

The calendar must support the historical period from the earliest available MODIS observations to the present, subject to actual dataset coverage.

When new observations arrive, update only the affected aggregation partitions.

Do not rebuild every historical year for each incremental ingestion.

Provide the following calendar metrics as independent selectable views:

1. Raw MODIS detections.
2. Raw VIIRS detections.
3. Combined raw detections.
4. Harmonized detection statistics.
5. Estimated fire-event statistics, where the event-grouping methodology supports them.
6. Aggregate fire radiative power.

Clearly explain that hotspot observations are satellite detections, not necessarily unique fires.

Distinguish zero detections from unavailable, incomplete or failed data.

## 13. Advanced anomaly detection engine

Implement an advanced anomaly analysis module.

Support:

### Temporal anomalies

Identify unusual increases and decreases in regional hotspot activity.

### Seasonal anomalies

Compare observations with appropriate historical seasonal baselines.

### Spatial anomalies

Identify unusual concentrations of activity in geographical grid cells or regions.

### Fire radiative power anomalies

Identify unusual changes in FRP relative to historical observations.

### Sensor anomalies

Identify differences that might result from sensor availability, acquisition patterns or detection characteristics.

Use appropriate methods such as:

- Median and median absolute deviation.
- Robust Z-scores.
- Seasonal baselines.
- Rolling windows.
- Quantile thresholds.
- Isolation Forest as an optional supplementary method.

Use adequate historical samples before declaring an anomaly.

Handle zero MAD and insufficient baseline data.

Each anomaly record must contain:

- Region.
- Observation period.
- Metric.
- Observed value.
- Expected baseline.
- Deviation.
- Severity.
- Number of baseline observations.
- Data completeness.
- Detection method.
- Algorithm version.
- Supporting evidence.
- Explanation.

Do not label every increase in hotspot activity an emergency.

Present anomalies as analytical indicators requiring interpretation.

## 14. Advanced geographical analytics

Optimise geographical analysis for global datasets.

Implement:

- Geographic bounding-box filtering.
- Country and administrative-region filtering.
- Spatial grid aggregation.
- Regional hotspot density.
- Geographic clustering.
- Historical spatial comparisons.
- Nearby hotspot searches.
- Geographic heatmaps.

Use spatial indexing, bounding-box pre-filtering and appropriate coordinate reference systems.

Consider H3 or an equivalent hierarchical spatial grid for fast regional aggregation.

Retain original hotspot coordinates for detailed exploration.

Do not use spatial simplification in a way that destroys scientific observation accuracy.

## 15. Optimise the interactive map

The global fire map must not load every hotspot observation into browser memory.

Implement:

- Viewport-based API queries.
- Server-side geographic filtering.
- Zoom-dependent aggregation.
- Hotspot clustering.
- Heatmap layers.
- Spatial grid summaries.
- Vector tiles where appropriate.
- Lazy loading.
- Request cancellation when the map viewport changes.
- Caching of frequently requested geographic areas.

At low zoom levels, show aggregated activity.

At higher zoom levels, show individual hotspot observations.

Only retrieve full observation details when the user selects an individual detection.

Maintain MODIS/VIIRS filters and observation provenance.

## 16. Optimise API performance

Review and optimise existing FastAPI endpoints.

Implement:

- Pagination.
- Date and geographical filtering.
- Efficient SQL queries.
- Asynchronous I/O where beneficial.
- Connection pooling.
- Result caching.
- Query timeouts.
- Request validation.
- Background report generation.
- Appropriate response compression.

Use precomputed aggregates for dashboards and calendars.

Do not run large historical analytical queries synchronously inside normal frontend requests.

For expensive jobs, return a job identifier and expose processing status.

## 17. Caching and analytical result reuse

Introduce a caching strategy for repeated requests.

Cache:

- Global dashboard summaries.
- Country activity summaries.
- Regional activity summaries.
- Monthly calendars.
- Yearly comparisons.
- Popular geographic map queries.
- Repeated anomaly summaries.

Invalidate or update relevant cache entries when new data changes the underlying analytical results.

Include dataset version and query parameters in cache keys where needed.

Avoid serving stale statistics without identifying their data freshness.

---

# 18. RESOURCE OPTIMISATION

The system must be configured for a resource-constrained local development environment.

Use conservative defaults for worker count, memory and concurrency.

Provide configurable:

- Maximum worker processes.
- Batch size.
- Maximum memory budget.
- DuckDB threads.
- Query concurrency.
- Temporary storage directory.
- Cache size.
- Processing timeouts.

Support processing without requiring the entire historical dataset in RAM.

Avoid loading large files simultaneously into multiple processing workers.

Monitor CPU, RAM and disk utilisation.

Automatically reduce processing concurrency when resource limits are approached.

The system must remain usable while background ingestion and analytics execute.

---

# 19. DATA QUALITY, SCIENTIFIC VALIDATION AND TRACEABILITY

Optimisation must never compromise scientific accuracy.

Implement validation for:

- Coordinates.
- Timestamps.
- Duplicate observations.
- Sensor identity.
- Confidence classification.
- FRP units.
- Spatial resolution.
- Missing dates.
- Missing products.
- Incomplete ingestion.
- Aggregation accuracy.
- Harmonisation consistency.

For each analytical output, preserve:

- Input dataset identifiers.
- Processing date.
- Sensor sources.
- Data coverage.
- Algorithm version.
- Methodology version.
- Record count.

Maintain the distinction between:

- No detected hotspots.
- No data available.
- Incomplete data.
- Processing failure.
- Data not yet published.

Recalculate analytical outputs when corrections or updated source collections require it.

---

# 20. ADMINISTRATIVE PERFORMANCE DASHBOARD

Create a dedicated dashboard showing:

### Processing performance
- Total records processed.
- Processing speed.
- Jobs running.
- Jobs completed.
- Failed jobs.
- Average processing time.
- Peak RAM usage.
- CPU utilisation.

### Analytics
- Daily aggregates generated.
- Monthly aggregates generated.
- Yearly aggregates generated.
- Anomalies identified.
- Regions analysed.
- Harmonisation runs completed.

### Data infrastructure
- Local storage usage.
- Cloud storage usage.
- PostgreSQL usage.
- Parquet file count.
- Total retained observations.
- Temporary files pending deletion.
- Dataset synchronisation status.

Allow administrators to inspect processing jobs and their execution logs.

---

# 21. TESTING AND BENCHMARKING

Create automated tests for both workstreams.

### Cloud integration
- Local storage adapter.
- R2 adapter.
- R2 uploads and downloads.
- Checksum verification.
- Synchronisation manifests.
- Resumable uploads.
- Storage capacity checks.
- Database synchronisation.

### Processing performance
- Large file processing.
- Streaming operations.
- Parallel partition processing.
- Memory consumption.
- DuckDB query performance.
- Polars processing performance.
- Incremental aggregation.

### Analytics
- Calendar accuracy.
- Regional aggregates.
- Seasonal analysis.
- Anomaly detection.
- FRP aggregation.
- Sensor comparisons.
- Harmonisation correctness.

### Frontend
- Cloud readiness dashboard.
- Storage dashboard.
- Processing dashboard.
- Historical calendar.
- Map interactions.
- Regional analytics.
- Anomaly inspection.

Use representative synthetic fixtures for automated tests, clearly labelled as synthetic. Use real NASA FIRMS datasets for scientific validation.

Run benchmarks at several dataset sizes, such as 100,000, 1 million and 10 million observations where hardware and available data permit.

Report actual measurements rather than promising arbitrary performance numbers.

---

# 22. IMPLEMENTATION PHASES

Execute both workstreams in this order.

**Phase 1 — Codebase and performance assessment**

Inspect the existing code, architecture, ingestion pipeline, database usage and performance bottlenecks.

Produce an implementation plan and baseline measurements.

**Phase 2 — Storage and deployment abstraction**

Implement local filesystem storage, R2 adapter, configuration profiles and database separation.

**Phase 3 — Cloud synchronisation preparation**

Implement manifests, checksums, dataset inventory, deployment preview and resumable transfers.

**Phase 4 — Processing engine optimisation**

Improve batch processing, Polars transformations, DuckDB queries, memory management and incremental ingestion.

**Phase 5 — Harmonisation optimisation**

Improve MODIS/VIIRS matching, provenance, quality checks and reproducibility.

**Phase 6 — Analytical engine**

Implement precomputed statistics, historical calendar optimisation, anomaly detection and regional analysis.

**Phase 7 — API and map optimisation**

Implement efficient endpoints, caching, viewport filtering and aggregated map rendering.

**Phase 8 — Administrative dashboards**

Create cloud readiness, storage monitoring and processing performance interfaces.

**Phase 9 — Testing and scientific validation**

Run integration, load, data integrity and analytical accuracy tests.

**Phase 10 — Documentation and deployment preparation**

Complete deployment configurations, documentation and local-to-cloud migration instructions.

Do not proceed past a critical failure in an earlier phase.

---

# 23. FINAL ACCEPTANCE CRITERIA

The implementation is complete only when:

1. FIREWATCH X runs locally without cloud credentials.
2. The application is ready to integrate with Cloudflare R2.
3. Local and cloud storage use the same storage interface.
4. Local datasets can be selectively synchronised to the cloud.
5. Cloud uploads are verified and resumable.
6. Local and production PostgreSQL databases remain separate.
7. Large historical datasets can be processed in batches.
8. Processing does not require loading the complete dataset into RAM.
9. Polars and DuckDB are used efficiently for their respective workloads.
10. MODIS and VIIRS provenance is retained.
11. Harmonisation is reproducible.
12. The historical calendar is driven by precomputed statistics.
13. Incremental ingestion updates only affected analytical partitions.
14. Anomaly detection uses documented historical baselines.
15. The global map does not load the complete dataset into the browser.
16. The backend uses efficient queries and caching.
17. Processing failures can resume without data duplication.
18. Temporary raw data is deleted only after successful output verification.
19. Storage and processing utilisation are visible in the application.
20. All changes pass automated tests and scientific validation.

# 24. FINAL DELIVERY REPORT

At completion, provide:

- Existing architecture assessment.
- New cloud-ready architecture.
- Updated repository structure.
- Storage abstraction implementation.
- Cloudflare R2 configuration instructions.
- PostgreSQL configuration instructions.
- Cloud synchronisation instructions.
- DuckDB and Polars optimisation details.
- Updated ingestion and harmonisation workflows.
- Updated analytics and anomaly detection methods.
- Performance benchmarks before and after optimisation.
- RAM and disk consumption measurements.
- Test results.
- Known limitations.
- Local execution instructions.
- Cloud deployment preparation instructions.

Do not stop at documentation or mockups.

Implement the actual functionality, connect the frontend to the backend, run migrations, execute tests and verify real data processing.

The final deliverable must be a fully functional, locally operable, cloud-ready and performance-optimised FIREWATCH X platform.