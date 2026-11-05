"""Report builder: a briefing document assembled from stored data only.

A report is a snapshot of what the platform can prove for a scope: detection
totals, daily trend, ranked cells, sensor mix, harmonization counts, coverage
state and anomalies. Every number is computed by the same services the screens
use, so a report cannot disagree with the UI.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FireEvent, FireObservation, ObservationMatch
from app.services.analytics import analytics_summary
from app.services.anomalies import detect_anomalies
from app.services.calendar import daily_metrics
from app.services.observation_queries import ObservationFilters

REPORT_VERSION = "report-v1"

METHODOLOGY = (
    "Counts are NASA FIRMS thermal detections, not confirmed wildfires; a detection "
    "may be agricultural, industrial or a false positive.",
    "Days are UTC calendar days. A day with no stored detections is shown as zero "
    "only when source availability says it was observed; otherwise it is a gap.",
    "FRP is the summed Fire Radiative Power of the stored detections, in megawatts.",
    "Top cells use a fixed geographic grid, not administrative boundaries.",
    "MODIS and VIIRS counts are never interchangeable and are reported separately.",
    "Cross-sensor matches and estimated events cover the last stored association "
    "scope; the report states that scope rather than implying full coverage.",
    "Anomalies are relative to the period's own baseline; insufficient history is "
    "reported instead of guessed.",
    "This document is generated from the database; no narrative is model-written.",
)


def build_report(
    session: Session,
    filters: ObservationFilters,
    *,
    start: date,
    end: date,
    top: int = 10,
) -> dict[str, Any]:
    analytics = analytics_summary(session, filters, start=start, end=end, top=top)
    # Reuse the series the analytics pass just produced: no second full scan.
    daily = {
        date.fromisoformat(str(point["date"])[:10]): {
            "detections": point["detections"],
            "frp_sum_mw": point["frp_sum_mw"],
        }
        for point in analytics["series"]
    }
    anomalies = detect_anomalies(session, filters, start=start, end=end, daily=daily)

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
        "methodology": list(METHODOLOGY),
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

    lines += ["", "## Methodology"]
    lines += [f"- {item}" for item in report.get("methodology", [])]

    lines += ["", "## Notes"]
    lines += [f"- {note}" for note in report["notes"]]
    return "\n".join(lines) + "\n"


def report_csv(report: dict[str, Any]) -> str:
    """Daily series as CSV, with the methodology as ``#`` comment lines."""
    buffer = io.StringIO()
    buffer.write(f"# FIREWATCH X report {report['start_date']} to {report['end_date']}\n")
    buffer.write(f"# report_version,{report['version']}\n")
    for item in report.get("methodology", []):
        buffer.write(f"# methodology,{item.replace(',', ';')}\n")
    writer = csv.writer(buffer)
    writer.writerow(
        ["date", "detections", "modis", "viirs", "frp_sum_mw", "frp_max_mw", "high_confidence"]
    )
    for point in report["series"]:
        writer.writerow(
            [
                point["date"],
                point["detections"],
                point.get("modis", 0),
                point.get("viirs", 0),
                point.get("frp_sum_mw", 0),
                point.get("frp_max_mw"),
                point.get("high_confidence", 0),
            ]
        )
    return buffer.getvalue()


def report_geojson(report: dict[str, Any]) -> str:
    """Top activity cells as GeoJSON points with the report's method attached."""
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [cell["longitude"], cell["latitude"]],
            },
            "properties": {
                "detections": cell["detections"],
                "frp_sum_mw": cell["frp_sum_mw"],
                "frp_max_mw": cell.get("frp_max_mw"),
                "cell_degrees": report["cell_degrees"],
            },
        }
        for cell in report["top_cells"]
    ]
    payload = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "report_version": report["version"],
            "start_date": str(report["start_date"]),
            "end_date": str(report["end_date"]),
            "headline": report["headline"],
            "harmonization": report["harmonization"],
            "methodology": report.get("methodology", []),
            "notes": report["notes"],
        },
    }
    return json.dumps(payload, indent=2, default=str)


