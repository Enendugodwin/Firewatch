"""NASA FIRMS area-CSV client.

Design notes
------------
* The MAP_KEY never appears in logs, error messages or responses; URLs are
  redacted before they are recorded.
* Retries use exponential backoff with jitter and honour ``Retry-After``.
* A 200 response with an empty body means "no detections"; an ``Invalid
  MAP_KEY`` body is an authentication failure, not an empty day. Those two must
  never be conflated, because a missing observation day is not zero activity.
"""

from __future__ import annotations

import csv
import io
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import httpx

from app.core.logging import get_logger
from app.services.sources import FIRMS_SOURCES_BY_CODE

logger = get_logger(__name__)

#: FIRMS documents a maximum five-day window per area request.
MAX_DAY_RANGE = 5
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
AUTH_FAILURE_MARKERS = ("invalid map_key", "invalid map key", "invalid key")
ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


class FirmsError(RuntimeError):
    """Base error for FIRMS retrieval."""


class FirmsAuthError(FirmsError):
    """The MAP_KEY was rejected. Retrying will not help."""


class FirmsTemporaryError(FirmsError):
    """Retries were exhausted or the provider is unavailable."""


@dataclass
class FirmsResponse:
    source_code: str
    bbox: str
    day_range: int
    request_date: date | None
    status: Literal["ok", "empty"]
    rows: list[dict[str, str]] = field(default_factory=list)
    http_status: int = 200
    duration_ms: int = 0
    attempts: int = 1

    @property
    def record_count(self) -> int:
        return len(self.rows)


def redact(url: str, map_key: str | None) -> str:
    """Remove the MAP_KEY from any URL before logging or storing it."""
    if map_key:
        return url.replace(map_key, "***")
    return url


@dataclass(frozen=True)
class AvailabilityWindow:
    """Coverage reported by FIRMS for one product."""

    source_code: str
    min_date: date | None
    max_date: date | None
    explicit_dates: frozenset[date] = frozenset()
    rows: int = 0

    def covers(self, day: date) -> bool:
        if self.min_date is not None and self.max_date is not None:
            return self.min_date <= day <= self.max_date
        return day in self.explicit_dates

    def classify(self, day: date) -> str:
        """Status for one date, honest about why it is not covered."""
        if self.covers(day):
            return "available"
        if self.min_date is not None and day < self.min_date:
            return "before_coverage"
        if self.max_date is not None and day > self.max_date:
            return "not_yet_available"
        if self.explicit_dates:
            return "missing"
        return "unknown"


def parse_availability(source_code: str, body: str) -> AvailabilityWindow:
    """Parse either the coverage-window CSV or a legacy list of ISO dates."""
    import csv
    import io as _io

    rows = [row for row in csv.DictReader(_io.StringIO(body or "")) if row]
    min_dates: list[date] = []
    max_dates: list[date] = []
    explicit: set[date] = set()

    for row in rows:
        columns = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        min_text = columns.get("min_date") or columns.get("date")
        max_text = columns.get("max_date") or columns.get("date")
        for raw in (min_text, max_text):
            if raw:
                try:
                    explicit.add(date.fromisoformat(raw))
                except ValueError:
                    continue
        try:
            if columns.get("min_date"):
                min_dates.append(date.fromisoformat(columns["min_date"]))
            if columns.get("max_date"):
                max_dates.append(date.fromisoformat(columns["max_date"]))
        except ValueError:
            continue

    if min_dates and max_dates:
        return AvailabilityWindow(
            source_code=source_code,
            min_date=min(min_dates),
            max_date=max(max_dates),
            explicit_dates=frozenset(explicit),
            rows=len(rows),
        )

    if explicit:
        return AvailabilityWindow(
            source_code=source_code,
            min_date=min(explicit),
            max_date=max(explicit),
            explicit_dates=frozenset(explicit),
            rows=len(rows),
        )

    return AvailabilityWindow(source_code=source_code, min_date=None, max_date=None, rows=len(rows))


