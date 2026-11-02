"""Documented fire events used to validate the platform against reality.

Each entry names a real event with an independent public source, a centre, a
radius and the period it was reported in. The validation script analyses the
radius with the regional engine and checks the qualitative claim (for example,
"activity rose sharply in October") against the stored FIRMS detections.

These are validation references, not training labels: nothing here feeds the
anomaly or trend logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ReferenceFire:
    key: str
    name: str
    country: str
    latitude: float
    longitude: float
    radius_km: float
    start: date
    end: date
    expected: str
    sources: tuple[str, ...]
    note: str = ""

    @property
    def slug(self) -> str:
        return f"reference-{self.key}"


REFERENCE_FIRES: tuple[ReferenceFire, ...] = (
    ReferenceFire(
        key="amazon-para-2026",
        name="Amazon fires, eastern Pará",
        country="Brazil",
        latitude=-3.0,
        longitude=-54.0,
        radius_km=250.0,
        start=date(2026, 9, 1),
        end=date(2026, 10, 31),
        expected=(
            "Sharp increase in fire activity from September 2026, with October "
            "activity above September in the eastern Amazon."
        ),
        sources=(
            "https://science.nasa.gov/earth/earth-observatory/fires-arrive-in-the-amazon-rainforest/",
            "https://www.reuters.com/business/environment/fires-surge-brazils-amazon-fueled-by-el-nio-climate-change-2026-10-14/",
        ),
        note="NASA Earth Observatory and Reuters reported the September–October 2026 surge.",
    ),
    ReferenceFire(
        key="kalimantan-2026",
        name="Central Kalimantan fires",
        country="Indonesia",
        latitude=-3.0,
        longitude=114.0,
        radius_km=250.0,
        start=date(2026, 9, 1),
        end=date(2026, 10, 31),
        expected=(
            "Widespread hotspots across Kalimantan in September–October 2026, "
            "with a state of emergency declared for fire and drought."
        ),
        sources=(
            "https://www.iqair.com/newsroom/wildfire-map-spotlight-indonesia-forest-and-peatland-fires-september-2026",
            "https://www.reuters.com/business/environment/indonesias-fire-hotspots-ease-rain-still-not-enough-official-says-2026-10-22/",
        ),
        note="Providers reported thousands of hotspots and emergency status in Kalimantan.",
    ),
)


def get_reference_fire(key: str) -> ReferenceFire:
    for fire in REFERENCE_FIRES:
        if fire.key == key:
            return fire
    raise KeyError(key)
