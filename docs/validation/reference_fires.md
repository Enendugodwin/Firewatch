# Reference fire validation

Measured against the stored FIRMS detections with the regional engine. Each fire is a radius region analysed for the period it was reported in. Counts are detections, not fires.

Generated: 2026-11-02

## Amazon fires, eastern Pará — Brazil

- Centre: -3.000, -54.000 · radius 250 km
- Period: 2026-09-01 → 2026-10-31
- Region id: `1e443817-6f59-5f13-9876-fc0a3c6153c0`
- Sources: https://science.nasa.gov/earth/earth-observatory/fires-arrive-in-the-amazon-rainforest/, https://www.reuters.com/business/environment/fires-surge-brazils-amazon-fueled-by-el-nio-climate-change-2026-10-14/

**Result: PASS**

| Check | Result | Measurement |
| --- | --- | --- |
| detections present | pass | 161,066 detections in 250 km radius |
| sustained activity | pass | 60 active days |
| intense detections | pass | peak daily FRP 2467.4 MW |
| October activity above September | pass | Sep 20,227 → Oct 140,839 |

- Detections: **161,066** over 60 active days
- Peak day: **2026-10-08** with 9,314 detections
- Peak daily FRP: **2467.4 MW**
- 2026-09: 20,227 detections (97% coverage)
- 2026-10: 140,839 detections (100% coverage)

_Sharp increase in fire activity from September 2026, with October activity above September in the eastern Amazon._

NASA Earth Observatory and Reuters reported the September–October 2026 surge.

## Central Kalimantan fires — Indonesia

- Centre: -3.000, 114.000 · radius 250 km
- Period: 2026-09-01 → 2026-10-31
- Region id: `1bcaef19-c1ee-5617-8b24-60b37eb2cb78`
- Sources: https://www.iqair.com/newsroom/wildfire-map-spotlight-indonesia-forest-and-peatland-fires-september-2026, https://www.reuters.com/business/environment/indonesias-fire-hotspots-ease-rain-still-not-enough-official-says-2026-10-22/

**Result: PASS**

| Check | Result | Measurement |
| --- | --- | --- |
| detections present | pass | 449,994 detections in 250 km radius |
| sustained activity | pass | 60 active days |
| intense detections | pass | peak daily FRP 835.6 MW |

- Detections: **449,994** over 60 active days
- Peak day: **2026-10-22** with 29,456 detections
- Peak daily FRP: **835.6 MW**
- 2026-09: 216,530 detections (97% coverage)
- 2026-10: 233,464 detections (100% coverage)

_Widespread hotspots across Kalimantan in September–October 2026, with a state of emergency declared for fire and drought._

Providers reported thousands of hotspots and emergency status in Kalimantan.

## Limitations

- A radius is a screening area; the reported event may not fill it and other fires may fall inside it.
- FIRMS detections are thermal anomalies, not a fire perimeter or a damage estimate.
- The comparison is qualitative. A PASS shows the platform reproduces the reported activity; it is not an accuracy score against burned area.