class FirmsClient:
    """Synchronous client; FastAPI endpoints call it in a worker thread."""

    def __init__(
        self,
        map_key: str | None,
        *,
        base_url: str = "https://firms.modaps.eosdis.nasa.gov/api",
        timeout: float = 60.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.map_key = map_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self._transport = transport
        self._sleep = sleep

    # -- public API --------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.map_key)

    def fetch_area(
        self,
        source_code: str,
        bbox: str,
        day_range: int = 1,
        request_date: date | None = None,
    ) -> FirmsResponse:
        if not self.configured:
            raise FirmsAuthError(
                "FIRMS_MAP_KEY is not configured; no NASA observations can be retrieved."
            )
        if source_code not in FIRMS_SOURCES_BY_CODE:
            raise FirmsError(f"Unsupported FIRMS source {source_code!r}.")
        if not 1 <= day_range <= MAX_DAY_RANGE:
            raise FirmsError(f"day_range must be between 1 and {MAX_DAY_RANGE}.")

        path = f"/area/csv/{self.map_key}/{source_code}/{bbox}/{day_range}"
        if request_date is not None:
            path += f"/{request_date.isoformat()}"
        url = f"{self.base_url}{path}"
        safe_url = redact(url, self.map_key)

        started = time.perf_counter()
        attempts = 0
        last_error: Exception | None = None

        while attempts < self.max_retries:
            attempts += 1
            try:
                response = self._get(url)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "firms_transport_error",
                    source=source_code,
                    attempt=attempts,
                    error=type(exc).__name__,
                )
                self._backoff(attempts, None)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_error = FirmsTemporaryError(
                    f"FIRMS returned HTTP {response.status_code} for {source_code}."
                )
                logger.warning(
                    "firms_retryable_status",
                    source=source_code,
                    status=response.status_code,
                    attempt=attempts,
                )
                self._backoff(attempts, response.headers.get("Retry-After"))
                continue

            if response.status_code in {400, 401, 403}:
                raise FirmsAuthError(
                    "NASA FIRMS rejected the request. Check that FIRMS_MAP_KEY is valid "
                    f"and active (HTTP {response.status_code})."
                )

            if response.status_code >= 400:
                raise FirmsError(
                    f"FIRMS returned an unexpected HTTP {response.status_code} for {source_code}."
                )

            duration_ms = int((time.perf_counter() - started) * 1000)
            result = self._parse(response, source_code, bbox, day_range, request_date)
            result.duration_ms = duration_ms
            result.attempts = attempts
            logger.info(
                "firms_fetch",
                source=source_code,
                bbox=bbox,
                day_range=day_range,
                request_date=request_date.isoformat() if request_date else None,
                records=result.record_count,
                status=result.status,
                duration_ms=duration_ms,
                attempts=attempts,
                url=safe_url,
            )
            return result

        raise FirmsTemporaryError(
            f"FIRMS retrieval failed after {attempts} attempts for {source_code}: {last_error}"
        )

    def fetch_availability(self, source_code: str) -> AvailabilityWindow:
        """Which dates the provider reports as observed for a source.

        The current endpoint returns a coverage window per product::

            data_id,min_date,max_date
            VIIRS_SNPP_NRT,2026-08-01,2026-10-30

        Older deployments return an explicit list of dates. Both are parsed, and
        the distinction matters: a date inside the coverage window is observed
        (it may legitimately contain zero detections), while a date outside it
        was never processed and must not be read as zero activity.
        """
        if not self.configured:
            raise FirmsAuthError("FIRMS_MAP_KEY is not configured.")
        url = f"{self.base_url}/data_availability/csv/{self.map_key}/{source_code}"
        response = self._get(url)
        if response.status_code in {400, 401, 403}:
            raise FirmsAuthError("NASA FIRMS rejected the availability request.")
        if response.status_code >= 400:
            raise FirmsError(f"Availability request failed with HTTP {response.status_code}.")
        return parse_availability(source_code, response.text)

        # -- internals ---------------------------------------------------------

    def _get(self, url: str) -> httpx.Response:
        with httpx.Client(
            timeout=self.timeout,
            transport=self._transport,
            follow_redirects=True,
            headers={"Accept": "text/csv, text/plain;q=0.9, */*;q=0.8"},
        ) as client:
            return client.get(url)

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if attempt >= self.max_retries:
            return
        delay = min(30.0, 2.0 ** (attempt - 1)) + random.uniform(0, 0.5)
        if retry_after:
            try:
                delay = max(delay, min(30.0, float(retry_after)))
            except ValueError:
                # A malformed Retry-After must not break the retry loop.
                delay = delay
        self._sleep(delay)

    def _parse(
        self,
        response: httpx.Response,
        source_code: str,
        bbox: str,
        day_range: int,
        request_date: date | None,
    ) -> FirmsResponse:
        body = response.text or ""
        lowered = body.strip().lower()

        if any(marker in lowered for marker in AUTH_FAILURE_MARKERS):
            raise FirmsAuthError(
                "NASA FIRMS rejected the MAP_KEY. Request a valid key at "
                "https://firms.modaps.eosdis.nasa.gov/api/map_key/"
            )

        # A short non-CSV body is a provider message, not an observation table.
        if body.strip() and "\n" not in body.strip() and "," not in body.strip():
            raise FirmsError(f"Unexpected FIRMS response: {body.strip()[:120]}")

        if not body.strip():
            return FirmsResponse(
                source_code=source_code,
                bbox=bbox,
                day_range=day_range,
                request_date=request_date,
                status="empty",
                http_status=response.status_code,
            )

        reader = csv.DictReader(io.StringIO(body))
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {(key or "").strip(): (value or "").strip() for key, value in raw.items()}
            if not row.get("latitude") or not row.get("longitude"):
                continue
            rows.append(row)

        return FirmsResponse(
            source_code=source_code,
            bbox=bbox,
            day_range=day_range,
            request_date=request_date,
            status="ok" if rows else "empty",
            rows=rows,
            http_status=response.status_code,
        )
