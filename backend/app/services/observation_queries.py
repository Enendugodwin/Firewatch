"""Observation query helpers shared by the fires, dashboard and harmonization APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    FireEvent,
    FireObservation,
    ObservationMatch,
)

#: Categories at or above each minimum. Unknown categories are never upgraded.
CONFIDENCE_LADDER: dict[str, tuple[str, ...]] = {
    "low": ("low", "nominal", "high"),
    "nominal": ("nominal", "high"),
    "high": ("high",),
}


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def as_list(self) -> list[float]:
        """Serialisable form, used when recording an analysis scope."""
        return [self.west, self.south, self.east, self.north]

    @classmethod
    def parse(cls, value: str) -> BBox:
        parts = [piece.strip() for piece in value.split(",")]
        if len(parts) != 4:
            raise AppError(
                "bad_request",
                "bbox must be four comma-separated numbers: west,south,east,north.",
                details={"received": value},
            )
        try:
            west, south, east, north = (float(part) for part in parts)
        except ValueError as exc:
            raise AppError("bad_request", "bbox contains a non-numeric value.") from exc
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise AppError(
                "bad_request",
                "bbox is out of range or inverted.",
                details={"west": west, "south": south, "east": east, "north": north},
            )
        return cls(west, south, east, north)


@dataclass(frozen=True)
class ObservationFilters:
    bbox: BBox | None = None
    start_date: date | None = None
    end_date: date | None = None
    sensor: str | None = None
    satellite: str | None = None
    min_frp: float | None = None
    daynight: str | None = None
    min_confidence: str | None = None
    synthetic: bool | None = None

    def apply(self, stmt: Select) -> Select:
        if self.bbox is not None:
            stmt = stmt.where(
                FireObservation.longitude >= self.bbox.west,
                FireObservation.longitude <= self.bbox.east,
                FireObservation.latitude >= self.bbox.south,
                FireObservation.latitude <= self.bbox.north,
            )
        if self.start_date is not None:
            start = datetime.combine(self.start_date, datetime.min.time(), tzinfo=UTC)
            stmt = stmt.where(FireObservation.acquired_at >= start)
        if self.end_date is not None:
            end = datetime.combine(
                self.end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
            )
            stmt = stmt.where(FireObservation.acquired_at < end)
        if self.sensor:
            stmt = stmt.where(FireObservation.sensor == self.sensor.upper())
        if self.satellite:
            stmt = stmt.where(FireObservation.satellite == self.satellite)
        if self.min_frp is not None:
            stmt = stmt.where(FireObservation.frp_mw >= self.min_frp)
        if self.daynight:
            stmt = stmt.where(FireObservation.daynight == self.daynight.upper()[:1])
        if self.min_confidence:
            allowed = CONFIDENCE_LADDER.get(self.min_confidence.lower())
            if allowed:
                stmt = stmt.where(FireObservation.confidence_category.in_(allowed))
        if self.synthetic is not None:
            stmt = stmt.where(FireObservation.is_synthetic.is_(self.synthetic))
        return stmt


def search_observations(
    session: Session,
    filters: ObservationFilters,
    *,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[FireObservation], int]:
    # Count on the bare table: wrapping a full-column select in a subquery makes
    # SQLite materialise every row before counting, which is seconds on 100k+.
    total = (
        session.scalar(filters.apply(select(func.count()).select_from(FireObservation))) or 0
    )
    rows = session.scalars(
        filters.apply(select(FireObservation))
        .order_by(FireObservation.acquired_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), int(total)


def sensor_counts(session: Session, *, synthetic: bool | None = None) -> dict[str, int]:
    stmt = select(FireObservation.sensor, func.count()).group_by(FireObservation.sensor)
    if synthetic is not None:
        stmt = stmt.where(FireObservation.is_synthetic.is_(synthetic))
    return {sensor: int(count) for sensor, count in session.execute(stmt).all()}


def match_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(ObservationMatch.match_status, func.count()).group_by(ObservationMatch.match_status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    counts["total"] = sum(counts.values())
    return counts


def event_stats(session: Session) -> tuple[int, int]:
    total = session.scalar(select(func.count()).select_from(FireEvent)) or 0
    multi = (
        session.scalar(
            select(func.count()).select_from(FireEvent).where(FireEvent.sensor_count > 1)
        )
        or 0
    )
    return int(total), int(multi)


def observation_to_dict(row: FireObservation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_code": row.source_code,
        "source_record_id": row.source_record_id,
        "sensor": row.sensor,
        "satellite": row.satellite,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "acquired_at": row.acquired_at,
        "confidence_raw": row.confidence_raw,
        "confidence_category": row.confidence_category,
        "brightness_temperature": row.brightness_temperature,
        "brightness_channel": row.brightness_channel,
        "frp_mw": row.frp_mw,
        "scan_km": row.scan_km,
        "track_km": row.track_km,
        "daynight": row.daynight,
        "processing_version": row.processing_version,
        "source_product": row.source_product,
        "quality_flags": row.quality_flags or {},
        "is_synthetic": row.is_synthetic,
    }