def report_pdf(report: dict[str, Any]) -> bytes:
    """A paginated briefing PDF built with reportlab (no browser required)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"FIREWATCH X report {report['start_date']} to {report['end_date']}",
        author="FIREWATCH X",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.grey)
    heading = ParagraphStyle("heading", parent=styles["Heading2"], fontSize=12, spaceBefore=8)
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=20, spaceAfter=4)
    story: list[Any] = [
        Paragraph("FIREWATCH X", title_style),
        Paragraph(
            f"Fire intelligence report ? {report['start_date']} ? {report['end_date']}",
            heading,
        ),
        Paragraph(
            "Satellite thermal detections are not confirmed wildfires. "
            "Read the methodology before quoting any figure.",
            small,
        ),
        Spacer(1, 6),
    ]

    headline = report["headline"]
    rows = [
        ["Detections", f"{headline['detections']:,}"],
        ["Active days", f"{headline['active_days']}/{headline['days']}"],
        ["MODIS / VIIRS", f"{headline['modis']:,} / {headline['viirs']:,}"],
        ["FRP sum", f"{headline['frp_sum_mw']:,.1f} MW"],
        ["Peak FRP", f"{(headline['frp_max_mw'] or 0):,.1f} MW"],
        ["High confidence", f"{headline['high_confidence']:,}"],
    ]
    table = Table(rows, colWidths=[55 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.lightgrey),
            ]
        )
    )
    story += [table, Spacer(1, 6), Paragraph("Methodology", heading)]
    story += [Paragraph(f"? {escape(item)}", body) for item in report.get("methodology", [])]

    story += [Paragraph("Daily detections", heading)]
    series = report["series"]
    daily_rows = [["Date", "Detections", "MODIS", "VIIRS", "FRP sum (MW)"]]
    for point in series[:400]:
        daily_rows.append(
            [
                str(point["date"]),
                f"{point['detections']:,}",
                f"{point.get('modis', 0):,}",
                f"{point.get('viirs', 0):,}",
                f"{point.get('frp_sum_mw', 0):,.1f}",
            ]
        )
    daily = Table(daily_rows, repeatRows=1)
    daily.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(daily)
    if len(series) > 400:
        story.append(Paragraph("Table truncated to the first 400 days.", small))

    story += [Paragraph(f"Top cells ({report['cell_degrees']}? grid)", heading)]
    cell_rows = [["Latitude", "Longitude", "Detections", "FRP sum (MW)"]]
    for cell in report["top_cells"]:
        cell_rows.append(
            [
                f"{cell['latitude']:.2f}",
                f"{cell['longitude']:.2f}",
                f"{cell['detections']:,}",
                f"{cell['frp_sum_mw']:,.1f}",
            ]
        )
    cells = Table(cell_rows, repeatRows=1)
    cells.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("LINEBELOW", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(cells)

    story += [PageBreak(), Paragraph("Harmonization, anomalies and notes", heading)]
    harmonization = report["harmonization"]
    story.append(
        Paragraph(
            f"{harmonization['matches_total']:,} matches "
            f"({harmonization['probable']:,} probable) ? "
            f"{harmonization['events']:,} estimated events "
            f"({harmonization['multi_sensor_events']:,} multi-sensor). "
            f"{harmonization['note']}",
            body,
        )
    )
    anomalies = report["anomalies"]
    if anomalies["status"] == "insufficient_history":
        story.append(Paragraph("Anomalies: insufficient observed history; no claims made.", body))
    elif not anomalies["flagged"]:
        story.append(Paragraph(f"Anomalies: none flagged ({anomalies['method']}).", body))
    else:
        for item in anomalies["flagged"]:
            story.append(
                Paragraph(
                    f"Anomaly {item['date']}: {item['observed']:,.0f} observed vs "
                    f"{item['expected']:,.1f} expected ({item['severity']}).",
                    body,
                )
            )
    story.append(Paragraph("Notes", heading))
    story += [Paragraph(f"? {escape(note)}", body) for note in report["notes"]]

    document.build(story)
    return buffer.getvalue()
