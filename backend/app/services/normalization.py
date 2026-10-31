"""Normalization adapters: FIRMS rows → canonical observations.

MODIS and VIIRS differ in field names, confidence semantics and brightness
channels, so each product family has its own adapter. Nothing is coerced into a
false equivalence: original values stay intact and any application-level
interpretation is labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.sources import FirmsSource

ALGORITHM_VERSION = "normalize-v1"

#: MODIS confidence is 0–100. Bands are an application classification, not NASA's.
MODIS_CONFIDENCE_BANDS = ((80, "high"), (30, "nominal"), (0, "low"))

#: VIIRS confidence is categorical.
VIIRS_CONFIDENCE = {"h": "high", "n": "nominal", "l": "low"}

#: FIRMS VIIRS files carry a short satellite code, not a name. MODIS files carry
#: the name already ("Terra"/"Aqua"), so these keys only match the coded values.
VIIRS_SATELLITE_CODES = {
    "N": "Suomi-NPP",
    "1": "NOAA-20",
    "2": "NOAA-21",
    "SNPP": "Suomi-NPP",
    "JPSS1": "NOAA-20",
    "JPSS2": "NOAA-21",
}


def satellite_label(value: str | None) -> str | None:
    """Expand a FIRMS satellite code to its mission name; other values pass through."""
    if value is None:
        return None
    code = value.strip()
    return VIIRS_SATELLITE_CODES.get(code.upper(), code)

#: FIRMS `type`: 0 presumed vegetation fire, 1 volcano, 2 other static source,
#: 3 offshore. Anything non-zero is a thermal anomaly that is probably not a fire.
FIRMS_TYPE_LABELS = {
    "0": "presumed_vegetation_fire",
    "1": "volcano",
    "2": "other_static_land",
    "3": "offshore_detection",
}

TIME_PATTERN = re.compile(r"^(\d{1,2}):?(\d{2})$")


class NormalizationError(ValueError):
    """A row that cannot be represented honestly is rejected, not repaired."""

    def __init__(self, reason: str, field_name: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.field_name = field_name


@dataclass
class NormalizedObservation:
    source_code: str
    source_record_id: str
    sensor: str
    satellite: str
    latitude: float
    longitude: float
    acquired_at: datetime
    confidence_raw: int | None
    confidence_category: str | None
    brightness_temperature: float | None
    brightness_channel: str | None
    frp_mw: float | None
    scan_km: float | None
    track_km: float | None
    daynight: str | None
    processing_version: str | None
    source_product: str
    source_payload: dict[str, Any]
    quality_flags: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "source_code": self.source_code,
            "source_record_id": self.source_record_id,
            "sensor": self.sensor,
            "satellite": self.satellite,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "acquired_at": self.acquired_at,
            "confidence_raw": self.confidence_raw,
            "confidence_category": self.confidence_category,
            "brightness_temperature": self.brightness_temperature,
            "brightness_channel": self.brightness_channel,
            "frp_mw": self.frp_mw,
            "scan_km": self.scan_km,
            "track_km": self.track_km,
            "daynight": self.daynight,
            "processing_version": self.processing_version,
            "source_product": self.source_product,
            "source_payload": self.source_payload,
            "quality_flags": self.quality_flags,
        }


# --- helpers --------------------------------------------------------------
def _clean(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null", "n/a", ""}:
            return text
    return None


def _as_float(row: Mapping[str, Any], *keys: str) -> float | None:
    text = _clean(row, *keys)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise NormalizationError(f"not a number: {text!r}", keys[0]) from exc


def _as_int(row: Mapping[str, Any], *keys: str) -> int | None:
    value = _as_float(row, *keys)
    return int(value) if value is not None else None


def parse_acquired_at(row: Mapping[str, Any]) -> datetime:
    """Combine ``acq_date`` and ``acq_time`` (HHMM, UTC) into an aware instant."""
    acq_date = _clean(row, "acq_date", "acqDate")
    if not acq_date:
        raise NormalizationError("missing acquisition date", "acq_date")

    try:
        day = datetime.strptime(acq_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise NormalizationError(f"unparseable acquisition date {acq_date!r}", "acq_date") from exc

    acq_time = _clean(row, "acq_time", "acqTime")
    if acq_time is None:
        raise NormalizationError("missing acquisition time", "acq_time")

    match = TIME_PATTERN.match(acq_time.zfill(4) if acq_time.isdigit() else acq_time)
    if not match:
        raise NormalizationError(f"unparseable acquisition time {acq_time!r}", "acq_time")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise NormalizationError(f"impossible acquisition time {acq_time!r}", "acq_time")

    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90.0 <= latitude <= 90.0:
        raise NormalizationError(f"latitude out of range: {latitude}", "latitude")
    if not -180.0 <= longitude <= 180.0:
        raise NormalizationError(f"longitude out of range: {longitude}", "longitude")


def observation_fingerprint(values: Mapping[str, Any]) -> str:
    """
    Stable identity for a detection.

    FIRMS publishes no per-row identifier, so identity is derived from the
    measurement itself. Rounding is deliberate: it makes repeats of the same
    satellite detection deduplicate, while genuinely distinct detections differ
    in time, position or radiometry.
    """

    def number(value: Any, digits: int) -> str | None:
        if value is None:
            return None
        return f"{round(float(value), digits)}"

    canonical = {
        "source": values.get("source_product"),
        "sensor": values.get("sensor"),
        "satellite": values.get("satellite"),
        "lat": number(values.get("latitude"), 5),
        "lon": number(values.get("longitude"), 5),
        "at": values["acquired_at"].isoformat()
        if isinstance(values.get("acquired_at"), datetime)
        else values.get("acquired_at"),
        "bt": number(values.get("brightness_temperature"), 2),
        "frp": number(values.get("frp_mw"), 3),
        "scan": number(values.get("scan_km"), 2),
        "track": number(values.get("track_km"), 2),
        "conf": values.get("confidence_raw") or values.get("confidence_category"),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:32]


# --- adapters -------------------------------------------------------------
def _common(row: Mapping[str, Any], source: FirmsSource) -> dict[str, Any]:
    latitude = _as_float(row, "latitude", "lat")
    longitude = _as_float(row, "longitude", "lon")
    if latitude is None or longitude is None:
        raise NormalizationError("missing coordinates", "latitude")
    validate_coordinates(latitude, longitude)

    acquired_at = parse_acquired_at(row)
    daynight = (_clean(row, "daynight", "day_night") or "").upper()[:1] or None

    scan_km = _as_float(row, "scan")
    track_km = _as_float(row, "track")
    if scan_km is not None and scan_km <= 0:
        scan_km = None
    if track_km is not None and track_km <= 0:
        track_km = None

    frp = _as_float(row, "frp")
    if frp is not None and frp < 0:
        frp = None

    quality: dict[str, Any] = {"normalizer": ALGORITHM_VERSION}
    firms_type = _clean(row, "type")
    if firms_type is not None:
        quality["firms_type"] = firms_type
        quality["firms_type_label"] = FIRMS_TYPE_LABELS.get(firms_type, "unknown")
        if firms_type != "0":
            quality["suspected_non_fire"] = True

    instrument = _clean(row, "instrument")
    if instrument:
        quality["instrument"] = instrument

    return {
        "latitude": latitude,
        "longitude": longitude,
        "acquired_at": acquired_at,
        "daynight": daynight,
        "scan_km": scan_km,
        "track_km": track_km,
        "frp_mw": frp,
        "quality_flags": quality,
        "source_payload": {str(key): value for key, value in row.items()},
    }


def normalize_modis(row: Mapping[str, Any], source: FirmsSource) -> NormalizedObservation:
    base = _common(row, source)
    confidence = _as_int(row, "confidence")

    category: str | None = None
    if confidence is not None:
        for threshold, label in MODIS_CONFIDENCE_BANDS:
            if confidence >= threshold:
                category = label
                break
        base["quality_flags"]["confidence_interpretation"] = (
            "application bands applied to NASA MODIS 0-100 confidence"
        )

    bright_t31 = _as_float(row, "bright_t31")
    if bright_t31 is not None:
        base["quality_flags"]["bright_t31_kelvin"] = bright_t31

    values = {
        **base,
        "source_code": source.code,
        "source_product": source.code,
        "sensor": source.sensor,
        "satellite": _clean(row, "satellite") or source.satellite,
        "confidence_raw": confidence,
        "confidence_category": category,
        "brightness_temperature": _as_float(row, "brightness"),
        "brightness_channel": "modis_brightness_4um",
        "processing_version": _clean(row, "version"),
    }
    values["source_record_id"] = observation_fingerprint(values)
    return NormalizedObservation(**values)


def normalize_viirs(row: Mapping[str, Any], source: FirmsSource) -> NormalizedObservation:
    base = _common(row, source)
    raw_confidence = _clean(row, "confidence")
    category = VIIRS_CONFIDENCE.get(raw_confidence.lower()) if raw_confidence else None

    bright_ti5 = _as_float(row, "bright_ti5")
    if bright_ti5 is not None:
        base["quality_flags"]["bright_ti5_kelvin"] = bright_ti5
    base["quality_flags"]["confidence_source"] = "categorical (l/n/h)"

    values = {
        **base,
        "source_code": source.code,
        "source_product": source.code,
        "sensor": source.sensor,
        # The stored value stays the FIRMS code (part of the record fingerprint);
        # the API expands it for display so provenance is not misread as "N".
        "satellite": _clean(row, "satellite") or source.satellite,
        "confidence_raw": None,
        "confidence_category": category,
        "brightness_temperature": _as_float(row, "bright_ti4"),
        "brightness_channel": "viirs_bright_ti4_4um",
        "processing_version": _clean(row, "version"),
    }
    values["source_record_id"] = observation_fingerprint(values)
    return NormalizedObservation(**values)


def normalize_row(row: Mapping[str, Any], source: FirmsSource) -> NormalizedObservation:
    """Dispatch to the adapter for the product family."""
    if source.sensor == "MODIS":
        return normalize_modis(row, source)
    if source.sensor == "VIIRS":
        return normalize_viirs(row, source)
    raise NormalizationError(f"no adapter for sensor {source.sensor!r}", "sensor")
