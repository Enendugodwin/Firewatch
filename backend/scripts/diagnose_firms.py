"""Diagnose FIRMS access without printing the MAP_KEY.

Prints only: HTTP status, redacted URLs, body shapes and record counts.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx

from app.core.config import get_settings

settings = get_settings()
key = settings.firms_map_key or ""
print("key configured:", bool(key), "length:", len(key))

base = settings.firms_base_url.rstrip("/")
availability_url = f"{base}/data_availability/csv/{key}/VIIRS_SNPP_NRT"

with httpx.Client(timeout=60) as client:
    response = client.get(availability_url)
    body = response.text
    print("availability status:", response.status_code)
    print("availability url:", availability_url.replace(key, "***"))
    print("body length:", len(body))
    print("first 300 chars:", body[:300].replace(key, "***"))
    print("dates found:", sorted(set(re.findall(r"\d{4}-\d{2}-\d{2}", body)))[-5:])

    # Query one day either side of "today" in a small West-Africa box.
    for days_back in (0, 1, 2, 5, 10, 30):
        target = date.today() - timedelta(days=days_back)
        url = f"{base}/area/csv/{key}/VIIRS_SNPP_NRT/2.5,4.0,14.7,13.9/1/{target.isoformat()}"
        result = client.get(url)
        text = result.text or ""
        lines = [line for line in text.splitlines() if line.strip()]
        print(
            f"area {target} -> status {result.status_code}, lines {len(lines)}, "
            f"head {lines[0][:60] if lines else ''!r}"
        )
