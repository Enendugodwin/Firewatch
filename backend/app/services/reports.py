"""Report builder: a briefing document assembled from stored data only.

A report is a snapshot of what the platform can prove for a scope: detection
totals, daily trend, ranked cells, sensor mix, harmonization counts, coverage
state and anomalies. Every number is computed by the same services the screens
use, so a report cannot disagree with the UI.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FireEvent, FireObservation, ObservationMatch
from app.services.analytics import analytics_summary
from app.services.anomalies import detect_anomalies
from app.services.calendar import daily_metrics
from app.services.observation_queries import ObservationFilters

REPORT_VERSION = "report-v1"


def build_report(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    top: int = 10,
) -> dict[str, Any]:
    analytics = analytics_summary(session, filters, start=start, end=end, top=top)
    anomalies = detect_anomalies(session, filters, start=start, end=end)

    matches_total = session.scalar(select(func.count()).select_from(ObservationMatch)) or 0
    probable = (
        session.scalar(
            select(func.count())
            .select_from(ObservationMatch)
            .where(ObservationMatch.match_status == "probable")
        )
        or 0
    )
    events = session.scalar(select(func.count()).select_from(FireEvent)) or 0
    multi_sensor_events = (
        session.scalar(
            select(func.count()).select_from(FireEvent).where(FireEvent.sensor_count > 1)
        )
        or 0
    )

    # Coverage: how many days in the range a source actually observed.
    observed = 0
    daily = daily_metrics(session, filters)
    cursor = start
    while cursor <= end:
        if cursor in daily:
            observed += 1
        cursor += timedelta(days=1)

    synthetic = (
        session.scalar(
            select(func.count())
            .select_from(FireObservation)
            .where(FireObservation.is_synthetic.is_(True))
        )
        or 0
    )

    totals = analytics["totals"]
    return {
        "version": REPORT_VERSION,
        "start_date": start,
        "end_date": end,
        "headline": {
            "detections": totals["detections"],
            "active_days": totals["active_days"],
            "days": totals["days"],
            "frp_sum_mw": totals["frp_sum_mw"],
            "frp_max_mw": totals["frp_max_mw"],
            "high_confidence": totals["high_confidence"],
            "modis": totals["modis"],
            "viirs": totals["viirs"],
        },
        "series": analytics["series"],
        "top_cells": analytics["top_cells"],
        "cell_degrees": analytics["cell_degrees"],
        "satellites": analytics["satellites"],
        "confidence": analytics["confidence"],
        "daynight": analytics["daynight"],
        "harmonization": {
            "matches_total": int(matches_total),
            "probable": int(probable),
            "events": int(events),
            "multi_sensor_events": int(multi_sensor_events),
            "note": "Match and event counts cover the last stored analysis scope, not this period.",
        },
        "anomalies": {
            "status": anomalies["status"],
            "flagged": anomalies["anomalies"],
            "method": anomalies["method"]["version"],
            "baseline_source": anomalies["method"]["baseline_source"],
        },
        "coverage": {
            "days_with_detections": observed,
            "range_days": totals["days"],
            "synthetic_rows": int(synthetic),
        },
        "notes": [
            "Counts are thermal detections, not confirmed fires.",
            "Rankings use a fixed geographic grid, not administrative boundaries.",
            "Anomalies are relative to the scope's own baseline; insufficient history is reported.",
            "This document is generated from the database and contains no model-written prose.",
        ],
    }


def report_markdown(report: dict[str, Any]) -> str:
    """Plain-text briefing; stable, diffable and safe to paste into a ticket."""
    headline = report["headline"]
    lines = [
        f"# FIREWATCH X report {report['start_date']} → {report['end_date']}",
        "",
        f"Detections: **{headline['detections']:,}** · active days "
        f"{headline['active_days']}/{headline['days']} · FRP sum "
        f"{headline['frp_sum_mw']:,.1f} MW · peak {headline['frp_max_mw'] or 0:,.1f} MW · "
        f"high confidence {headline['high_confidence']:,}",
        "",
        "## Sensor mix",
        f"- MODIS: {headline['modis']:,}",
        f"- VIIRS: {headline['viirs']:,}",
        "",
        "## Daily detections",
    ]
    for point in report["series"]:
        lines.append(f"- {point['date']}: {point['detections']:,}")

    lines += ["", f"## Top cells ({report['cell_degrees']}° grid)"]
    for cell in report["top_cells"]:
        lines.append(
            f"- {cell['latitude']:.2f}, {cell['longitude']:.2f}: "
            f"{cell['detections']:,} detections · {cell['frp_sum_mw']:,.1f} MW"
        )

    lines += ["", "## Harmonization"]
    harmonization = report["harmonization"]
    lines.append(
        f"- {harmonization['matches_total']:,} matches "
        f"({harmonization['probable']:,} probable) · {harmonization['events']:,} events "
        f"({harmonization['multi_sensor_events']:,} multi-sensor)"
    )
    lines.append(f"- {harmonization['note']}")

    lines += ["", "## Anomalies"]
    anomalies = report["anomalies"]
    if anomalies["status"] == "insufficient_history":
        lines.append("- Not enough observed history for a baseline; no claims made.")
    elif not anomalies["flagged"]:
        lines.append(f"- None flagged ({anomalies['method']}, {anomalies['baseline_source']}).")
    else:
        for item in anomalies["flagged"]:
            lines.append(
                f"- {item['date']}: {item['observed']:,.0f} vs {item['expected']:,.1f} expected "
                f"({item['severity']}, z={item['robust_z']})"
            )

    lines += ["", "## Notes"]
    lines += [f"- {note}" for note in report["notes"]]
    return "\n".join(lines) + "\n"
