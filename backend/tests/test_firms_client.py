"""FIRMS client: parsing, retries, authentication and key hygiene."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.services.firms.client import (
    AvailabilityWindow,
    FirmsAuthError,
    FirmsClient,
    FirmsError,
    FirmsTemporaryError,
    parse_availability,
    redact,
)

CSV_BODY = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight,type\n"
    "8.500,9.100,340.2,1.0,1.0,2026-10-28,1020,Terra,MODIS,85,6.1NRT,301.4,12.4,D,0\n"
    "8.512,9.093,331.8,1.0,1.0,2026-10-28,1110,Terra,MODIS,60,6.1NRT,299.8,6.1,D,0\n"
)


def make_client(handler, *, key: str | None = "TESTKEY", retries: int = 4) -> FirmsClient:
    return FirmsClient(
        key,
        base_url="https://firms.test/api",
        max_retries=retries,
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )


def test_fetch_area_parses_rows_and_builds_documented_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=CSV_BODY)

    client = make_client(handler)
    result = client.fetch_area(
        "MODIS_SP", "-5,4,15,14", day_range=2, request_date=date(2026, 10, 28)
    )

    assert result.status == "ok"
    assert result.record_count == 2
    assert result.rows[0]["latitude"] == "8.500"
    assert seen[0] == "https://firms.test/api/area/csv/TESTKEY/MODIS_SP/-5,4,15,14/2/2026-10-28"


def test_empty_body_means_no_detections_not_an_error() -> None:
    client = make_client(lambda _request: httpx.Response(200, text=""))

    result = client.fetch_area("MODIS_SP", "world", day_range=1)

    assert result.status == "empty"
    assert result.record_count == 0


def test_invalid_key_body_raises_authentication_error() -> None:
    client = make_client(lambda _request: httpx.Response(200, text="Invalid MAP_KEY."))

    with pytest.raises(FirmsAuthError):
        client.fetch_area("MODIS_SP", "world", day_range=1)


def test_server_errors_are_retried_then_succeed() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, text=CSV_BODY)

    result = make_client(handler).fetch_area("MODIS_SP", "world", day_range=1)

    assert attempts["count"] == 3
    assert result.attempts == 3
    assert result.record_count == 2


def test_rate_limit_is_retried() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")
        return httpx.Response(200, text=CSV_BODY)

    result = make_client(handler).fetch_area("MODIS_SP", "world", day_range=1)
    assert result.record_count == 2


def test_authorisation_failure_is_not_retried() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, text="forbidden")

    with pytest.raises(FirmsAuthError):
        make_client(handler).fetch_area("MODIS_SP", "world", day_range=1)

    assert attempts["count"] == 1


def test_exhausted_retries_raise_temporary_error() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(500, text="boom")

    with pytest.raises(FirmsTemporaryError):
        make_client(handler, retries=3).fetch_area("MODIS_SP", "world", day_range=1)

    assert attempts["count"] == 3


def test_transport_errors_are_retried() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, text=CSV_BODY)

    result = make_client(handler).fetch_area("MODIS_SP", "world", day_range=1)
    assert result.record_count == 2


def test_missing_key_fails_fast() -> None:
    with pytest.raises(FirmsAuthError):
        make_client(lambda _r: httpx.Response(200, text=""), key=None).fetch_area(
            "MODIS_SP", "world"
        )


@pytest.mark.parametrize("day_range", [0, 6, 30])
def test_day_range_is_validated(day_range: int) -> None:
    with pytest.raises(FirmsError):
        make_client(lambda _r: httpx.Response(200, text="")).fetch_area(
            "MODIS_SP", "world", day_range=day_range
        )


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(FirmsError):
        make_client(lambda _r: httpx.Response(200, text="")).fetch_area("VIIRS_MARS_SP", "world")


def test_short_non_csv_body_is_an_error_not_a_row() -> None:
    with pytest.raises(FirmsError):
        make_client(lambda _r: httpx.Response(200, text="Service unavailable")).fetch_area(
            "MODIS_SP", "world"
        )


def test_map_key_never_appears_in_redacted_url() -> None:
    url = "https://firms.test/api/area/csv/SECRETKEY/MODIS_SP/world/1"
    assert "SECRETKEY" not in redact(url, "SECRETKEY")
    assert redact(url, None) == url


# --- availability ---------------------------------------------------------


def test_availability_parses_a_coverage_window() -> None:
    # This is the shape the live endpoint returns (verified 2026-10-30).
    body = "data_id,min_date,max_date\nVIIRS_SNPP_NRT,2026-08-01,2026-10-30\n"

    window = parse_availability("VIIRS_SNPP_NRT", body)

    assert isinstance(window, AvailabilityWindow)
    assert window.min_date == date(2026, 8, 1)
    assert window.max_date == date(2026, 10, 30)
    assert window.rows == 1

    assert window.covers(date(2026, 9, 15))
    assert not window.covers(date(2026, 7, 31))
    assert not window.covers(date(2026, 10, 31))


def test_availability_classifies_outside_coverage() -> None:
    window = parse_availability(
        "MODIS_SP", "data_id,min_date,max_date\nMODIS_SP,2026-08-01,2026-10-30\n"
    )

    assert window.classify(date(2026, 9, 1)) == "available"
    assert window.classify(date(2026, 7, 1)) == "before_coverage"
    assert window.classify(date(2026, 11, 1)) == "not_yet_available"


def test_availability_accepts_a_legacy_date_list() -> None:
    body = "source,country_id,date\nMODIS_SP,NG,2026-10-01\nMODIS_SP,NG,2026-10-02\n"

    window = parse_availability("MODIS_SP", body)

    assert window.covers(date(2026, 10, 1))
    assert not window.covers(date(2026, 10, 3))
    assert window.min_date == date(2026, 10, 1)


def test_availability_endpoint_returns_the_window() -> None:
    body = "data_id,min_date,max_date\nMODIS_SP,2026-08-01,2026-10-30\n"
    client = make_client(lambda _r: httpx.Response(200, text=body))

    window = client.fetch_availability("MODIS_SP")

    assert window.max_date == date(2026, 10, 30)


def test_unknown_availability_shape_is_not_assumed_available() -> None:
    window = parse_availability("MODIS_SP", "unexpected,columns\n1,2\n")

    assert window.min_date is None
    assert window.max_date is None
    assert window.classify(date(2026, 10, 1)) == "unknown"
