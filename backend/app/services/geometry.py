"""Geographic boundary handling without PostGIS.

The portable PostgreSQL build has no PostGIS, so a region is stored as GeoJSON and
containment is evaluated with Shapely in the application. The database bounding
box is only a **candidate filter**: every published count is computed against the
actual polygon, never against the box.

Supported inputs are GeoJSON ``Polygon``/``MultiPolygon``, a ``Feature`` or a
``FeatureCollection``, a radius buffer, and a rectangle (used for the approximate
gazetteer regions). Longitudes are validated to [-180, 180]; a boundary that
crosses the antimeridian is rejected rather than silently mis-counted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from app.core.errors import AppError

#: Bounds the per-request cost of the exact containment test.
MAX_VERTICES = 50_000
#: Grid used for recurring-activity cells; documented in every response.
CELL_DEGREES = 0.5


@dataclass(frozen=True)
class RegionGeometry:
    """Validated boundary ready for storage and containment tests."""

    geometry: dict[str, Any]
    bbox: tuple[float, float, float, float]  # west, south, east, north
    area_km2: float
    vertices: int

    def to_shape(self) -> BaseGeometry:
        return shape(self.geometry)


def _invalid(message: str, **details: Any) -> AppError:
    return AppError("bad_request", message, details=details or None)


def _coordinate_pairs(coords: Any) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for item in coords:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise _invalid("Boundary coordinates must be [longitude, latitude] pairs.")
        lon, lat = float(item[0]), float(item[1])
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            raise _invalid(
                "Boundary coordinate is outside the valid longitude/latitude range.",
                longitude=lon,
                latitude=lat,
            )
        pairs.append((lon, lat))
    return pairs


def _round(value: float) -> float:
    return round(value, 6)


def _normalise(geometry: BaseGeometry) -> MultiPolygon:
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    if geometry.is_empty:
        raise _invalid("The boundary is empty.")
    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])
    if isinstance(geometry, MultiPolygon):
        return geometry
    # make_valid can return a GeometryCollection when a ring self-intersects.
    if geometry.geom_type == "GeometryCollection":
        polygons = [item for item in geometry.geoms if isinstance(item, (Polygon, MultiPolygon))]
        flattened: list[Polygon] = []
        for item in polygons:
            if isinstance(item, Polygon):
                flattened.append(item)
            else:
                flattened.extend(item.geoms)
        if not flattened:
            raise _invalid("The boundary does not contain a polygon.")
        return MultiPolygon(flattened)
    raise _invalid(
        "Only polygon boundaries are supported (Polygon or MultiPolygon).",
        received=geometry.geom_type,
    )


def _build(polygons: MultiPolygon, *, area_note: bool = True) -> RegionGeometry:
    west, south, east, north = polygons.bounds
    if east - west > 180.0 and west < 0 < east:
        raise _invalid(
            "This boundary appears to cross the antimeridian. Split it into two "
            "regions at 180° so counts are not silently merged."
        )

    coordinates: list[list[list[list[float]]]] = []
    vertices = 0
    for polygon in polygons.geoms:
        rings = []
        for ring in [polygon.exterior, *polygon.interiors]:
            pairs = _coordinate_pairs(list(ring.coords))
            if len(pairs) < 4:
                raise _invalid("Every polygon ring needs at least four points (closed).")
            if pairs[0] != pairs[-1]:
                raise _invalid("Every polygon ring must be closed (first point equals last).")
            vertices += len(pairs)
            rings.append([[_round(lon), _round(lat)] for lon, lat in pairs])
        coordinates.append(rings)
        if vertices > MAX_VERTICES:
            raise _invalid(
                "The boundary has too many vertices for this deployment.",
                max_vertices=MAX_VERTICES,
                vertices=vertices,
            )

    mean_lat = (south + north) / 2.0
    # Planar degrees² scaled at the polygon's mean latitude. Adequate for display
    # and ranking; it is not a geodesic area.
    area_km2 = float(polygons.area) * 111.32 * 110.574 * max(
        math.cos(math.radians(mean_lat)), 0.01
    )

    return RegionGeometry(
        geometry={"type": "MultiPolygon", "coordinates": coordinates},
        bbox=(float(west), float(south), float(east), float(north)),
        area_km2=round(area_km2, 3),
        vertices=vertices,
    )


def parse_boundary(payload: dict[str, Any]) -> RegionGeometry:
    """
    Accept a GeoJSON geometry, Feature or FeatureCollection and return a validated
    MultiPolygon. Anything non-polygonal is rejected with a 400, not coerced.
    """
    if not isinstance(payload, dict) or "type" not in payload:
        raise _invalid("Boundary must be a GeoJSON object with a type.")

    kind = payload["type"]
    if kind == "FeatureCollection":
        features = payload.get("features") or []
        if not features:
            raise _invalid("FeatureCollection contains no features.")
        geometries = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
        if not geometries:
            raise _invalid("FeatureCollection contains no geometries.")
        merged = shapely.union_all(geometries)
        return _build(_normalise(merged))
    if kind == "Feature":
        if not payload.get("geometry"):
            raise _invalid("Feature contains no geometry.")
        return _build(_normalise(shape(payload["geometry"])))
    if kind in {"Polygon", "MultiPolygon"}:
        return _build(_normalise(shape(payload)))
    raise _invalid(
        "Unsupported GeoJSON type; use Polygon, MultiPolygon, Feature or FeatureCollection.",
        received=kind,
    )


def load_boundary(geojson: dict[str, Any]) -> RegionGeometry:
    """Rehydrate a stored boundary, revalidating it on the way out."""
    return parse_boundary(geojson)


def bbox_boundary(
    west: float, south: float, east: float, north: float
) -> RegionGeometry:
    return parse_boundary(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        }
    )


def circle_boundary(latitude: float, longitude: float, radius_km: float) -> RegionGeometry:
    """
    Radius buffer in degrees, corrected for the latitude-dependent longitude
    scale. A radius that would cross a pole is rejected instead of clipped.
    """
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        raise _invalid("Radius centre is outside the valid coordinate range.")
    if not (0.05 <= radius_km <= 2_000.0):
        raise _invalid("Radius must be between 0.05 km and 2000 km.")

    lat_radius = radius_km / 110.574
    if abs(latitude) + lat_radius >= 89.9:
        raise _invalid("This radius would cross a pole; use a smaller radius.")

    lon_radius = radius_km / (111.320 * max(math.cos(math.radians(latitude)), 0.01))
    unit = Point(0.0, 0.0).buffer(1.0, quad_segs=32)
    ellipse = affinity.scale(unit, xfact=lon_radius, yfact=lat_radius, origin=(0.0, 0.0))
    moved = affinity.translate(ellipse, xoff=longitude, yoff=latitude)
    return _build(_normalise(moved))


def mask_points(geometry: BaseGeometry, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Exact point-in-polygon mask for arrays of longitude/latitude."""
    if lons.size == 0:
        return np.zeros(0, dtype=bool)
    return shapely.contains_xy(geometry, lons, lats)


def point_inside(geometry: BaseGeometry, longitude: float, latitude: float) -> bool:
    return bool(shapely.contains_xy(geometry, np.array([longitude]), np.array([latitude]))[0])


def cell_of(latitude: float, longitude: float, size: float = CELL_DEGREES) -> tuple[int, int]:
    """Equirectangular grid index. Documented as a screening grid, not H3."""
    return (
        int(math.floor((latitude + 90.0) / size)),
        int(math.floor((longitude + 180.0) / size)),
    )


def cell_centre(
    lat_index: int, lon_index: int, size: float = CELL_DEGREES
) -> tuple[float, float]:
    return (
        -90.0 + (lat_index + 0.5) * size,
        -180.0 + (lon_index + 0.5) * size,
    )
