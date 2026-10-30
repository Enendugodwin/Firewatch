# FIREWATCH X — Complete End-to-End Development Specification

[NASA SVS | Worldview: Active fires detected by Suomi NPP satellite](https://images.openai.com/static-rsc-4/Ij65k5Dwp6thAraGAmHGjDyEoLu8QHpf9aNoNuQjdEzkfQwwRlBB4y-EBKvYlNkmjh0slv1dW2MB8Hb5XErFkDZzovanpqDhzEpJTFdxDpOkUsViO4id6YGEGDRcCchjdFjg1lYKfDrYTdflRZiK27VswR_fUzmBhnL5FbW52co?purpose=inline)

[svs.gsfc.nasa.gov](https://svs.gsfc.nasa.gov/5263/?utm_source=chatgpt.com)

Full platform

Global coverage

Advanced intelligence

Product: FIREWATCH X

Mission: Global Fire Intelligence, Historical Analysis and Early Warning Platform.

Core proposition: Transform satellite fire detections into an accessible, scientifically defensible global intelligence system that helps people understand where fires are occurring, how activity changes over time, which patterns are unusual, and which communities or assets may be geographically exposed.

This specification is designed to be given to an AI coding agent or development team to build the application from an empty repository through to deployment.

## 1. Product vision and objectives

FIREWATCH X must be a functional geospatial intelligence platform, not a static dashboard or a mockup.

The system must integrate genuine NASA satellite observations, process historical and near-real-time data, harmonize MODIS and VIIRS observations, and provide analytical capabilities.

### Primary objectives

1. Monitor active-fire detections globally.
2. Harmonize MODIS and VIIRS datasets.
3. Build an interactive historical burning activity calendar.
4. Identify unusual fire activity relative to historical baselines.
5. Provide regional and global fire statistics.
6. Assess the proximity of fires to communities and infrastructure.
7. Provide AI-assisted interpretation of scientific results.
8. Generate downloadable fire intelligence reports.
9. Allow users to investigate historical fire events.
10. Support future expansion into environmental monitoring and emergency intelligence.

### Core design principle

Every important analytical result must be traceable to its original satellite observations.

The system must distinguish:

- Satellite thermal detections.
- Probable cross-sensor matches.
- Individual fire observations.
- Estimated fire events.
- Confirmed wildfire information, when supplied by a verified external source.

Never present a hotspot count as the number of separate fires.

## 2. Application modules

The application will have ten primary modules.

| Module                | Main responsibility                        |
| --------------------- | ------------------------------------------ |
| Global Overview       | Global fire activity and intelligence      |
| Live Fire Map         | Interactive global hotspot monitoring      |
| Burning Calendar      | Historical activity by day, month and year |
| Fire Analytics        | Trends, comparisons and statistics         |
| Sensor Intelligence   | MODIS–VIIRS harmonization                  |
| Anomaly Detection     | Unusual activity identification            |
| Regional Intelligence | Geographic and environmental analysis      |
| Exposure Analysis     | Proximity to population and infrastructure |
| Intelligence Reports  | Automated analytical reporting             |
| AI Assistant          | Natural-language investigation             |

### Module 1 — Global Overview

[NASA SVS | Wildland Fires Dashboard](https://images.openai.com/static-rsc-4/JE8h7yLh5BBg9Xw24c4HUNrXG4Igkihh5JsCP6IUU5Kp1pgnVcNeLF4_VjqqU_k9vEG8L9OGDnhRsGLbJVE-dUWeNVVcRH2zIA8K9UNd5bg3Ye2UDfuL-W5fvntwcgyZ_fJBrqcU9qzoUHso20I0SCLkBtyvPQKC6jQk-zL1rz8?purpose=inline)

[svs.gsfc.nasa.gov](https://svs.gsfc.nasa.gov/gallery/wildland-fires/?utm_source=chatgpt.com)

The landing page should provide an immediate global picture.

Information displayed:

- Total satellite detections for the selected period.
- MODIS detection count.
- VIIRS detection count.
- Number of probable cross-sensor matches.
- Number of regions experiencing elevated activity.
- Daily detection trend.
- Global fire activity heatmap.
- Highest-activity countries and regions.
- Historical activity comparison.
- Recent data ingestion status.

Every statistic must be calculated from the underlying dataset and have a clear time range and source.

Include a date selector, sensor selector, geographic selector and data freshness indicator.

### Module 2 — Global Fire Map

[NASA SVS | Current Active Fires from FIRMS](https://images.openai.com/static-rsc-4/DlWuvvXZGy_FGM798w-g3FxDoR172G0VBi8W5omX7PtcOSZ2UfNpHi0e80NPRSyYuo6-Jn3vsf5fGR_bjiavuVdaWPOQv97LzY30i6n66Ruiqx3fVLuqBOPd-7AnIHpiLD0sJWbXSjR1ZaZvDGFYr3-aMzkJSNh8GdLsROLMEw8?purpose=inline)

[svs.gsfc.nasa.gov](https://svs.gsfc.nasa.gov/5546?utm_source=chatgpt.com)

Use MapLibre GL JS.

Map capabilities:

- Global geographic navigation.
- Zoom and pan.
- MODIS and VIIRS layers.
- Hotspot clustering.
- Individual detection markers.
- Heatmap visualization.
- Country and administrative boundaries.
- Geographic search.
- Date and time filtering.
- Confidence filtering.
- Satellite filtering.
- Day/night satellite observation distinction where data supports it.

Clicking a hotspot should open a detailed inspection panel containing:

- Latitude and longitude.
- Acquisition date and time.
- Sensor and satellite.
- Confidence category.
- Brightness temperature.
- FRP (Fire Radiative Power).
- Scan and track dimensions, where available.
- Data source.
- Original observation identifier.

### Module 3 — Historical Burning Activity Calendar

[Calendar Chart with Dark Earth theme | AnyChart Gallery](https://images.openai.com/static-rsc-4/x91ykt9eJFbtqCMQWftWbrdV1-zq5nlmuBn00umuxuMjaj4J1vyq-Ln_AqVBUuY1LXWQOEMf3yL0Rcuxfi3MEH-UZVebATaVIjtndFegWozRhbMuF3UlDLRLMZVulCSo0UWMg8LVcpSScbLPUVa0t1C8fkAHXVxHuI9JZhEUdWI?purpose=inline)

[anychart.com](https://www.anychart.com/products/anychart/gallery/Calendar_Chart/?theme=darkEarth\&utm_source=chatgpt.com)

This is the signature feature and must receive particular development attention.

Users should be able to select any geographic area and examine fire activity over historical periods.

Required views:

- Daily calendar.
- Weekly summary.
- Monthly heatmap.
- Annual calendar.
- Multi-year comparison.
- Seasonal activity analysis.

Each calendar cell should show an appropriately defined activity measurement, such as:

- Number of raw detections.
- Number of harmonized detection groups.
- Unique probable fire events, only when event clustering has been performed.
- Aggregate FRP.

Users must be able to switch between these measurements.

Clicking a date should reveal the actual observations behind that value.

Historical analysis must support the entire available MODIS and VIIRS record, not just the last 30 days.

### Module 4 — Fire Analytics

Provide interactive analysis tools.

Required analytics:

- Daily, weekly and monthly trends.
- Year-over-year comparisons.
- Seasonal activity.
- Country-level comparisons.
- Regional activity rankings.
- Detection density.
- FRP distribution.
- Sensor-specific activity.
- Detection confidence distribution.
- Historical baseline comparison.

Charts should be interactive and support exporting the underlying data.

### Module 5 — Sensor Intelligence and Harmonization

This is the technical centrepiece.

Create a dedicated workspace showing:

- MODIS ingestion status.
- VIIRS ingestion status by satellite.
- Raw observation counts.
- Normalized observation counts.
- Probable cross-sensor matches.
- Unmatched detections.
- Data quality statistics.
- Processing errors.
- Dataset coverage.

The user should be able to inspect a detection and trace it back to the original sensor record.

### Module 6 — Anomaly Detection

[Wildfire Snapshot: Share Wildfire Intelligence—No Login | OroraTech – Blogs – OroraTech](https://images.openai.com/static-rsc-4/L-R-BmF2lNBtx2hu1l2GXNq6ZxtyjYum9W1hxgbH66bOG4cZJgViUOpZ6VSXT1IBqUUqhbTVmbH6PznFWzdxxw0lmZncA8OyWxnCzg40UDRIRnftis9BVEQ7W0074ut0zdp-2AsY1ma1-sstxg_u1DeZxXwM3uxd4cIq2ErQMi4?purpose=inline)

[ororatech.com](https://ororatech.com/resources/news-blog/wildfire-snapshot-share-wildfire-intelligence-with-anyone-no-login-required?utm_source=chatgpt.com)

Develop a statistical anomaly detection engine.

The system should detect:

- Unusually high daily activity.
- Unexpected seasonal activity.
- Sudden regional increases.
- Unusual spatial concentration.
- Abnormal FRP distributions.
- Changes relative to historical averages.

Use:

- Rolling averages.
- Seasonal baselines.
- Median and median absolute deviation.
- Z-scores where assumptions are appropriate.
- Isolation Forest as an optional secondary model.

Every anomaly must have an explanation.

Example:

> Fire detections in this region are substantially higher than the historical baseline for this time of year. The increase is based on observations from the previous seven days compared with the corresponding seasonal historical distribution.

The report should provide the baseline period, sample size, observation count, comparison period and confidence limitations.

### Module 7 — Regional Intelligence

Users should be able to select:

- Country.
- State or province.
- District.
- Custom polygon.
- Circular geographic area.
- Map-drawn bounding box.

The system should generate a regional intelligence profile containing:

- Current activity.
- Historical activity.
- Seasonal trends.
- Satellite distribution.
- Anomalies.
- Geographic concentrations.
- Nearby settlements and infrastructure, if supporting datasets are configured.

### Module 8 — Exposure Analysis

[Decision Support for Integrated Management of Local-Level Adaptation to Climate Changes: The Case of Serbia | International Journal of Disaster Risk Science | Springer Nature Link](https://images.openai.com/static-rsc-4/J4QvHa3LUnAFmt4j4Bobiv94Tz7W3nKFwxrhTI1JJnE6tR6_YgcBd3njTpGYXxKonDk6l9_jhx-IVwXARWPibJ331vdV9sN6xRNMGcOKcHThxV_La11aaz8iktta7vdTRSTlmX0CJNH87kKd9V_OfX-1AuLfdNfOhEK33lkmLtE?purpose=inline)

[link.springer.com](https://link.springer.com/article/10.1007/s13753-021-00357-3?utm_source=chatgpt.com)

Overlay detections with geographic infrastructure datasets.

Potential datasets:

- OpenStreetMap.
- WorldPop.
- Protected Planet.
- ESA WorldCover.
- Government-provided infrastructure data.

Analyse proximity to:

- Population centres.
- Hospitals.
- Schools.
- Roads.
- Power infrastructure.
- Agricultural land.
- Protected forests.

Provide configurable distance bands.

For example:

| Distance from detection | Interpretation                 |
| ----------------------- | ------------------------------ |
| 0–1 km                  | Immediate geographic proximity |
| 1–5 km                  | Nearby                         |
| 5–10 km                 | Wider surrounding area         |
| 10–25 km                | Regional context               |

These are configurable screening distances, not emergency-response thresholds.

Do not call proximity a predicted fire threat. A hotspot may be a small agricultural burn, industrial heat source or another thermal anomaly.

### Module 9 — Intelligence Reports

Users should be able to generate:

- Global fire activity reports.
- Country reports.
- Regional reports.
- Historical seasonal reports.
- Anomaly investigation reports.
- MODIS–VIIRS comparison reports.
- Exposure screening reports.

Export formats:

- PDF.
- CSV.
- GeoJSON.
- JSON.

Reports should include methodology, data sources, timestamps, limitations and observation identifiers.

### Module 10 — AI Intelligence Assistant

[WildfireSight](https://images.openai.com/static-rsc-4/xdLQrNAiu8eTbs2IalD9HKvDrnQPXg9wlig78MIrkiuc5TMqLe0i9CzvA4fkgyjDGqTiK8ctdlStWk7ds2IRxVM-i_ErpkvgT8TVxPqVDk-new28KSYyKvuUJfIjLXHvJyua1fwHWlxfjZfZMDXsh2dqXqexw0TD73jXaQyFGbU?purpose=inline)

[wfs-aui-dev.hb.hn](https://wfs-aui-dev.hb.hn/?utm_source=chatgpt.com)

The AI assistant should interact with actual application data through controlled backend functions.

Example questions:

- What countries have the highest fire activity this month?
- Compare fire activity in Nigeria between 2024 and 2026.
- Which regions have unusual activity compared with their seasonal baseline?
- Show MODIS and VIIRS detections around a selected location.
- Which settlements are within five kilometres of the selected detections?
- Generate a report on the current fire situation in West Africa.

The AI must not invent measurements, coordinates, fire classifications or statistics.

It must call the appropriate analytical functions, retrieve the results and explain them.

## 3. Technical architecture

The architecture should separate the user interface, satellite data ingestion, scientific processing, geospatial analytics and AI services.

[The Intelligence Multiplier: Orchestrating the Future of Sovereign GEOINT (2025–2034)\[v1\] | Preprints.org](https://images.openai.com/static-rsc-4/0JtHCTla7Yn872ozePI0R364EwbWIIKlbhGBOgWMUR41FBLBt3lBy2AY8nciT5blrErvTpyOvilFN0YeXcYNIl_ADryacc69ZrJ288leBdbgzIeV9YAek_0-diyWACxW1mScgVCDyJwTi3Mu99bJKyt0s5uQ8kqv6NYYn8EuS7Y?purpose=inline)

[preprints.org](https://www.preprints.org/manuscript/202604.1163?utm_source=chatgpt.com)

### 3.1 Recommended technology stack

| Component       | Technology                         | Responsibility                 |
| --------------- | ---------------------------------- | ------------------------------ |
| Frontend        | React + TypeScript                 | Application interface          |
| Styling         | Tailwind CSS                       | Responsive design system       |
| Mapping         | MapLibre GL JS                     | Global hotspot visualization   |
| Charts          | Plotly.js                          | Interactive analytics          |
| Backend         | Python + FastAPI                   | Application API                |
| Data processing | Pandas + Polars                    | Large dataset processing       |
| Geospatial      | GeoPandas + Shapely                | Spatial operations             |
| Database        | PostgreSQL + PostGIS               | Spatial and relational storage |
| Analytics       | SciPy + Scikit-learn               | Statistical intelligence       |
| AI              | LLM with tool calling              | Investigation assistant        |
| Cache           | Redis                              | Caching and job coordination   |
| Task processing | Celery                             | Background processing          |
| File storage    | S3-compatible storage              | Raw data and reports           |
| Deployment      | Docker                             | Containerization               |
| Hosting         | Cloudflare Pages + backend hosting | Application deployment         |

### 3.2 Architecture requirements

Build the system as a modular monolith initially, with clearly separated application services.

Do not introduce microservices simply for architectural complexity.

The following services must have independent responsibilities:

1. `firms_ingestion` — NASA data retrieval.
2. `normalization` — Standardized observation records.
3. `harmonization` — Cross-sensor association.
4. `geospatial` — Spatial queries and region analysis.
5. `calendar` — Historical activity aggregation.
6. `anomaly_engine` — Statistical anomaly detection.
7. `exposure_engine` — Infrastructure proximity analysis.
8. `reporting` — Report generation.
9. `ai_assistant` — Natural-language analytical interface.
10. `notification_engine` — Configurable alerts.
11. `auth` — User authentication and authorization.
12. `audit` — User actions and processing history.

Each service should have defined interfaces, unit tests and structured logging.

### 3.3 Data pipeline

NASA FIRMS

MODIS · VIIRS SNPP · NOAA-20 · NOAA-21

Ingestion workers

Scheduled queries · Pagination/batching · Retry · Validation

Raw observation storage

Immutable source records · Retrieval metadata

Normalization and quality control

Schema mapping · Timestamp normalization · Quality flags

MODIS records

Normalized

VIIRS records

Normalized

Cross-sensor association

Spatial-temporal matching · Duplicate assessment · Event grouping

PostGIS + Analytics Engine

Historical calendar · Trends · Anomalies · Exposure · Reports

FIREWATCH X Web Application

Maps · Intelligence · Reports · AI assistant

## 4. NASA FIRMS integration specification

Primary external integration

NASA FIRMS must be the authoritative active-fire observation provider for the first release.

Official documentation:

- [FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/?utm_source=chatgpt.com)
- [Area API](https://firms.modaps.eosdis.nasa.gov/api/area/?utm_source=chatgpt.com)
- [Data availability API](https://firms.modaps.eosdis.nasa.gov/api/data_availability/?utm_source=chatgpt.com)
- [Request MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key/?utm_source=chatgpt.com)

### 4.1 Authentication and configuration

Register for a free NASA FIRMS MAP_KEY.

Store it exclusively on the backend.

Environment configuration:

```
FIRMS_MAP_KEY=your_nasa_firms_map_key

FIRMS_BASE_URL=https://firms.modaps.eosdis.nasa.gov/api

FIRMS_REQUEST_TIMEOUT=60
FIRMS_MAX_RETRIES=4

DATABASE_URL=postgresql://user:password@db:5432/firewatch
REDIS_URL=redis://redis:6379/0

OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_BUCKET=firewatch-data
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=

AI_PROVIDER=
AI_API_KEY=
AI_MODEL=
```

Never put `FIRMS_MAP_KEY`, database credentials or AI provider secrets in frontend JavaScript.

### 4.2 Supported sensor sources

Implement the following standard-processing sources:

| Source            | Satellite  | Purpose                 |
| ----------------- | ---------- | ----------------------- |
| `MODIS_SP`        | Terra/Aqua | Historical observations |
| `VIIRS_SNPP_SP`   | Suomi-NPP  | Historical observations |
| `VIIRS_NOAA20_SP` | NOAA-20    | Historical observations |
| `VIIRS_NOAA21_SP` | NOAA-21    | Historical observations |

Also support corresponding NRT products for current monitoring.

Standard Processing should be the primary source for retrospective historical analysis. NRT should power the operational monitoring interface.

NASA FIRMS supports area-based CSV queries, availability checks and additional fire services. Its area query supports one-to-five-day windows per request. The MAP_KEY currently has a published limit of 5,000 transactions per ten-minute interval, with larger requests potentially consuming multiple transactions.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firms.modaps.eosdis.nasa.gov\&sz=32)

FIRMS+2



### 4.3 API integration example

Use a backend client similar to:

```
import osimport httpximport pandas as pdfrom io import StringIOBASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"class FirmsClient:    def __init__(self):        self.map_key = os.environ["FIRMS_MAP_KEY"]    async def get_area_data(        self,        source: str,        bbox: str,        days: int = 1,        date: str | None = None    ):        if not 1 <= days <= 5:            raise ValueError("Day range must be between 1 and 5")        if source not in {            "MODIS_SP",            "VIIRS_SNPP_SP",            "VIIRS_NOAA20_SP",            "VIIRS_NOAA21_SP",            "MODIS_NRT",            "VIIRS_SNPP_NRT",
```

The production implementation must additionally handle malformed CSV, empty datasets, API errors, rate limiting, retries, request auditing and response schema changes.

For the global historical backfill, do not try to retrieve the entire planet in one giant request. Divide the world into manageable spatial tiles and time windows, track completed ingestion partitions, and resume failed jobs.

NASA specifically warns that global VIIRS requests can return tens of thousands to more than 100,000 records per day.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firms.modaps.eosdis.nasa.gov\&sz=32)

firms.modaps.eosdis.nasa.gov



### 4.4 Historical data acquisition

The application must support a backfill process.

Recommended initial strategy:

1. Discover product availability for each source.
2. Define spatial tiles across the globe.
3. Retrieve historical data in supported time windows.
4. Store raw records.
5. Normalize observations.
6. Process cross-sensor associations.
7. Generate calendar aggregates.
8. Record source coverage and missing dates.

Do not assume that all historical products have identical availability or that every date contains complete observations.

Use the FIRMS data availability and missing-data services to distinguish an actual zero-detection day from a missing-data day.

### 4.5 Data freshness

Maintain separate indicators:

- Last successful NRT retrieval.
- Last successful standard-processing retrieval.
- Latest observation timestamp.
- Last historical backfill.
- Ingestion lag.
- Missing product dates.
- Processing queue status.

Do not describe a dataset as live merely because the map refreshes automatically.

## 5. MODIS–VIIRS harmonization methodology

This section is particularly important for scientific credibility.

MODIS and VIIRS do not observe the Earth at identical spatial resolutions, use identical detection algorithms or have equivalent confidence semantics.

The system must not blindly merge records or compare raw detection totals as if they were interchangeable.

### 5.1 Canonical observation schema

Every source record must be transformed into a canonical schema.

| Canonical field          | Description                         |
| ------------------------ | ----------------------------------- |
| `source_id`              | Original source identifier          |
| `sensor`                 | MODIS or VIIRS                      |
| `satellite`              | Terra, Aqua, SNPP, NOAA-20, NOAA-21 |
| `latitude`               | Observation latitude                |
| `longitude`              | Observation longitude               |
| `acquired_at`            | UTC acquisition timestamp           |
| `confidence_raw`         | Original confidence value           |
| `confidence_category`    | Original source classification      |
| `brightness_temperature` | Relevant source temperature         |
| `frp_mw`                 | Fire Radiative Power in MW          |
| `scan_km`                | Scan dimension                      |
| `track_km`               | Track dimension                     |
| `daynight`               | Day/night observation               |
| `processing_version`     | Original product version            |
| `source_product`         | FIRMS source identifier             |
| `quality_flags`          | Processing and quality information  |

Retain source-specific measurements even when they cannot be mapped into a common field.

For example, MODIS and VIIRS brightness temperature channels are not necessarily equivalent. Store the original channel values and identify the measurement semantics.

### 5.2 Confidence normalization

Do not treat confidence values as directly interchangeable probabilities.

Preserve:

- Original numeric confidence.
- Original categorical confidence.
- Sensor.
- Product version.
- Confidence interpretation.

Create a separate application-level quality classification, but label it as a harmonized interpretation, not NASA's original confidence.

### 5.3 Cross-sensor matching

Use a spatial-temporal association algorithm.

Suggested initial matching approach:

1. Select observations from different sensor families.
2. Restrict comparisons to an appropriate acquisition-time window.
3. Calculate geodesic distance between coordinates.
4. Account for actual pixel dimensions and observation geometry.
5. Calculate candidate spatial overlap where footprint information is available.
6. Score candidate associations.
7. Preserve all possible associations and their scores.
8. Require configurable thresholds before creating a probable match.

Use PostGIS geography operations or a geospatial library such as Shapely and GeoPandas.

A configurable matching model could be:

\\[ S = w_t T + w_s G + w_f F \\]

Where:

- \\(T\\) = temporal similarity.
- \\(G\\) = geographic proximity score.
- \\(F\\) = footprint overlap score.
- \\(w_t,w_s,w_f\\) = configurable weights.

This is an association score, not a probability that the detections represent the same physical fire.

Critical: Multiple detections can represent one fire, and the same fire can be observed by multiple satellites. Therefore, preserve three separate concepts:

- Raw satellite observation.
- Probable cross-sensor match.
- Estimated fire event.

Do not automatically collapse all nearby detections into one event.

### 5.4 Fire-event grouping

Create an optional spatiotemporal clustering engine.

Possible algorithms:

- DBSCAN.
- HDBSCAN.
- Spatial-temporal graph clustering.

Each estimated event should contain:

- Associated observation identifiers.
- First and last detection timestamps.
- Geographic extent.
- Sensor coverage.
- Aggregate and maximum FRP, clearly labelled.
- Number of observations.
- Event confidence and methodology.
- Clustering parameters.

The event model must not imply continuous fire monitoring between satellite overpasses.

### 5.5 Calendar harmonization

Provide several independent metrics:

1. Raw MODIS observations.
2. Raw VIIRS observations.
3. Combined raw detections.
4. Probable cross-sensor match groups.
5. Estimated fire events.
6. Aggregate FRP.

This prevents the burning calendar from becoming scientifically misleading.

## 6. Database architecture and schema

Use PostgreSQL with PostGIS as the primary database.

The schema must support high-volume satellite observations, spatial filtering, historical queries and provenance tracking.

### 6.1 Core database entities

Database relationship overview

```
users
  ├── saved_regions
  ├── alerts
  ├── reports
  └── audit_logs

data_sources
  └── ingestion_runs
        └── raw_observations
              └── fire_observations
                    ├── observation_matches
                    └── event_observations
                          └── fire_events

geographic_regions
  ├── daily_fire_statistics
  ├── regional_baselines
  └── anomalies

infrastructure_assets
  └── exposure_assessments

anomaly_models
  └── anomaly_results
```

### 6.2 Table definitions

`users`

| Field         | Type           |
| ------------- | -------------- |
| id            | UUID           |
| email         | VARCHAR UNIQUE |
| password_hash | TEXT           |
| role          | VARCHAR        |
| created_at    | TIMESTAMP      |
| last_login_at | TIMESTAMP      |

Roles: `ADMIN`, `ANALYST`, `RESEARCHER`, `VIEWER`.

`data_sources`

| Field            | Type           |
| ---------------- | -------------- |
| id               | UUID           |
| source_code      | VARCHAR UNIQUE |
| sensor           | VARCHAR        |
| satellite        | VARCHAR        |
| processing_level | VARCHAR        |
| active           | BOOLEAN        |

`ingestion_runs`

| Field            | Type      |
| ---------------- | --------- |
| id               | UUID      |
| source_id        | UUID FK   |
| started_at       | TIMESTAMP |
| completed_at     | TIMESTAMP |
| status           | VARCHAR   |
| records_received | BIGINT    |
| records_inserted | BIGINT    |
| records_rejected | BIGINT    |
| error_message    | TEXT      |
| query_parameters | JSONB     |

`fire_observations`

This is the primary observation table.

| Field                  | Type                   |
| ---------------------- | ---------------------- |
| id                     | UUID                   |
| source_id              | UUID FK                |
| source_record_id       | VARCHAR                |
| sensor                 | VARCHAR                |
| satellite              | VARCHAR                |
| location               | GEOGRAPHY(Point, 4326) |
| latitude               | DOUBLE PRECISION       |
| longitude              | DOUBLE PRECISION       |
| acquired_at            | TIMESTAMPTZ            |
| confidence_raw         | VARCHAR                |
| confidence_category    | VARCHAR                |
| brightness_temperature | DOUBLE PRECISION       |
| brightness_channel     | VARCHAR                |
| frp_mw                 | DOUBLE PRECISION       |
| scan_km                | DOUBLE PRECISION       |
| track_km               | DOUBLE PRECISION       |
| daynight               | VARCHAR                |
| processing_version     | VARCHAR                |
| source_payload         | JSONB                  |
| quality_flags          | JSONB                  |
| ingested_at            | TIMESTAMPTZ            |

Use a unique constraint based on the source product and original observation identity, with a carefully defined fallback fingerprint when source IDs are unavailable.

`observation_matches`

| Field                  | Type             |
| ---------------------- | ---------------- |
| id                     | UUID             |
| observation_a_id       | UUID FK          |
| observation_b_id       | UUID FK          |
| temporal_delta_seconds | INTEGER          |
| spatial_distance_m     | DOUBLE PRECISION |
| footprint_overlap      | DOUBLE PRECISION |
| association_score      | DOUBLE PRECISION |
| match_status           | VARCHAR          |
| algorithm_version      | VARCHAR          |
| created_at             | TIMESTAMPTZ      |

`fire_events`

| Field                 | Type             |
| --------------------- | ---------------- |
| id                    | UUID             |
| first_detected_at     | TIMESTAMPTZ      |
| last_detected_at      | TIMESTAMPTZ      |
| geometry              | GEOMETRY         |
| observation_count     | INTEGER          |
| sensor_count          | INTEGER          |
| maximum_frp_mw        | DOUBLE PRECISION |
| aggregate_frp_mw      | DOUBLE PRECISION |
| clustering_method     | VARCHAR          |
| clustering_parameters | JSONB            |
| methodology_version   | VARCHAR          |

`event_observations`

Contains the many-to-many relationship between estimated events and satellite observations.

`geographic_regions`

| Field        | Type                         |
| ------------ | ---------------------------- |
| id           | UUID                         |
| name         | VARCHAR                      |
| region_type  | VARCHAR                      |
| country_code | VARCHAR                      |
| geometry     | GEOMETRY(MultiPolygon, 4326) |
| data_source  | VARCHAR                      |

`daily_fire_statistics`

| Field                 | Type             |
| --------------------- | ---------------- |
| id                    | UUID             |
| region_id             | UUID FK          |
| date                  | DATE             |
| sensor                | VARCHAR          |
| raw_detection_count   | BIGINT           |
| probable_match_count  | BIGINT           |
| estimated_event_count | BIGINT           |
| total_frp_mw          | DOUBLE PRECISION |
| data_completeness     | JSONB            |

`regional_baselines`

Stores historical comparison distributions.

Include:

- Region.
- Sensor or harmonized metric.
- Day-of-year or seasonal period.
- Baseline start/end.
- Sample count.
- Mean.
- Median.
- Standard deviation.
- Median absolute deviation.
- Quantiles.
- Model version.

`anomalies`

Include:

- Region.
- Detection period.
- Metric.
- Observed value.
- Expected value.
- Deviation score.
- Severity.
- Method.
- Model version.
- Evidence metadata.
- Investigation status.

`infrastructure_assets`

Include:

- Asset identifier.
- Asset category.
- Name.
- Geographic location.
- Data source.
- Source timestamp.
- Geometry.

`exposure_assessments`

Include:

- Observation or event reference.
- Asset reference.
- Distance in metres.
- Assessment date.
- Distance band.
- Methodology version.

Additional tables:

- `alerts`
- `saved_regions`
- `reports`
- `audit_logs`
- `model_registry`
- `data_quality_checks`
- `api_request_logs`
- `system_settings`

### 6.3 Database optimization

Implement:

- Spatial GiST indexes.
- B-tree indexes on acquisition timestamps.
- Composite indexes on sensor and acquisition date.
- Unique indexes for source-record deduplication.
- Date-based partitioning for high-volume observations.
- Materialized views for calendar aggregates where beneficial.
- Background refresh jobs.
- Query pagination.

For historical scale, partition `fire_observations` by acquisition month or year according to measured data volume.

Do not store large original satellite files directly in PostgreSQL. Use object storage for files and store their references in the database.

## 7. API design

The backend must expose versioned REST APIs.

Base path:

```
/api/v1
```

### 7.1 Dashboard APIs

| Method | Endpoint                 | Purpose                  |
| ------ | ------------------------ | ------------------------ |
| GET    | `/dashboard/overview`    | Global summary           |
| GET    | `/dashboard/trends`      | Global activity trends   |
| GET    | `/dashboard/top-regions` | Highest activity regions |
| GET    | `/dashboard/data-status` | Data freshness           |

### 7.2 Observation APIs

| Method | Endpoint           | Purpose                |
| ------ | ------------------ | ---------------------- |
| GET    | `/fires`           | Search detections      |
| GET    | `/fires/{id}`      | Observation details    |
| GET    | `/fires/nearby`    | Nearby detections      |
| GET    | `/fires/aggregate` | Spatial aggregation    |
| GET    | `/fires/geojson`   | Map-ready observations |
| GET    | `/fires/sources`   | Available sensors      |

Example:

```
GET /api/v1/fires?bbox=-5,4,15,14&start_date=2026-01-01&end_date=2026-01-31&sensor=VIIRS
```

Support pagination, date constraints, confidence filters, satellite filters and geographic constraints.

### 7.3 Calendar APIs

| Method | Endpoint                | Purpose               |
| ------ | ----------------------- | --------------------- |
| GET    | `/calendar/daily`       | Daily activity        |
| GET    | `/calendar/monthly`     | Monthly aggregation   |
| GET    | `/calendar/yearly`      | Annual calendar       |
| GET    | `/calendar/compare`     | Multi-year comparison |
| GET    | `/calendar/region/{id}` | Regional calendar     |

Example:

```
GET /api/v1/calendar/yearly?region_id=NG&year=2026&metric=raw_detections
```

### 7.4 Harmonization APIs

| Method | Endpoint                      | Purpose                       |
| ------ | ----------------------------- | ----------------------------- |
| GET    | `/harmonization/summary`      | Harmonization statistics      |
| GET    | `/harmonization/matches`      | Probable cross-sensor matches |
| GET    | `/harmonization/matches/{id}` | Match details                 |
| POST   | `/harmonization/run`          | Launch matching job           |
| GET    | `/harmonization/jobs/{id}`    | Job status                    |

### 7.5 Anomaly APIs

| Method | Endpoint                  | Purpose            |
| ------ | ------------------------- | ------------------ |
| GET    | `/anomalies`              | Search anomalies   |
| GET    | `/anomalies/{id}`         | Anomaly evidence   |
| POST   | `/anomalies/analyze`      | Launch analysis    |
| GET    | `/anomalies/regions/{id}` | Regional anomalies |

### 7.6 Regional intelligence APIs

| Method | Endpoint                     | Purpose             |
| ------ | ---------------------------- | ------------------- |
| GET    | `/regions`                   | List regions        |
| GET    | `/regions/search`            | Geographic search   |
| GET    | `/regions/{id}`              | Region details      |
| GET    | `/regions/{id}/intelligence` | Regional profile    |
| POST   | `/regions/custom`            | Create custom area  |
| GET    | `/regions/{id}/history`      | Historical activity |

### 7.7 Exposure APIs

| Method | Endpoint                 | Purpose                   |
| ------ | ------------------------ | ------------------------- |
| GET    | `/exposure/assets`       | Search infrastructure     |
| POST   | `/exposure/analyze`      | Run proximity analysis    |
| GET    | `/exposure/results/{id}` | Analysis results          |
| GET    | `/exposure/regions/{id}` | Regional exposure summary |

### 7.8 Reporting APIs

| Method | Endpoint                 | Purpose         |
| ------ | ------------------------ | --------------- |
| POST   | `/reports/generate`      | Create report   |
| GET    | `/reports`               | List reports    |
| GET    | `/reports/{id}`          | Report details  |
| GET    | `/reports/{id}/download` | Download report |

### 7.9 AI APIs

| Method | Endpoint                        | Purpose                  |
| ------ | ------------------------------- | ------------------------ |
| POST   | `/assistant/chat`               | Ask analytical questions |
| GET    | `/assistant/conversations`      | Conversation history     |
| GET    | `/assistant/conversations/{id}` | Retrieve conversation    |

### 7.10 Administrative APIs

| Method | Endpoint                   | Purpose              |
| ------ | -------------------------- | -------------------- |
| GET    | `/admin/ingestion/jobs`    | Ingestion jobs       |
| POST   | `/admin/ingestion/run`     | Trigger ingestion    |
| GET    | `/admin/ingestion/sources` | Source health        |
| GET    | `/admin/quality`           | Data-quality reports |
| GET    | `/admin/system/health`     | System health        |
| GET    | `/admin/audit`             | Audit records        |

All API endpoints must have validation, authorization where required, structured errors, rate limiting and OpenAPI documentation.

## 8. Advanced intelligence methodology

### 8.1 Historical baselines

Calculate baselines by geographic region, metric and sensor.

Avoid comparing January activity against a July baseline in a region with strong seasonal differences.

Recommended baseline options:

- Rolling 30-day.
- Rolling 90-day.
- Same period in previous years.
- Day-of-year seasonal baseline.
- Monthly historical baseline.

Require sufficient historical samples before declaring an anomaly.

### 8.2 Anomaly scoring

A robust starting point is the median absolute deviation:

\\[ MAD = median(|x_i - median(X)|) \\]

\\[ Z_r = \frac{x - median(X)}{1.4826 \times MAD} \\]

Where \\(Z_r\\) is a robust standardized deviation score.

Handle cases where MAD is zero or where the sample is insufficient.

Anomaly classifications should be configurable and should not be confused with probabilities of a wildfire.

### 8.3 Spatial anomaly detection

Detect unusual spatial concentrations using:

- Geographic grid aggregation.
- Kernel density estimation.
- Spatial clustering.
- Historical regional density comparison.

Use a consistent geographic grid when comparing periods.

### 8.4 Predictive analytics

For the advanced release, include optional experimental forecasting of regional detection counts.

Potential models:

- Seasonal statistical models.
- Prophet-style time-series forecasting.
- Gradient-boosted regression.
- Random Forest regression.

Forecasts should predict expected observation activity, not claim to predict the precise location or spread of a future fire.

Evaluate using rolling-origin backtesting and compare against simple seasonal baselines.

### 8.5 Explainability

Every anomaly and forecast should expose:

- Model or algorithm.
- Training or baseline period.
- Input metrics.
- Expected value.
- Observed value.
- Uncertainty or prediction interval, where applicable.
- Data completeness.
- Known limitations.

The platform must never allow an AI-generated explanation to overwrite scientific source measurements.

## 9. UI/UX and design system

The application should look like a professional environmental intelligence platform, not a generic administration dashboard.

### 9.1 Visual direction

[Live Canada wildfire map | Real-time fire tracking tool](https://images.openai.com/static-rsc-4/tFl2ppQO2J1rNX0nNg-J3dSZH203TuH_8FJ1DlH6eqGe9V23L2SBZGPaKfu4ZyE_5_Ce6bbz0RhSRq8v9695KISEg1J55Mla7XMA-C-ljRC2DDq8tIR3dXiQIbRqr-wmM1OnAMdKeTNYRmBx-VwB3zLZ9PpY3uDI2M4t3HtOWR4?purpose=inline)

[RiskLabs: Next Generation Wildfire Intelligence](https://images.openai.com/static-rsc-4/DdZ-g47V2C9BPgrouf9z-wZVRQwiSojWBsY4fWtp0L9ZyG1bd-VXf3sAmQ6aqi0x9bzqbi-o-lNIsrVq9XvMlRH65vumRmz4TejAh5nJ-hE7A6lJBzY9uQIph-txvutEuTuC7EqCWuYEt-lpQUnJSS_eiPweipBMxk7U-st_d1E?purpose=inline)

[High-Res Imaging and Predictive AI: How AiDash Protects the Grid - News](https://images.openai.com/static-rsc-4/oizFC_zjSthx1rejgbzpRv9Z7Ki_KiFHaepAWH9pos93KUet0aTK9HKkRQeJ7cIgwOpqUdw1PSObsD4Ns79CLpEzN8Lz6XgG7uPnF4yw0SJ6XWXlTwaaEmQ9q4OR8Rv4E4nEA4HJ0eEXlAWmLQUpXiOVQ0a88ag_kBydLhGBqbA?purpose=inline)

10

Design language:

- Dark-first interface.
- Deep navy and charcoal backgrounds.
- Muted grey surfaces.
- Orange, amber and red for fire activity.
- Cyan and blue for geographic information.
- Green for normal system and data states.
- Thin borders and subtle elevation.
- Minimal unnecessary gradients.
- High information density without visual clutter.

Suggested palette:

| Token          | Colour    |
| -------------- | --------- |
| Background     | `#080D16` |
| Sidebar        | `#0C1421` |
| Panel          | `#111C2C` |
| Border         | `#253449` |
| Primary text   | `#F1F5F9` |
| Secondary text | `#94A3B8` |
| Fire low       | `#FACC15` |
| Fire medium    | `#FB923C` |
| Fire high      | `#EF4444` |
| Normal         | `#22C55E` |
| Information    | `#38BDF8` |

### 9.2 Application navigation

FIREWATCH X

System online

Overview

Global Fire Map

Burning Calendar

Analytics

Sensor Intelligence

Anomaly Detection

Regional Intelligence

Exposure Analysis

Reports

AI Assistant

Settings & Administration

### 9.3 Main dashboard layout

Desktop:

- Left: fixed navigation sidebar.
- Top: global search, date selector, notifications and profile.
- Centre: main analytical workspace.
- Right: contextual intelligence panel.
- Bottom: selected time-range and data-source information.

Mobile:

- Responsive navigation.
- Full-width map.
- Collapsible analytical panels.
- Touch-friendly filters.
- Bottom-sheet hotspot details.

The map must remain usable on mobile, not simply shrink the desktop dashboard.

### 9.4 Interaction requirements

- All map layers must be toggleable.
- Filters must update displayed data.
- Calendar cells must be clickable.
- Charts must support drill-down.
- Hotspot details must show provenance.
- Reports must be generated from selected filters.
- The AI assistant must preserve analytical context.
- Long-running jobs must expose progress and failure states.
- Empty and incomplete data states must be clearly distinguished.

## 10. Security and reliability

Implement production-grade security from the beginning.

Authentication

- Secure login.
- Password hashing using Argon2id.
- Role-based access control.
- Session expiry.
- Optional MFA.
- Password reset.
- Secure logout.

Application security

- Strict input validation.
- Parameterized database queries.
- CORS restrictions.
- CSRF protection where cookie-based authentication is used.
- Rate limiting.
- Secrets management.
- Secure HTTP headers.
- File upload validation.
- Audit logging.

Data reliability

- Idempotent ingestion.
- Duplicate detection.
- Retry policies with exponential backoff.
- Failed-job recovery.
- Database backups.
- Data provenance.
- Schema migration management.
- Queue monitoring.

AI security

- Treat retrieved data as untrusted.
- Prevent prompt injection from external records.
- Allow only approved analytical tools.
- Enforce user permissions on tool calls.
- Never expose environment variables or internal secrets.
- Log tool calls and source records used to produce answers.

### 10.1 Observability

Provide:

- Structured application logs.
- Ingestion success/failure metrics.
- API latency.
- Database performance.
- Queue depth.
- Background worker health.
- Data freshness.
- Error tracking.

Use OpenTelemetry-compatible instrumentation where practical.

## 11. Testing and scientific validation

A visually impressive platform is not sufficient. FIREWATCH X must produce defensible analytical results.

### 11.1 Unit testing

Test:

- NASA field normalization.
- Coordinate validation.
- Timestamp parsing.
- Confidence interpretation.
- FRP handling.
- Duplicate detection.
- Spatial distance calculations.
- Match scoring.
- Calendar aggregation.
- Baseline computation.
- Anomaly detection.
- Report generation.

### 11.2 Integration testing

Test:

- NASA FIRMS API connection.
- Data availability checks.
- Historical ingestion.
- Database persistence.
- Geospatial queries.
- Map GeoJSON responses.
- Background job execution.
- AI analytical tool calls.
- Report exports.

### 11.3 Scientific validation

| Validation            | Expected result                    |
| --------------------- | ---------------------------------- |
| Coordinate tests      | Correct geographic positions       |
| Timestamp tests       | Correct UTC conversion             |
| Deduplication         | No repeated source records         |
| Cross-sensor matching | No automatic false equivalence     |
| Calendar totals       | Reconcile with source observations |
| FRP aggregation       | Correct units and aggregation      |
| Baselines             | Reproducible results               |
| Anomaly detection     | Correct synthetic test cases       |
| Missing data          | Never interpreted as zero activity |
| Spatial exposure      | Correct geodesic distance          |

### 11.4 Historical backtesting

Select historical geographic regions and periods.

Run the analytical pipeline and compare:

- Sensor-specific detection totals.
- Cross-sensor association results.
- Seasonal patterns.
- Anomaly classifications.
- Model forecasts against actual observations.

Use synthetic datasets to test edge cases such as duplicate observations, missing days, sensor outages, extreme FRP values and date-boundary errors.

### 11.5 Performance testing

Test at increasing dataset sizes:

- 100,000 observations.
- 1 million observations.
- 10 million observations.
- Larger volumes as infrastructure permits.

Test map loading, calendar aggregation, geographic search, filtering and report generation.

Do not make performance claims until benchmarks have actually been measured.

## 12. Deployment and infrastructure

Recommended deployment:

Users / Web browsers

Cloudflare Pages

React frontend · CDN · HTTPS

Python FastAPI backend

Authentication · API · Analytical services

PostgreSQL

PostGIS data

Redis

Cache and queues

Celery workers

Data processing

Object storage

Exports and archives

### Required deployment deliverables

- Dockerfiles.
- Docker Compose for local development.
- Production container configuration.
- Environment variable template.
- Database migration scripts.
- Seed data scripts.
- Background worker configuration.
- Scheduled ingestion configuration.
- Health-check endpoints.
- Backup and restoration instructions.
- CI/CD pipeline.
- Deployment documentation.

For the hackathon, deploy the frontend and backend separately if necessary. Keep the database, Redis and background workers in a persistent environment.

Do not run long historical ingestion jobs inside a serverless request handler.

## 13. Project directory structure

Use a maintainable monorepo.

```
firewatch-x/
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       ├── layouts/
│       ├── pages/
│       │   ├── overview/
│       │   ├── fire-map/
│       │   ├── calendar/
│       │   ├── analytics/
│       │   ├── harmonization/
│       │   ├── anomalies/
│       │   ├── regions/
│       │   ├── exposure/
│       │   ├── reports/
│       │   └── assistant/
│       ├── hooks/
│       ├── services/
│       ├── stores/
│       ├── types/
│       └── utils/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── firms_ingestion/
│   │   │   ├── normalization/
│   │   │   ├── harmonization/
│   │   │   ├── geospatial/
│   │   │   ├── calendar/
│   │   │   ├── anomalies/
│   │   │   ├── exposure/
│   │   │   ├── reporting/
│   │   │   └── assistant/
│   │   ├── workers/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
│
├── infrastructure/
│   ├── docker/
│   ├── deployment/
│   └── monitoring/
│
├── scripts/
│   ├── bootstrap.py
│   ├── ingest_historical.py
│   ├── ingest_recent.py
│   └── validate_data.py
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── data_dictionary.md
│   ├── methodology.md
│   ├── deployment.md
│   ├── user_guide.md
│   └── scientific_validation.md
│
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

## 14. Master implementation prompt

The following is the main build instruction. It combines the product requirements, architecture, scientific methodology, implementation sequence and acceptance criteria into one instruction for a coding agent.

Ready for implementation

# FIREWATCH X — MASTER END-TO-END IMPLEMENTATION PROMPT

## ROLE

Act as a senior full-stack software architect, geospatial engineer, satellite remote-sensing specialist, data scientist, machine-learning engineer, UI/UX designer and DevOps engineer.

Your task is to design, implement, test and deploy FIREWATCH X, a production-oriented global fire intelligence platform built around genuine NASA MODIS and VIIRS active-fire observations.

Do not produce a static prototype, a collection of disconnected screens, or a dashboard populated with invented statistics.

Build a functioning application with a real data pipeline, working APIs, persistent database, scientific processing, interactive maps, historical analytics, anomaly detection, reports and an AI-assisted investigation interface.

Work directly in the existing repository if one is supplied. Inspect its existing files and technology before making architectural changes. Preserve working functionality unless a change is necessary.

---

# PART 1 — PRODUCT DEFINITION

Product name: FIREWATCH X

Product category: Global Environmental Intelligence and Fire Monitoring.

Mission:

Transform satellite fire detections into a unified global intelligence platform that helps researchers, environmental agencies, emergency planners and the public investigate active-fire observations, understand historical burning patterns, identify unusual activity and assess the geographic proximity of detected activity to communities and infrastructure.

Primary data sources:

- NASA MODIS Terra.
- NASA MODIS Aqua.
- NASA VIIRS Suomi-NPP.
- NASA VIIRS NOAA-20.
- NASA VIIRS NOAA-21.

Geographic coverage: Global.

Primary data provider: NASA FIRMS.

Build the system around ten modules:

1. Global Overview.
2. Global Fire Map.
3. Historical Burning Activity Calendar.
4. Fire Analytics.
5. Sensor Intelligence and Harmonization.
6. Anomaly Detection.
7. Regional Intelligence.
8. Exposure Analysis.
9. Intelligence Reports.
10. AI Intelligence Assistant.

The actual challenge requirements must remain the central focus: MODIS/VIIRS harmonization and the historical burning activity calendar.

---

# PART 2 — TECHNOLOGY STACK

Frontend:

- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- MapLibre GL JS.
- Plotly.js.
- TanStack Query.
- Zustand where shared client state is necessary.

Backend:

- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy.
- Alembic.

Scientific processing:

- Pandas.
- Polars where large-scale processing benefits from it.
- NumPy.
- SciPy.
- GeoPandas.
- Shapely.
- PyProj.
- Scikit-learn.

Database:

- PostgreSQL.
- PostGIS.

Infrastructure:

- Redis.
- Celery.
- S3-compatible object storage.
- Docker.
- Docker Compose.

Testing:

- Pytest.
- Vitest.
- React Testing Library.
- Playwright.

Use stable, compatible package versions. Pin dependencies and provide lockfiles.

Do not introduce unnecessary microservices. Build a modular monolith with independently testable service modules and background workers.

---

# PART 3 — VISUAL DESIGN AND EXPERIENCE

Create a premium dark geospatial intelligence interface.

The visual language should resemble professional satellite intelligence, GIS and environmental monitoring software.

Design palette:

- Background: #080D16.
- Sidebar: #0C1421.
- Panels: #111C2C.
- Borders: #253449.
- Primary text: #F1F5F9.
- Secondary text: #94A3B8.
- Low activity: #FACC15.
- Medium activity: #FB923C.
- High activity: #EF4444.
- Normal status: #22C55E.
- Information: #38BDF8.

Use subtle borders, clear typography, compact analytical cards, readable charts and restrained animation.

Avoid excessive gradients, decorative charts, giant empty cards, excessive rounded containers and generic AI-generated dashboard aesthetics.

The application must be responsive and functional on desktop, tablet and mobile.

## Main navigation

Create a persistent sidebar with:

- Overview.
- Global Fire Map.
- Burning Calendar.
- Analytics.
- Sensor Intelligence.
- Anomaly Detection.
- Regional Intelligence.
- Exposure Analysis.
- Reports.
- AI Assistant.
- Settings.

## Global application header

Include:

- FIREWATCH X logo.
- Global search.
- Geographic search.
- Date selector.
- Notifications.
- Data freshness indicator.
- User profile.
- Theme settings.

All navigation elements and controls must work.

---

# PART 4 — NASA FIRMS DATA INTEGRATION

Implement NASA FIRMS as the primary data provider.

Official documentation:

[https://firms.modaps.eosdis.nasa.gov/api/](https://firms.modaps.eosdis.nasa.gov/api/)

[https://firms.modaps.eosdis.nasa.gov/api/area/](https://firms.modaps.eosdis.nasa.gov/api/area/)

[https://firms.modaps.eosdis.nasa.gov/api/data_availability/](https://firms.modaps.eosdis.nasa.gov/api/data_availability/)

[https://firms.modaps.eosdis.nasa.gov/api/map_key/](https://firms.modaps.eosdis.nasa.gov/api/map_key/)

Create a configurable FIRMS client.

Environment variables:

FIRMS_MAP_KEY\
FIRMS_BASE_URL\
FIRMS_REQUEST_TIMEOUT\
FIRMS_MAX_RETRIES

Never expose the MAP_KEY in frontend code.

## Supported sources

Standard Processing:

- MODIS_SP.
- VIIRS_SNPP_SP.
- VIIRS_NOAA20_SP.
- VIIRS_NOAA21_SP.

Near-Real-Time:

- MODIS_NRT.
- VIIRS_SNPP_NRT.
- VIIRS_NOAA20_NRT.
- VIIRS_NOAA21_NRT.

Support source discovery and availability checks.

Implement:

1. Global ingestion.
2. Custom bounding-box ingestion.
3. Country/region ingestion where supported.
4. Historical ingestion.
5. Recent observation ingestion.
6. Data availability checking.
7. Missing-date detection.
8. Retry and failure recovery.
9. Rate-limit-aware request scheduling.
10. Ingestion auditing.

Use the FIRMS area API.

The documented API pattern is:

[https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}](https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE})

For historical queries, append the appropriate date parameter.

Respect the documented maximum five-day range per area request.

Check the current API documentation during implementation rather than assuming endpoint behaviour will never change.

## Historical ingestion engine

Build a resumable historical ingestion engine.

It must:

- Discover source availability.
- Divide global coverage into manageable spatial tiles.
- Divide date ranges into supported windows.
- Schedule retrieval jobs.
- Store raw source records.
- Track completed partitions.
- Resume failed jobs.
- Avoid repeated ingestion.
- Detect missing data.
- Record request and response metadata.
- Validate every batch.

Do not attempt an unbounded global historical download in one request.

Implement configurable ingestion limits and an administrative control panel.

The ingestion process must distinguish:

- No detections.
- Missing satellite data.
- API failure.
- Incomplete processing.
- Data not yet available.

Never interpret missing data as zero fire activity.

## NRT and standard-processing separation

Use NRT for current operational monitoring.

Use Standard Processing for historical analysis and retrospective comparisons.

Keep processing versions and source types visible.

When a newer processing release supersedes older observations, retain version and provenance information and implement an explicit reconciliation policy.

Do not blindly combine different processing versions.

---

# PART 5 — DATA NORMALIZATION

Create a canonical observation model.

Required fields:

- Internal UUID.
- Original source record identifier.
- Source product.
- Sensor.
- Satellite.
- Latitude.
- Longitude.
- UTC acquisition timestamp.
- Original confidence.
- Original confidence category.
- Brightness temperature.
- Brightness channel.
- FRP in MW.
- Scan dimension.
- Track dimension.
- Day/night indicator.
- Processing version.
- Source payload.
- Quality flags.
- Ingestion timestamp.

Preserve all original source-specific fields in JSONB or a suitable source-specific structure.

Implement separate normalization adapters for MODIS and each VIIRS product family.

Do not assume that confidence values or brightness temperature channels have identical meanings across sensors.

Implement:

- Coordinate validation.
- Timestamp validation.
- Numeric validation.
- Schema validation.
- Source-record deduplication.
- Data-quality reporting.

Maintain original raw records for provenance and reproducibility.

---

# PART 6 — MODIS/VIIRS HARMONIZATION ENGINE

Develop a scientifically defensible harmonization engine.

The engine must never blindly combine sensor observations.

Implement the following processing stages.

### Stage 1: Sensor-specific normalization

Convert original observations into the canonical schema while retaining original measurements.

### Stage 2: Quality assessment

Apply validation and quality flags.

### Stage 3: Spatial-temporal candidate association

Identify potentially related observations from different sensors.

Use:

- Acquisition time difference.
- Geodesic spatial distance.
- Pixel scan and track dimensions.
- Available observation footprints.
- Spatial overlap where possible.
- Satellite identity.
- Observation quality.

### Stage 4: Match scoring

Implement a configurable association score:

S = wt*T + ws*G + wf\*F

Where:

- T is temporal similarity.
- G is geographic proximity.
- F is footprint overlap.
- wt, ws and wf are configurable weights.

The score is not a probability of physical identity.

### Stage 5: Match classification

Classify associations as:

- Probable match.
- Possible match.
- Unmatched.
- Rejected.

Allow users to inspect why a match was produced.

### Stage 6: Fire-event estimation

Implement optional spatiotemporal event clustering.

Start with DBSCAN and allow future HDBSCAN integration.

Preserve the original observations associated with each estimated event.

Do not claim that each cluster represents a confirmed individual fire.

### Stage 7: Harmonization output

Expose:

- Raw MODIS observations.
- Raw VIIRS observations.
- Combined raw observations.
- Probable cross-sensor match groups.
- Estimated fire events.
- Unmatched observations.
- Match statistics.

Every output must be traceable to original records and the algorithm version used.

---

# PART 7 — DATABASE IMPLEMENTATION

Use PostgreSQL and PostGIS.

Create migrations for:

- users.
- data_sources.
- ingestion_runs.
- raw_observations.
- fire_observations.
- observation_matches.
- fire_events.
- event_observations.
- geographic_regions.
- daily_fire_statistics.
- regional_baselines.
- anomalies.
- anomaly_models.
- infrastructure_assets.
- exposure_assessments.
- saved_regions.
- alerts.
- reports.
- audit_logs.
- data_quality_checks.

Use UUID primary keys.

Use foreign-key constraints and appropriate unique constraints.

Add:

- GiST spatial indexes.
- Timestamp indexes.
- Sensor/date composite indexes.
- Source-record uniqueness indexes.
- Appropriate partitioning for observation volumes.

Implement Alembic migrations.

Use materialized views or pre-aggregated tables for expensive historical queries.

Do not store large satellite imagery files directly in PostgreSQL.

---

# PART 8 — GLOBAL FIRE MAP

Implement MapLibre GL JS.

The map must display:

- Global fire observations.
- MODIS layer.
- VIIRS layer.
- Individual satellite filters.
- Sensor-specific markers.
- Hotspot clusters.
- Density heatmaps.
- Country boundaries.
- Geographic search.
- Date filtering.
- Confidence filtering.
- FRP filtering.
- Day/night filtering.

Implement dynamic viewport-based querying.

Do not download the entire global historical dataset into the browser.

Use GeoJSON for appropriately sized query results and vector tiles or server-side aggregation for large-scale views.

Clicking a detection must open an information panel with the original source information.

Provide map legends and source attribution.

---

# PART 9 — HISTORICAL BURNING ACTIVITY CALENDAR

This is a primary project deliverable.

Build an interactive historical activity calendar.

Support:

- Daily activity.
- Weekly aggregation.
- Monthly heatmaps.
- Annual calendars.
- Multi-year comparisons.
- Seasonal analysis.

Allow selection of:

- Country.
- State/province.
- District.
- Custom polygon.
- Bounding box.
- Circular region.

Allow the user to switch metrics:

1. Raw MODIS detections.
2. Raw VIIRS detections.
3. Combined raw detections.
4. Probable cross-sensor match groups.
5. Estimated fire events.
6. Aggregate FRP.

Every calendar value must be traceable to underlying observations or derived event records.

Clicking a calendar cell must open a detailed view of the observations for that date.

Distinguish zero activity from unavailable or incomplete satellite data.

Implement year-over-year comparison and historical seasonal baselines.

---

# PART 10 — FIRE ANALYTICS

Implement:

- Daily activity charts.
- Weekly activity charts.
- Monthly activity charts.
- Annual activity charts.
- Country rankings.
- Regional rankings.
- Sensor comparisons.
- FRP distributions.
- Confidence distributions.
- Seasonal patterns.
- Historical baselines.
- Spatial density.

All charts must be connected to backend APIs.

Provide loading, error and empty-data states.

Support CSV export of chart data.

---

# PART 11 — ADVANCED ANOMALY DETECTION

Develop a statistical anomaly engine.

Implement:

- Rolling-average comparisons.
- Seasonal baseline comparisons.
- Median absolute deviation.
- Robust standardized deviation.
- Z-score where statistically appropriate.
- Isolation Forest as an optional secondary model.
- Spatial concentration analysis.

Analyse:

- Daily detection counts.
- Weekly detection counts.
- FRP.
- Regional detection density.
- Sensor-specific activity.

An anomaly must contain:

- Region.
- Metric.
- Observation period.
- Baseline period.
- Observed value.
- Expected value.
- Deviation score.
- Sample size.
- Severity.
- Method.
- Model version.
- Evidence records.
- Data-completeness status.

Do not generate anomaly alerts where historical data are insufficient.

Provide an explainability panel.

---

# PART 12 — REGIONAL INTELLIGENCE

Build a global regional analysis workspace.

Support administrative regions and custom geographic boundaries.

A regional intelligence report must include:

- Current activity.
- Historical activity.
- Monthly trends.
- Seasonal comparison.
- Sensor breakdown.
- Geographic concentration.
- Anomaly results.
- Data completeness.
- Source attribution.

Start with global country coverage.

Allow users to save frequently monitored regions.

Do not hardcode Nigeria as the only supported country.

---

# PART 13 — EXPOSURE ANALYSIS

Integrate optional supporting geographic datasets.

Potential sources:

- OpenStreetMap.
- WorldPop.
- ESA WorldCover.
- Protected Planet.
- Other documented and appropriately licensed infrastructure datasets.

Allow geographic proximity analysis for:

- Settlements.
- Roads.
- Hospitals.
- Schools.
- Agricultural areas.
- Protected forests.
- Power infrastructure.

Use PostGIS distance queries and configurable distance bands.

Expose the distance, reference location, dataset and assessment timestamp.

Clearly label this as geographic exposure screening.

Do not present it as a fire-spread prediction, confirmed impact assessment or evacuation instruction.

---

# PART 14 — AI INTELLIGENCE ASSISTANT

Build a conversational analytical assistant.

It must use controlled application tools rather than inventing answers.

Provide tools such as:

- get_global_fire_summary.
- search_fire_observations.
- compare_regional_activity.
- get_historical_calendar.
- get_anomaly_details.
- get_sensor_breakdown.
- find_nearby_assets.
- generate_regional_report.
- explain_harmonization_match.

The assistant must:

1. Understand the user's geographic and temporal request.
2. Call the appropriate analytical functions.
3. Retrieve actual application results.
4. Explain the results.
5. Cite observation periods and data sources.
6. Disclose uncertainty and limitations.
7. Offer links to the relevant application views.

Example questions:

- Which countries have the highest recorded fire activity this month?
- Compare Nigeria's 2024 and 2026 fire activity.
- Which regions have unusually high activity for this season?
- Show probable MODIS/VIIRS matches around this location.
- Which settlements are within five kilometres of these detections?
- Generate a regional fire intelligence report.

The assistant must not invent statistics, coordinates, source records or fire classifications.

Treat external data and retrieved text as untrusted input.

---

# PART 15 — REPORTING AND EXPORTS

Implement report templates for:

- Global fire activity.
- Country-level fire activity.
- Regional intelligence.
- Historical seasonal analysis.
- Sensor comparison.
- Harmonization quality.
- Anomaly investigation.
- Exposure screening.

Support:

- PDF.
- CSV.
- GeoJSON.
- JSON.

Every report must include:

- Generation timestamp.
- Selected geographic area.
- Selected observation period.
- Data sources.
- Data processing versions.
- Methodology.
- Statistical limitations.
- Relevant observation identifiers.

Use background workers for large report generation.

---

# PART 16 — ALERTS AND NOTIFICATIONS

Implement user-configurable alerts.

Alert triggers:

- Unusual regional activity.
- Daily activity threshold.
- Elevated FRP.
- New anomaly.
- New observations in a saved region.
- Data ingestion failure.

Support in-app notifications initially.

Design the notification service to allow future email and webhook integrations.

Never send an alert that implies a confirmed emergency based only on an unverified satellite hotspot.

---

# PART 17 — API IMPLEMENTATION

Implement REST APIs under:

/api/v1

Required API groups:

- /dashboard
- /fires
- /calendar
- /harmonization
- /anomalies
- /regions
- /exposure
- /reports
- /assistant
- /admin
- /auth

Use Pydantic request and response models.

Implement pagination, filters, validation, structured errors, rate limiting and access controls.

Generate OpenAPI documentation automatically.

Provide an API health endpoint and readiness endpoint.

---

# PART 18 — SECURITY

Implement:

- Argon2id password hashing.
- Secure authentication.
- Role-based access control.
- Optional MFA.
- Secure sessions.
- Rate limiting.
- CORS restrictions.
- Input validation.
- SQL injection prevention.
- Secure file handling.
- Audit logging.
- Secrets management.
- Secure HTTP headers.
- Backup and recovery.

Roles:

ADMIN, ANALYST, RESEARCHER, VIEWER.

Ensure that only authorized users can trigger expensive historical ingestion and administrative processing jobs.

---

# PART 19 — TESTING AND SCIENTIFIC VALIDATION

Create automated tests.

Backend tests:

- FIRMS API client.
- Source adapters.
- Data normalization.
- Timestamp conversion.
- Coordinate validation.
- Deduplication.
- Harmonization.
- Event grouping.
- Calendar aggregation.
- Baseline calculation.
- Anomaly detection.
- Spatial queries.
- Report generation.

Frontend tests:

- Navigation.
- Filters.
- Map interactions.
- Calendar interactions.
- Charts.
- Hotspot inspection.
- Report generation.
- Authentication.
- Responsive layouts.

Integration tests:

- NASA API integration.
- Database persistence.
- Background ingestion.
- Geospatial querying.
- AI tool calls.
- Export generation.

Scientific validation:

- Compare output totals against source records.
- Verify geographic calculations.
- Verify UTC handling.
- Test missing data.
- Test sensor-specific confidence handling.
- Validate FRP units.
- Evaluate match precision and recall using carefully curated reference cases.
- Backtest anomaly detection.
- Test forecast performance against seasonal baselines.

Use synthetic test fixtures for edge cases, but never represent synthetic fixtures as actual NASA observations.

---

# PART 20 — PERFORMANCE

The system must support progressive growth.

Test at:

- 100,000 records.
- 1 million records.
- 10 million records.
- Larger datasets as resources permit.

Implement:

- Viewport-based map queries.
- Spatial indexes.
- Background processing.
- Query pagination.
- Redis caching.
- Precomputed calendar aggregates.
- Efficient bulk inserts.
- Database partitioning when justified.

Do not load the complete global historical database into the frontend.

Measure and document actual performance rather than inventing benchmarks.

---

# PART 21 — DEPLOYMENT

Create:

- Dockerfile for frontend.
- Dockerfile for backend.
- Docker configuration for workers.
- Docker Compose.
- PostgreSQL/PostGIS configuration.
- Redis configuration.
- Environment template.
- Database migrations.
- Seed scripts.
- CI/CD configuration.
- Health checks.
- Backup scripts.
- Deployment documentation.

Use Cloudflare Pages or an equivalent static frontend host.

Deploy the backend and persistent workers to an environment that supports Python applications and long-running jobs.

Use managed PostgreSQL with PostGIS where possible.

Do not place long-running ingestion tasks inside short-lived serverless request functions.

---

# PART 22 — DOCUMENTATION

Produce:

README.md:

- Product introduction.
- Screenshots.
- Features.
- Technology stack.
- Installation.
- Configuration.
- Development commands.
- Deployment.

docs/architecture.md:

- Application architecture.
- Service responsibilities.
- Data flow.

docs/api.md:

- API documentation.
- Authentication.
- Example requests.

docs/data_dictionary.md:

- Database tables.
- Field definitions.
- Source-specific schemas.

docs/methodology.md:

- Normalization.
- Harmonization.
- Event grouping.
- Calendar calculations.
- Anomaly detection.

docs/scientific_validation.md:

- Validation methodology.
- Test datasets.
- Evaluation results.
- Known limitations.

docs/deployment.md:

- Production deployment.
- Environment variables.
- Database setup.
- Worker setup.
- Backup and restoration.

docs/user_guide.md:

- Dashboard navigation.
- Map usage.
- Calendar analysis.
- Regional investigation.
- Report generation.
- AI assistant.

---

# PART 23 — IMPLEMENTATION ORDER

Build the project in the following sequence.

PHASE 1 — Foundation

- Inspect repository.
- Set up frontend and backend.
- Configure database.
- Configure Docker.
- Establish design system.
- Create application navigation.

PHASE 2 — NASA Integration

- Implement FIRMS client.
- Configure MAP_KEY.
- Implement source adapters.
- Implement ingestion workers.
- Create raw and normalized observation storage.

PHASE 3 — Harmonization

- Implement sensor normalization.
- Implement cross-sensor candidate matching.
- Implement quality controls.
- Implement event grouping.
- Create harmonization inspection interface.

PHASE 4 — Main User Experience

- Implement global map.
- Implement filters.
- Implement hotspot inspection.
- Implement geographic search.

PHASE 5 — Historical Calendar

- Implement daily aggregation.
- Implement annual calendar.
- Implement monthly heatmaps.
- Implement seasonal comparisons.
- Implement calendar drill-down.

PHASE 6 — Intelligence

- Implement regional analytics.
- Implement historical baselines.
- Implement anomaly detection.
- Implement exposure screening.

PHASE 7 — AI and Reports

- Implement AI analytical tools.
- Implement conversational interface.
- Implement report generation.
- Implement notifications.

PHASE 8 — Validation

- Execute tests.
- Validate data provenance.
- Backtest analytical methods.
- Perform performance testing.
- Fix defects.

PHASE 9 — Deployment

- Configure production services.
- Deploy frontend.
- Deploy backend.
- Deploy workers.
- Configure monitoring.
- Run smoke tests.

Do not move to the next phase with critical defects in the preceding phase.

---

# PART 24 — ACCEPTANCE CRITERIA

The application is not complete until all of the following are demonstrated.

1. A user can access the deployed application.
2. The application connects to NASA FIRMS using a backend-stored MAP_KEY.
3. MODIS and VIIRS observations are retrieved from real source products.
4. Data are stored persistently.
5. Duplicate ingestion is prevented.
6. Historical ingestion is resumable.
7. Sensor records are normalized without losing source provenance.
8. Cross-sensor matching produces inspectable associations.
9. The global map displays genuine satellite observations.
10. Users can filter by date, source and geography.
11. Users can select a geographic region.
12. The burning activity calendar displays historical observations.
13. Calendar values reconcile with the underlying selected metric.
14. Missing data are distinguishable from zero detections.
15. Historical trends are calculated from actual records.
16. Anomaly detection provides evidence and baseline information.
17. Regional analysis works for multiple countries.
18. Exposure analysis calculates geographic distances.
19. The AI assistant retrieves real application data.
20. Reports can be generated and downloaded.
21. API documentation is accessible.
22. Automated tests pass.
23. The application is responsive.
24. Deployment and installation documentation is complete.
25. Scientific limitations and NASA attribution are visible.

---

# PART 25 — HACKATHON PRESENTATION

Prepare a working demonstration lasting approximately five minutes.

Demonstration sequence:

1. Open the global fire intelligence dashboard.
2. Show genuine NASA FIRMS detections.
3. Filter the map to Nigeria.
4. Switch between MODIS and VIIRS.
5. Open the historical burning activity calendar.
6. Compare two historical periods.
7. Inspect a probable cross-sensor match.
8. Open the anomaly detection module.
9. Select an unusual regional activity result.
10. Ask the AI assistant to explain the result.
11. Generate and download a regional intelligence report.

The presentation must demonstrate the actual application, not slides pretending to be functional features.

Prepare:

- Product pitch.
- Problem statement.
- Solution overview.
- Technical architecture.
- Scientific methodology.
- Live demonstration.
- Impact statement.
- Future development roadmap.

Clearly communicate that NASA thermal anomalies are detections, not confirmed fire boundaries or guaranteed wildfire identifications.

---

# FINAL DEVELOPMENT INSTRUCTIONS

Start by inspecting the repository and establishing the actual state of the project.

Then produce a concise implementation plan and begin coding.

Do not stop after generating a plan, documentation or mockups.

Build the working frontend, backend, database, data integrations, processing engine, APIs and tests.

Do not substitute static sample charts for working analytical queries.

Do not invent NASA API responses, observation counts, historical statistics or successful ingestion status.

When API credentials are missing, implement the integration completely, document the required credential and provide a clearly labelled setup state. Do not pretend that live data have been retrieved.

When external APIs are unavailable during development, use explicitly labelled synthetic test fixtures and keep them isolated from production data.

Implement features incrementally and verify them before continuing.

At the end, provide:

1. Completed feature list.
2. Repository structure.
3. Installation instructions.
4. Required environment variables.
5. Database migration instructions.
6. NASA MAP_KEY configuration instructions.
7. Local development commands.
8. Test results.
9. Deployment instructions.
10. Known limitations.
11. Remaining work, if any.
12. A demonstration script.

The final deliverable must be a functioning, documented, tested and deployable FIREWATCH X platform.

## 15. What you need before development starts

There are only a few external requirements to prepare.

1\. NASA FIRMS MAP_KEY

Free

Register here: [Request NASA FIRMS API key](https://firms.modaps.eosdis.nasa.gov/api/map_key/?utm_source=chatgpt.com)

This is essential for retrieving real fire observations.

2\. PostgreSQL + PostGIS

Set up a spatial database for observations, regions, matches and historical analytics.

[PostGIS documentation](https://postgis.net/?utm_source=chatgpt.com)

3\. Hosting

Frontend hosting, Python backend hosting, persistent PostgreSQL and background workers.

4\. AI provider

Optional initially. The platform's statistical intelligence must work even without an LLM.

## 16. My recommended implementation strategy

Do not ask your coding agent to build all ten modules simultaneously. Use the master prompt as the project specification, then implement in controlled stages.

## First working milestone

Build this first

A functioning NASA fire intelligence pipeline

1. Retrieve actual MODIS observations.
2. Retrieve actual VIIRS observations.
3. Store both in PostgreSQL.
4. Display both on MapLibre.
5. Filter observations by country and date.
6. Display the historical burning calendar.
7. Compare sensor activity.

Second milestone

Add cross-sensor matching, anomaly detection, regional analytics and reporting.

Third milestone

Add AI assistance, exposure analysis, alerts and advanced intelligence.

### Important implementation consideration

NASA's FIRMS API has request limits, and historical ingestion must be carefully scheduled. Its area endpoint accepts up to five days per request, and large global queries can return substantial volumes of records. Use incremental ingestion and persistent job checkpoints rather than attempting to download the entire historical dataset at once.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firms.modaps.eosdis.nasa.gov\&sz=32)

FIRMS+2



Also display NASA's active-fire data disclaimer prominently: satellite detections are thermal anomalies, may have false positives and can be obscured by cloud cover. They are not intended as the sole basis for protecting life or property.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://firms.modaps.eosdis.nasa.gov\&sz=32)

FIRMS



## 17. Definition of success

I would consider FIREWATCH X a successful hackathon submission when we can demonstrate this complete workflow:

## The FIREWATCH X discovery workflow

1. NASA satellite detects thermal anomalies.
2. FIREWATCH X retrieves the observations.
3. MODIS and VIIRS records are normalized.
4. Potential cross-sensor matches are identified.
5. Historical activity is visualized on a calendar.
6. Statistical intelligence identifies unusual activity.
7. Researchers investigate the geographic evidence.
8. AI explains the results and generates a report.

End-to-end demonstrable product

My strongest recommendation: Make the MODIS–VIIRS harmonization engine and historical burning activity calendar the two features you perfect first. They directly address the challenge, demonstrate genuine engineering and give FIREWATCH X a stronger scientific identity than another generic AI-powered wildfire dashboard.