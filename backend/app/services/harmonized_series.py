"""Harmonised daily series: one count per thermal anomaly seen by either sensor.

Definition
----------
    harmonized = MODIS + VIIRS − matched_VIIRS

``matched_VIIRS`` is the number of **distinct** VIIRS detections that have at
least one probable or possible association with a MODIS detection on the same
UTC day. That removes the double count created when both sensors see the same
hotspot, without merging, editing or deleting any observation: the raw sensor
series stay exactly as stored.

Limits that the response always states:

* associations exist only where a harmonisation run covered the scope; a day
  without matches returns ``harmonized == raw`` and says so;
* the association score is not a probability of identity, so the reduction is a
  documented de-duplication, not a calibrated fire count;
* a MODIS detection matched to several VIIRS detections subtracts each matched
  VIIRS once; a VIIRS detection matched to several MODIS detections is still
  subtracted once.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name, utc_day
from app.db.models import FireObservation, ObservationMatch
from app.services.observation_queries import ObservationFilters
from app.services.rollups import activity_rows

ALGORITHM_VERSION = "harmonized-series-v1"
DEFAULT_STATUSES = ("probable", "possible")


def _day_key(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def harmonized_daily(
    session: Session,
    *,
    start: date,
    end: date,
    synthetic: bool = False,
    statuses: tuple[str, ...] = DEFAULT_STATUSES,
) -> dict[str, Any]:
    if start > end:
        raise ValueError("start must be on or before end")

    # Raw counts come from the daily rollup, so the series does not scan 11 M rows.
    rows = activity_rows(
        session,
        ObservationFilters(start_date=start, end_date=end, synthetic=synthetic),
    )
    raw: dict[date, dict[str, int]] = {}
    for row in rows:
        day = _day_key(row.day)
        entry = raw.setdefault(day, {"MODIS": 0, "VIIRS": 0})
        if row.sensor in entry:
            entry[row.sensor] += int(row.detections)

    # Distinct VIIRS detections with at least one cross-sensor association.
    b = FireObservation
    day_expr = utc_day(b.acquired_at, dialect_name(session))
    matched_rows = session.execute(
        select(day_expr.label("day"), func.count(func.distinct(b.id)))
        .join(ObservationMatch, ObservationMatch.observation_b_id == b.id)
        .where(
            ObservationMatch.match_status.in_(statuses),
            b.is_synthetic == synthetic,
            day_expr >= start,
            day_expr <= end,
        )
        .group_by(day_expr)
    ).all()
    matched = {_day_key(row[0]): int(row[1]) for row in matched_rows}

    days: list[dict[str, Any]] = []
    totals: dict[str, float | int] = {
        "modis": 0,
        "viirs": 0,
        "raw": 0,
        "matched_viirs": 0,
        "harmonized": 0,
    }
    for day in sorted(set(raw) | set(matched)):
        modis = raw.get(day, {}).get("MODIS", 0)
        viirs = raw.get(day, {}).get("VIIRS", 0)
        paired = min(matched.get(day, 0), viirs)
        harmonized = modis + viirs - paired
        days.append(
            {
                "date": day.isoformat(),
                "modis": modis,
                "viirs": viirs,
                "raw": modis + viirs,
                "matched_viirs": paired,
                "harmonized": harmonized,
                "reduction_ratio": round(paired / viirs, 4) if viirs else 0.0,
            }
        )
        totals["modis"] += modis
        totals["viirs"] += viirs
        totals["raw"] += modis + viirs
        totals["matched_viirs"] += paired
        totals["harmonized"] += harmonized

    days_with_matches = sum(1 for day in days if day["matched_viirs"] > 0)
    totals["reduction_ratio"] = (
        round(totals["matched_viirs"] / totals["viirs"], 4) if totals["viirs"] else 0.0
    )

    if days_with_matches == 0:
        note = (
            "No cross-sensor associations exist for this window, so the harmonised "
            "series equals the raw total. Run harmonisation over this scope to create "
            "associations; this is not evidence that no duplicates exist."
        )
        status = "unmatched"
    else:
        note = (
            f"{days_with_matches} of {len(days)} days have associations. Days without "
            "associations contribute their raw count unchanged."
        )
        status = "ok"

    return {
        "status": status,
        "algorithm_version": ALGORITHM_VERSION,
        "start_date": start,
        "end_date": end,
        "synthetic": synthetic,
        "match_statuses": list(statuses),
        "definition": (
            "harmonized = MODIS + VIIRS - distinct VIIRS detections with at least one "
            "probable or possible MODIS association on the same UTC day"
        ),
        "days": days,
        "totals": totals,
        "coverage": {
            "days": len(days),
            "days_with_matches": days_with_matches,
            "association_scope_note": (
                "Associations are produced by scoped harmonisation runs; they are not "
                "computed for every stored day."
            ),
        },
        "notes": [
            "Raw MODIS and VIIRS series are unchanged; only the combined series "
            "subtracts duplicates.",
            "The association score is not a probability of identity, so this is a "
            "documented de-duplication, not a calibrated fire count.",
            "Counts are detections, not fires.",
            note,
        ],
    }
