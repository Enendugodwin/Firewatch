"""Geodesic helpers.

Distances are computed on the WGS84 mean sphere, which is accurate to ~0.5% for
the tens-of-kilometres scale used here and avoids a heavy projection dependency.
Pixel footprints are approximated as circles from the reported scan/track
extents, which is a screening value, not a rigorous footprint overlap.
"""

from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def haversine_m_array(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Vectorised great-circle distance in metres."""
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = phi2 - phi1
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def footprint_radius_km(scan_km: float | None, track_km: float | None) -> float | None:
    """Equivalent circle radius for a rectangular pixel footprint."""
    if not scan_km or not track_km or scan_km <= 0 or track_km <= 0:
        return None
    return math.sqrt(scan_km * track_km) / 2.0


def footprint_overlap(
    distance_m: float,
    scan_a: float | None,
    track_a: float | None,
    scan_b: float | None,
    track_b: float | None,
) -> float | None:
    """
    Overlap score in [0, 1] for two circular footprint approximations.

    Returns ``None`` when either footprint is unknown — the caller then
    redistributes the footprint weight instead of inventing a value.
    """
    radius_a = footprint_radius_km(scan_a, track_a)
    radius_b = footprint_radius_km(scan_b, track_b)
    if radius_a is None or radius_b is None:
        return None
    combined = (radius_a + radius_b) * 1000.0
    if combined <= 0:
        return None
    return max(0.0, min(1.0, 1.0 - distance_m / combined))
