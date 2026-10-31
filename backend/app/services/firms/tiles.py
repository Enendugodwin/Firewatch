"""Spatial tiles and date windows for resumable ingestion.

The FIRMS area endpoint accepts one to five days per request and warns that a
global VIIRS request can return tens of thousands of records per day. Historical
backfills therefore work in (tile, date window) partitions that can be retried
and resumed independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.firms.client import MAX_DAY_RANGE


@dataclass(frozen=True)
class Tile:
    key: str
    west: float
    south: float
    east: float
    north: float

    @property
    def bbox(self) -> str:
        """FIRMS area coordinate order: west,south,east,north."""
        return f"{self.west},{self.south},{self.east},{self.north}"


WORLD = Tile("world", -180.0, -90.0, 180.0, 90.0)


def global_tiles(lon_step: int = 30, lat_step: int = 20) -> list[Tile]:
    """Deterministic global tiling (default 12 × 9 = 108 tiles)."""
    if not (1 <= lon_step <= 180 and 1 <= lat_step <= 90):
        raise ValueError("Tile steps must be positive and divide the globe sensibly.")
    tiles: list[Tile] = []
    for west in range(-180, 180, lon_step):
        for south in range(-90, 90, lat_step):
            tiles.append(
                Tile(
                    key=f"t_{west:+04d}_{south:+03d}",
                    west=float(west),
                    south=float(south),
                    east=float(min(west + lon_step, 180)),
                    north=float(min(south + lat_step, 90)),
                )
            )
    return tiles


def tile_for_point(lat: float, lon: float, lon_step: int = 30, lat_step: int = 20) -> Tile:
    """Look up the tile containing a coordinate (used for provenance checks)."""
    west = int((lon // lon_step) * lon_step)
    south = int((lat // lat_step) * lat_step)
    return Tile(
        key=f"t_{west:+04d}_{south:+03d}",
        west=float(west),
        south=float(south),
        east=float(min(west + lon_step, 180)),
        north=float(min(south + lat_step, 90)),
    )


def date_windows(start: date, end: date, max_days: int = MAX_DAY_RANGE) -> list[tuple[date, date]]:
    """Split an inclusive date range into windows the API accepts."""
    if end < start:
        raise ValueError("end must not be before start")
    if not 1 <= max_days <= MAX_DAY_RANGE:
        raise ValueError(f"max_days must be between 1 and {MAX_DAY_RANGE}")

    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=max_days - 1), end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def window_days(start: date, end: date) -> int:
    return (end - start).days + 1
