"""Measure cross-sensor consistency and compare activity with a burned-area table.

Two different questions are reported separately, because conflating them is how
fire dashboards end up overclaiming:

* **Corroboration** - of the VIIRS detections inside a documented fire region,
  what share also has a MODIS association? This measures how consistent the two
  independent sensors are, not how accurate the detections are.
* **Burned-area agreement** - only computed when a burned-area CSV is supplied
  (``month,area`` rows). It is a rank correlation between monthly detection
  counts and reported burned area, reported with its sample size and never as a
  percentage accuracy.

Usage:
    python -m scripts.accuracy_report --write
    python -m scripts.accuracy_report --write --burned-area burned_area.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.db.models import FireObservation, ObservationMatch
from app.db.session import session_scope
from app.services.reference_fires import REFERENCE_FIRES, ReferenceFire

MATCH_STATUSES = ("probable", "possible")


def _start(region: ReferenceFire) -> datetime:
    return datetime.combine(region.start, datetime.min.time(), tzinfo=UTC)


def _end(region: ReferenceFire) -> datetime:
    return datetime.combine(region.end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)


def _region_counts(region: ReferenceFire) -> dict[str, int]:
    lat = 111_320.0
    dlat = region.radius_km * 1000 / lat
    dlon = dlat  # generous; the association query is a box, not a circle
    with session_scope() as session:
        base = (
            select(FireObservation.sensor, func.count())
            .where(
                FireObservation.acquired_at >= _start(region),
                FireObservation.acquired_at < _end(region),
            )
            .where(
                FireObservation.latitude.between(
                    region.latitude - dlat, region.latitude + dlat
                ),
                FireObservation.longitude.between(
                    region.longitude - dlon, region.longitude + dlon
                ),
                FireObservation.is_synthetic.is_(False),
            )
            .group_by(FireObservation.sensor)
        )
        counts = {sensor: int(count) for sensor, count in session.execute(base)}

        b = FireObservation
        matched = session.scalar(
            select(func.count(func.distinct(b.id)))
            .select_from(ObservationMatch)
            .join(b, b.id == ObservationMatch.observation_b_id)
            .where(
                ObservationMatch.match_status.in_(MATCH_STATUSES),
                b.sensor == "VIIRS",
                b.latitude.between(
                    region.latitude - dlat, region.latitude + dlat
                ),
                b.longitude.between(
                    region.longitude - dlon, region.longitude + dlon
                ),
                b.acquired_at >= _start(region),
                b.acquired_at < _end(region),
            )
        )
    return {
        "modis": counts.get("MODIS", 0),
        "viirs": counts.get("VIIRS", 0),
        "matched_viirs": int(matched or 0),
    }


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and values[order[end + 1]] == values[order[index]]:
            end += 1
        average = (index + end) / 2 + 1
        for position in range(index, end + 1):
            ranks[order[position]] = average
        index = end + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry, strict=True))
    denom_x = sum((x - mean_x) ** 2 for x in rx) ** 0.5
    denom_y = sum((y - mean_y) ** 2 for y in ry) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return None
    return round(numerator / (denom_x * denom_y), 3)


def _detections_by_month(region: ReferenceFire) -> dict[str, int]:
    lat = 111_320.0
    dlat = region.radius_km * 1000 / lat
    dlon = dlat
    stamp = func.date_trunc("month", FireObservation.acquired_at)
    with session_scope() as session:
        rows = session.execute(
            select(stamp, func.count())
            .where(
                FireObservation.latitude.between(
                    region.latitude - dlat, region.latitude + dlat
                ),
                FireObservation.longitude.between(
                    region.longitude - dlon, region.longitude + dlon
                ),
                FireObservation.is_synthetic.is_(False),
            )
            .group_by(stamp)
            .order_by(stamp)
        ).all()
    return {row[0].strftime("%Y-%m"): int(row[1]) for row in rows}


def _read_burned_area(path: Path) -> dict[str, float]:
    areas: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = (row.get("month") or "").strip()
            value = (row.get("area") or row.get("burned_ha") or "").strip()
            if month and value:
                areas[month] = float(value)
    return areas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--burned-area",
        type=Path,
        help="CSV with month,area columns (aggregate monthly burned area)",
    )
    parser.add_argument("--write", action="store_true", help="Write docs/validation/accuracy.md")
    args = parser.parse_args()

    with __import__("contextlib").suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")

    burned = _read_burned_area(args.burned_area) if args.burned_area else {}

    rows: list[dict[str, Any]] = []
    for region in REFERENCE_FIRES:
        counts = _region_counts(region)
        rate = (
            counts["matched_viirs"] / counts["viirs"] if counts["viirs"] else 0.0
        )
        rows.append({**counts, "region": region, "corroboration": round(rate, 4)})

    lines = [
        "# Accuracy and consistency",
        "",
        "Generated: " + date.today().isoformat(),
        "",
        "Two questions are kept apart. **Corroboration** asks how often the two "
        "sensors agree on the same hotspot. **Burned-area agreement** is a rank "
        "correlation and is only reported when a burned-area table is supplied.",
        "",
        "## Cross-sensor corroboration",
        "",
        "| Reference region | MODIS | VIIRS | VIIRS with a MODIS association | Share |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        region = row["region"]
        lines.append(
            f"| {region.name} ({region.start} → {region.end}) | {row['modis']:,} | "
            f"{row['viirs']:,} | {row['matched_viirs']:,} | "
            f"{row['corroboration'] * 100:.1f}% |"
        )
    lines += [
        "",
        "A low share is not an error: VIIRS detects smaller and cooler fires than "
        "MODIS, so many VIIRS-only detections are expected. The share is a "
        "consistency measure, not an accuracy score, and it moves with the "
        "association thresholds.",
        "",
    ]

    if burned:
        lines += [
            "## Burned-area agreement",
            "",
            "| Reference region | Months compared | Spearman rho |",
            "| --- | ---: | ---: |",
        ]
        for region in REFERENCE_FIRES:
            monthly = _detections_by_month(region)
            months = sorted(set(monthly) & set(burned))
            rho = _spearman(
                [float(monthly[m]) for m in months],
                [burned[m] for m in months],
            )
            lines.append(
                f"| {region.name} | {len(months)} | "
                + ("not enough overlap" if rho is None else f"{rho}")
            )
        lines += [
            "",
            "Rank correlation, not accuracy. A high value means the platform's "
            "month-to-month shape agrees with the burned-area record; it does not "
            "mean every detection is a fire.",
            "",
        ]
    else:
        lines += [
            "## Burned-area agreement: not measured",
            "",
            "No burned-area table was supplied, so no agreement figure is reported. "
            "The honest next step is to download MODIS MCD64A1 (or GFED) for each "
            "reference region and rerun with `--burned-area`; inventing a figure "
            "from the platform's own data would be circular.",
            "",
        ]

    text = "\n".join(lines)
    print(text)
    if args.write:
        root = Path(__file__).resolve().parents[2]
        target = root / "docs" / "validation" / "accuracy.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
