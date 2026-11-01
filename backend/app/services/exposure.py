"""Watched assets and proximity screening.

Exposure analysis usually needs population and infrastructure layers this
deployment does not ship. Rather than invent them, the platform screens against
assets the user explicitly registers: "which of my places had detections nearby?"
That is a real, checkable answer with no external dataset.
"""

from __future__ import annotations

import math
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FireObservation, WatchedAsset
from app.services.observation_queries import ObservationFilters

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def list_assets(session: Session) -> list[WatchedAsset]:
    return list(session.scalars(select(WatchedAsset).order_by(WatchedAsset.name)).all())


def screen_assets(
    session: Session,
    filters: ObservationFilters,
    *,
    radius_km: float = 50.0,
    max_assets: int = 200,
    max_observations: int = 20000,
) -> dict[str, Any]:
    assets = list_assets(session)[:max_assets]
    observations = list(
        session.scalars(
            filters.apply(select(FireObservation)).execution_options(stream_results=True)
        ).all()[:max_observations]
    )

    results = []
    for asset in assets:
        nearby = []
        nearest: dict[str, Any] | None = None
        for row in observations:
            distance = haversine_km(asset.latitude, asset.longitude, row.latitude, row.longitude)
            if distance > radius_km:
                continue
            nearby.append((distance, row))
            if nearest is None or distance < nearest["distance_km"]:
                nearest = {
                    "distance_km": round(distance, 2),
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "acquired_at": row.acquired_at,
                    "frp_mw": row.frp_mw,
                    "sensor": row.sensor,
                }

        frp_values = [row.frp_mw for _, row in nearby if row.frp_mw is not None]
        results.append(
            {
                "asset_id": str(asset.id),
                "name": asset.name,
                "category": asset.category,
                "latitude": asset.latitude,
                "longitude": asset.longitude,
                "detections_within_radius": len(nearby),
                "frp_sum_mw": round(sum(frp_values), 2) if frp_values else 0.0,
                "frp_max_mw": round(max(frp_values), 2) if frp_values else None,
                "nearest": nearest,
            }
        )

    results.sort(
        key=lambda item: int(item["detections_within_radius"]),  # type: ignore[arg-type]
        reverse=True,
    )
    return {
        "assets": results,
        "asset_count": len(assets),
        "radius_km": radius_km,
        "observations_scanned": len(observations),
        "truncated": len(observations) >= max_observations,
        "note": (
            "Screening uses the assets registered here. No population or infrastructure "
            "dataset is bundled, so this is proximity to detections, not a risk score."
        ),
    }


def create_asset(
    session: Session,
    *,
    name: str,
    latitude: float,
    longitude: float,
    category: str | None = None,
) -> WatchedAsset:
    asset = WatchedAsset(
        id=uuid.uuid4(),
        name=name.strip()[:120],
        latitude=latitude,
        longitude=longitude,
        category=(category or "unspecified")[:48],
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def delete_asset(session: Session, asset_id: str) -> bool:
    try:
        parsed = uuid.UUID(asset_id)
    except ValueError:
        return False
    asset = session.get(WatchedAsset, parsed)
    if asset is None:
        return False
    session.delete(asset)
    session.commit()
    return True


def asset_counts(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(WatchedAsset)) or 0)


def window_days(start: date, end: date) -> int:
    return (end - start).days + 1
