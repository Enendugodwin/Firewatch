"""Geographic regions and their materialised regional statistics.

Boundaries are stored as GeoJSON because the portable PostgreSQL build has no
PostGIS. A bounding box is kept alongside for SQL prefiltering; it is only a
candidate filter — every published count is computed against the actual polygon.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JsonType, TimestampMixin, UUIDPrimaryKeyMixin


class GeographicRegion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A selectable analysis boundary.

    ``boundary_kind`` says how much the polygon can be trusted: ``polygon`` is an
    imported or user-drawn boundary, ``circle`` a radius buffer, and ``bbox`` a
    gazetteer rectangle that is explicitly approximate.
    """

    __tablename__ = "geographic_regions"

    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")
    boundary_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="polygon")
    geometry: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False)
    bbox_west: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_south: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_east: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_north: Mapped[float] = mapped_column(Float, nullable=False)
    area_km2: Mapped[float | None] = mapped_column(Float)
    vertices: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boundary_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="custom")
    is_approximate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_analysis_algorithm: Mapped[str | None] = mapped_column(String(48))

    statistics: Mapped[list[RegionalDailyStatistic]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_geographic_regions_level", "level"),
        Index("ix_geographic_regions_name", "name"),
    )


class RegionalDailyStatistic(UUIDPrimaryKeyMixin, Base):
    """
    One region × day × sensor. ``ALL`` is the combined row.

    A day with no row means the day was outside the analysed range or the region
    had no observed coverage; the analysis run records which. It is never written
    as an implicit zero for an unobserved day.
    """

    __tablename__ = "regional_daily_statistics"

    region_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("geographic_regions.id", ondelete="CASCADE"), nullable=False
    )
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    sensor: Mapped[str] = mapped_column(String(16), nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frp_sum_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    frp_max_mw: Mapped[float | None] = mapped_column(Float)
    high_confidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    region: Mapped[GeographicRegion] = relationship(back_populates="statistics")

    __table_args__ = (
        UniqueConstraint(
            "region_id", "activity_date", "sensor", name="uq_regional_daily_region_day_sensor"
        ),
        Index("ix_regional_daily_region_date", "region_id", "activity_date"),
    )


class RegionalCellStatistic(UUIDPrimaryKeyMixin, Base):
    """
    Recurring-activity grid inside a region (0.5° cells).

    H3 is not installed in this deployment, so the grid is a plain equirectangular
    cell index. Every cell is labelled with its resolution; it is a screening grid,
    not an H3 index.
    """

    __tablename__ = "regional_cell_statistics"

    region_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("geographic_regions.id", ondelete="CASCADE"), nullable=False
    )
    lat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lon_index: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frp_sum_mw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    frp_max_mw: Mapped[float | None] = mapped_column(Float)
    years_with_detections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_year: Mapped[int | None] = mapped_column(Integer)
    last_year: Mapped[int | None] = mapped_column(Integer)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "region_id", "lat_index", "lon_index", name="uq_regional_cell_region_cell"
        ),
        Index("ix_regional_cell_region", "region_id"),
    )
