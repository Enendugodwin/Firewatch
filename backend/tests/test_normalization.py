"""Normalization adapters: canonical records, confidence semantics, rejection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.normalization import (
    NormalizationError,
    normalize_row,
    observation_fingerprint,
    parse_acquired_at,
)
from app.services.sources import get_source

MODIS_ROW = {
    "latitude": "8.500",
    "longitude": "9.100",
    "brightness": "340.2",
    "scan": "1.0",
    "track": "1.0",
    "acq_date": "2026-10-28",
    "acq_time": "1020",
    "satellite": "Terra",
    "instrument": "MODIS",
    "confidence": "85",
    "version": "6.1NRT",
    "bright_t31": "301.4",
    "frp": "12.4",
    "daynight": "D",
    "type": "0",
}

VIIRS_ROW = {
    "latitude": "8.503",
    "longitude": "9.104",
    "bright_ti4": "341.9",
    "scan": "0.375",
    "track": "0.375",
    "acq_date": "2026-10-28",
    "acq_time": "1035",
    "satellite": "Suomi-NPP",
    "instrument": "VIIRS",
    "confidence": "h",
    "version": "2.0NRT",
    "bright_ti5": "295.2",
    "frp": "9.8",
    "daynight": "D",
    "type": "0",
}


def test_modis_adapter_keeps_raw_confidence_and_channel() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    observation = normalize_row(MODIS_ROW, source)

    assert observation.sensor == "MODIS"
    assert observation.satellite == "Terra"
    assert observation.confidence_raw == 85
    assert observation.confidence_category == "high"
    assert observation.brightness_channel == "modis_brightness_4um"
    assert observation.brightness_temperature == pytest.approx(340.2)
    assert observation.frp_mw == pytest.approx(12.4)
    assert observation.quality_flags["bright_t31_kelvin"] == pytest.approx(301.4)
    assert "confidence_interpretation" in observation.quality_flags


def test_viirs_adapter_maps_categorical_confidence() -> None:
    source = get_source("VIIRS_SNPP_SP")
    assert source is not None

    observation = normalize_row(VIIRS_ROW, source)

    assert observation.sensor == "VIIRS"
    assert observation.confidence_raw is None  # VIIRS confidence is categorical
    assert observation.confidence_category == "high"
    assert observation.brightness_channel == "viirs_bright_ti4_4um"
    assert observation.quality_flags["bright_ti5_kelvin"] == pytest.approx(295.2)


def test_confidence_bands_are_application_level_and_documented() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    nominal = normalize_row({**MODIS_ROW, "confidence": "45"}, source)
    low = normalize_row({**MODIS_ROW, "confidence": "12"}, source)

    assert nominal.confidence_category == "nominal"
    assert low.confidence_category == "low"
    assert "application bands" in nominal.quality_flags["confidence_interpretation"]


def test_channels_are_not_conflated_across_sensors() -> None:
    modis = normalize_row(MODIS_ROW, get_source("MODIS_SP"))
    viirs = normalize_row(VIIRS_ROW, get_source("VIIRS_SNPP_SP"))

    assert modis.brightness_channel != viirs.brightness_channel
    assert modis.sensor != viirs.sensor


def test_acquisition_time_is_parsed_as_utc() -> None:
    parsed = parse_acquired_at(MODIS_ROW)

    assert parsed == datetime(2026, 10, 28, 10, 20, tzinfo=UTC)
    assert parsed.tzinfo is UTC


def test_colon_separated_time_is_accepted() -> None:
    assert parse_acquired_at({**MODIS_ROW, "acq_time": "10:20"}) == datetime(
        2026, 10, 28, 10, 20, tzinfo=UTC
    )


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"acq_time": "2560"}, "acq_time"),
        ({"acq_time": "later"}, "acq_time"),
        ({"acq_date": "28/10/2026"}, "acq_date"),
        ({"latitude": "95"}, "latitude"),
        ({"longitude": "-181"}, "longitude"),
    ],
)
def test_invalid_rows_are_rejected_not_repaired(patch: dict[str, str], field: str) -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    with pytest.raises(NormalizationError) as excinfo:
        normalize_row({**MODIS_ROW, **patch}, source)

    assert excinfo.value.field_name == field


def test_missing_time_is_rejected() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    with pytest.raises(NormalizationError):
        normalize_row({k: v for k, v in MODIS_ROW.items() if k != "acq_time"}, source)


def test_negative_frp_is_not_negative_power() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    observation = normalize_row({**MODIS_ROW, "frp": "-3"}, source)
    assert observation.frp_mw is None


def test_non_vegetation_thermal_anomaly_is_flagged() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    observation = normalize_row({**MODIS_ROW, "type": "2"}, source)

    assert observation.quality_flags["suspected_non_fire"] is True
    assert observation.quality_flags["firms_type_label"] == "other_static_land"


def test_fingerprint_is_stable_and_discriminating() -> None:
    source = get_source("MODIS_SP")
    assert source is not None

    first = normalize_row(MODIS_ROW, source)
    second = normalize_row(dict(MODIS_ROW), source)
    other = normalize_row({**MODIS_ROW, "acq_time": "1021"}, source)

    assert first.source_record_id == second.source_record_id
    assert first.source_record_id != other.source_record_id
    assert len(first.source_record_id) == 32

    # The fingerprint ignores presentation-only whitespace.
    assert observation_fingerprint(first.to_row()) == first.source_record_id
