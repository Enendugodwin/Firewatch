"""Assistant: deterministic answers computed from the database.

There is no language model in this deployment. Questions are matched to a small,
documented intent set and answered with the same aggregates the screens use. The
response says which intent fired, what scope it used, and which data it read, so
an answer can always be checked. Nothing is generated.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FireEvent, ObservationMatch
from app.services.analytics import analytics_summary
from app.services.anomalies import detect_anomalies
from app.services.gazetteer import CITIES, COUNTRIES, Place
from app.services.observation_queries import ObservationFilters
from app.services.regions import REGION_NOTE, region_box

CAPABILITIES = [
    "how many detections in <period or place>",
    "top activity cells",
    "sensor split (MODIS vs VIIRS)",
    "cross-sensor matches and events",
    "anomalies for the period",
]


def _find_place(question: str) -> Place | None:
    """Longest name wins, so "Nigeria" is not read as "Niger"."""
    lowered = question.lower()
    matches = [
        place for place in (*COUNTRIES, *CITIES) if place.name.lower() in lowered
    ]
    if not matches:
        return None
    return max(matches, key=lambda place: len(place.name))


def _intent(question: str) -> str:
    text = question.lower()
    if "anomal" in text or "unusual" in text:
        return "anomalies"
    if "top" in text and any(word in text for word in ("region", "area", "cell", "hotspot")):
        return "top_cells"
    if "sensor" in text or "modis" in text or "viirs" in text:
        return "sensor_split"
    if "match" in text or "association" in text:
        return "matches"
    if "event" in text:
        return "events"
    if any(word in text for word in ("how many", "detection", "count", "active")):
        return "totals"
    return "help"


def answer(
    session: Session,
    *,
    question: str,
    start: date,
    end: date,
    synthetic: bool | None = None,
) -> dict[str, Any]:
    intent = _intent(question)
    place = _find_place(question)
    bbox = region_box(place) if place is not None else None
    filters = ObservationFilters(
        bbox=bbox, start_date=start, end_date=end, synthetic=synthetic
    )

    scope = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "bbox": bbox.as_list() if bbox else None,
        "place": place.name if place else None,
    }
    notes = ["Answers are computed from stored NASA FIRMS detections; nothing is generated."]
    if place is not None:
        notes.append(REGION_NOTE)

    data: dict[str, Any] = {}

    if intent in ("totals", "sensor_split", "top_cells"):
        summary = analytics_summary(session, filters, start=start, end=end, top=10)
        totals = summary["totals"]
        data = {"totals": totals, "top_cells": summary["top_cells"]}
        where = f" in {place.name} (approximate box)" if place else ""
        if intent == "sensor_split":
            text = (
                f"{totals['detections']:,} detections{where}: MODIS {totals['modis']:,}, "
                f"VIIRS {totals['viirs']:,}. High confidence {totals['high_confidence']:,}."
            )
        elif intent == "top_cells":
            top = summary["top_cells"][:3]
            listing = "; ".join(
                f"{cell['latitude']:.1f}, {cell['longitude']:.1f} — {cell['detections']:,}"
                for cell in top
            )
            text = f"Busiest {summary['cell_degrees']}° cells{where}: {listing}."
        else:
            text = (
                f"{totals['detections']:,} detections{where} between {start} and {end}, "
                f"active on {totals['active_days']} of {totals['days']} days, "
                f"FRP sum {totals['frp_sum_mw']:,.1f} MW."
            )
    elif intent == "anomalies":
        result = detect_anomalies(session, filters, start=start, end=end)
        data = {
            "status": result["status"],
            "flagged": result["anomalies"],
            "method": result["method"],
        }
        if result["status"] == "insufficient_history":
            text = (
                "Not enough observed history for a baseline in this scope, so no anomaly "
                "is claimed. " + result["requirements"]["note"]
            )
        elif not result["anomalies"]:
            text = (
                f"No day in {start} → {end} departs from its baseline by the threshold "
                f"(z ≥ {result['method']['z_threshold']})."
            )
        else:
            first = result["anomalies"][0]
            text = (
                f"{len(result['anomalies'])} day(s) flagged; the strongest is {first['date']} "
                f"with {first['observed']:,.0f} detections against {first['expected']:,.1f} "
                f"expected ({first['severity']})."
            )
    elif intent in ("matches", "events"):
        matches = session.scalar(select(func.count()).select_from(ObservationMatch)) or 0
        probable = (
            session.scalar(
                select(func.count())
                .select_from(ObservationMatch)
                .where(ObservationMatch.match_status == "probable")
            )
            or 0
        )
        events = session.scalar(select(func.count()).select_from(FireEvent)) or 0
        data = {"matches": int(matches), "probable": int(probable), "events": int(events)}
        if intent == "matches":
            text = f"{matches:,} cross-sensor matches stored, {probable:,} of them probable."
        else:
            text = f"{events:,} estimated events stored from those associations."
        notes.append(
            "Match and event counts cover the last stored analysis scope, not this period."
        )
    else:
        text = (
            "I answer a fixed set of data questions: " + "; ".join(CAPABILITIES) + "."
        )

    return {
        "answer": text,
        "intent": intent,
        "scope": scope,
        "data": data,
        "method": "deterministic",
        "capabilities": CAPABILITIES,
        "notes": notes,
    }


def default_window(question_start: date | None, question_end: date | None) -> tuple[date, date]:
    end = question_end or date.today()
    start = question_start or (end - timedelta(days=6))
    return start, end
