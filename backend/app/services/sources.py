"""NASA FIRMS source catalogue.

These are the *only* supported products in the first release. The registry is
shared by the ingestion layer (Phase 2), the API and the UI so that source
codes cannot drift between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProcessingLevel = Literal["SP", "NRT"]


@dataclass(frozen=True)
class FirmsSource:
    code: str
    sensor: Literal["MODIS", "VIIRS"]
    satellite: str
    processing_level: ProcessingLevel
    description: str

    @property
    def is_standard_processing(self) -> bool:
        return self.processing_level == "SP"


FIRMS_SOURCES: tuple[FirmsSource, ...] = (
    FirmsSource(
        code="MODIS_SP",
        sensor="MODIS",
        satellite="Terra/Aqua",
        processing_level="SP",
        description="MODIS Collection 61 standard processing (historical analysis).",
    ),
    FirmsSource(
        code="VIIRS_SNPP_SP",
        sensor="VIIRS",
        satellite="Suomi-NPP",
        processing_level="SP",
        description="VIIRS 375 m standard processing (historical analysis).",
    ),
    FirmsSource(
        code="VIIRS_NOAA20_SP",
        sensor="VIIRS",
        satellite="NOAA-20",
        processing_level="SP",
        description="VIIRS 375 m standard processing (historical analysis).",
    ),
    FirmsSource(
        code="VIIRS_NOAA21_SP",
        sensor="VIIRS",
        satellite="NOAA-21",
        processing_level="SP",
        description="VIIRS 375 m standard processing (historical analysis).",
    ),
    FirmsSource(
        code="MODIS_NRT",
        sensor="MODIS",
        satellite="Terra/Aqua",
        processing_level="NRT",
        description="MODIS near-real-time (operational monitoring).",
    ),
    FirmsSource(
        code="VIIRS_SNPP_NRT",
        sensor="VIIRS",
        satellite="Suomi-NPP",
        processing_level="NRT",
        description="VIIRS 375 m near-real-time (operational monitoring).",
    ),
    FirmsSource(
        code="VIIRS_NOAA20_NRT",
        sensor="VIIRS",
        satellite="NOAA-20",
        processing_level="NRT",
        description="VIIRS 375 m near-real-time (operational monitoring).",
    ),
    FirmsSource(
        code="VIIRS_NOAA21_NRT",
        sensor="VIIRS",
        satellite="NOAA-21",
        processing_level="NRT",
        description="VIIRS 375 m near-real-time (operational monitoring).",
    ),
)

FIRMS_SOURCES_BY_CODE: dict[str, FirmsSource] = {s.code: s for s in FIRMS_SOURCES}

SP_SOURCES = tuple(s.code for s in FIRMS_SOURCES if s.is_standard_processing)
NRT_SOURCES = tuple(s.code for s in FIRMS_SOURCES if not s.is_standard_processing)


def get_source(code: str) -> FirmsSource | None:
    return FIRMS_SOURCES_BY_CODE.get(code)


def source_payload(source: FirmsSource) -> dict[str, str | bool]:
    return {
        "code": source.code,
        "sensor": source.sensor,
        "satellite": source.satellite,
        "processing_level": source.processing_level,
        "description": source.description,
    }
