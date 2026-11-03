"""Regional historical backfill planning.

The FIRMS area API serves the full standard-processing archive (MODIS from
2000-11-01, VIIRS from 2012-01-20) but only five days per request, so a decade of
history is thousands of bounded requests. A *global* multi-year backfill is not
practical on a workstation (hundreds of millions of rows), so the historical
archive is built for a small, documented set of fire regions instead. The region
covered by a backfill is recorded on every ingestion partition, and the calendar
marks days outside it as ``unobserved`` rather than ``quiet``.

This module holds the region catalogue and the pure planning helpers; the
runner lives in ``scripts/backfill_history.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.firms.client import AvailabilityWindow
from app.services.firms.tiles import Tile
from app.services.sources import get_source

#: The FIRMS area endpoint accepts at most five days per request.
CHUNK_DAYS = 5


@dataclass(frozen=True)
class HistoricalRegion:
    """A documented fire region used for long-term backfills."""

    key: str
    name: str
    west: float
    south: float
    east: float
    north: float
    note: str

    @property
    def bbox(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"

    @property
    def tile(self) -> Tile:
        # The key is stable, so re-running the same backfill resumes its
        # partitions instead of duplicating work.
        return Tile(f"region:{self.key}", self.west, self.south, self.east, self.north)


REGIONS: dict[str, HistoricalRegion] = {
    "amazon": HistoricalRegion(
        key="amazon",
        name="Amazon arc of deforestation",
        west=-70.0,
        south=-12.0,
        east=-50.0,
        north=2.0,
        note=(
            "Brazilian arc of deforestation and eastern Amazon; validated against "
            "the 2026 Para fires."
        ),
    ),
    "kalimantan": HistoricalRegion(
        key="kalimantan",
        name="Central Kalimantan",
        west=108.0,
        south=-6.0,
        east=120.0,
        north=4.0,
        note="Indonesian peatland fires; validated against the 2026 Kalimantan fires.",
    ),
    "mediterranean": HistoricalRegion(
        key="mediterranean",
        name="Mediterranean basin",
        west=-8.0,
        south=34.0,
        east=30.0,
        north=46.0,
        note="Southern Europe and the Maghreb; summer fire season.",
    ),
    "australia": HistoricalRegion(
        key="australia",
        name="South-east Australia",
        west=138.0,
        south=-40.0,
        east=155.0,
        north=-24.0,
        note="Temperate south-east Australia; December-February fire season.",
    ),
    "california": HistoricalRegion(
        key="california",
        name="California and the south-west",
        west=-124.0,
        south=32.0,
        east=-114.0,
        north=42.0,
        note="Californian chaparral and the south-west; May-November fire season.",
    ),
}

#: The only products that can supply history. NRT coverage is a rolling window.
HISTORY_SOURCES = ("MODIS_SP", "VIIRS_SNPP_SP", "VIIRS_NOAA20_SP", "VIIRS_NOAA21_SP")


def get_region(key: str) -> HistoricalRegion:
    try:
        return REGIONS[key]
    except KeyError as exc:
        raise KeyError(
            f"Unknown historical region {key!r}; choose from {', '.join(sorted(REGIONS))}."
        ) from exc


def resolve_tile(
    *,
    region: str | None = None,
    bbox: str | None = None,
    name: str = "custom",
) -> Tile:
    """A tile from a catalogue region or a ``west,south,east,north`` string."""
    if region:
        return get_region(region).tile
    if not bbox:
        raise ValueError("Provide --region or --bbox.")
    parts = [part.strip() for part in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("--bbox must be west,south,east,north.")
    west, south, east, north = (float(part) for part in parts)
    if west >= east or south >= north:
        raise ValueError("--bbox must satisfy west<east and south<north.")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("Longitudes must be within -180..180.")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("Latitudes must be within -90..90.")
    return Tile(f"region:{name}", west, south, east, north)


def validate_history_source(code: str) -> bool:
    source = get_source(code)
    return source is not None and source.is_standard_processing


def plan_windows(start: date, end: date, chunk_days: int = CHUNK_DAYS) -> list[tuple[date, date]]:
    """Bounded, ordered windows; every request covers at most five days."""
    if start > end:
        raise ValueError("start must be on or before end")
    size = max(1, min(chunk_days, CHUNK_DAYS))
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=size - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def clamped_window(
    window: AvailabilityWindow, start: date, end: date
) -> tuple[date, date] | None:
    """Intersect a requested window with the coverage FIRMS reports for a product.

    Returns ``None`` when the product has no coverage in the requested period,
    which is different from "no detections in a covered day".
    """
    if window.min_date is None or window.max_date is None:
        # Legacy availability bodies list explicit dates instead of a range.
        covered = sorted(day for day in window.explicit_dates if start <= day <= end)
        if not covered:
            return None
        return covered[0], covered[-1]

    first = max(start, window.min_date)
    last = min(end, window.max_date)
    if first > last:
        return None
    return first, last
