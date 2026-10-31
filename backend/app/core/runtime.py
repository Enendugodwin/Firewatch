"""Process-level runtime facts (start time, current delivery phase)."""

from __future__ import annotations

import time

STARTED_AT = time.monotonic()

#: Current delivery phase from the implementation plan (PART 23).
CURRENT_PHASE = "6"
CURRENT_PHASE_NAME = "Analytics & Anomalies"


def current_phase() -> tuple[str, str]:
    return CURRENT_PHASE, CURRENT_PHASE_NAME
