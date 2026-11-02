"""Validate FIREWATCH X against documented fire events.

For each reference fire, create (or reuse) a radius region, run the regional
analysis on the reported period, and check the qualitative claim against the
stored FIRMS detections. Prints measured numbers; with ``--write`` it also writes
``docs/validation/reference_fires.md``.

This touches real data only: no synthetic rows are added, and a failed check is
reported as FAIL rather than adjusted away.

    python -m scripts.validate_reference_fire
    python -m scripts.validate_reference_fire --write
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.db.models import GeographicRegion
from app.db.session import session_scope
from app.services.reference_fires import REFERENCE_FIRES, ReferenceFire
from app.services.regional import (
    _monthly,
    _stats_rows,
    analyze_region,
    create_radius_region,
)


def _ensure_region(session, fire: ReferenceFire) -> GeographicRegion:
    region = session.scalar(
        select(GeographicRegion).where(GeographicRegion.slug == fire.slug)
    )
    if region is not None:
        return region
    return create_radius_region(
        session,
        name=fire.name,
        latitude=fire.latitude,
        longitude=fire.longitude,
        radius_km=fire.radius_km,
        slug=fire.slug,
    )


def _evaluate(fire: ReferenceFire, session) -> dict:
    region = _ensure_region(session, fire)
    summary = analyze_region(
        session,
        region,
        start=fire.start,
        end=fire.end,
        synthetic=False,
    )
    rows = _stats_rows(session, region.id, fire.start, fire.end, "ALL")
    months = _monthly(rows, start=fire.start, end=fire.end)

    total = sum(row["detections"] for row in rows)
    active_days = sum(1 for row in rows if row["detections"] > 0)
    peak = max(rows, key=lambda row: row["detections"], default=None)
    max_frp = max(
        (row["frp_max_mw"] for row in rows if row["frp_max_mw"] is not None),
        default=None,
    )
    by_month = {month["month"]: month["detections"] for month in months}
    september = by_month.get(9)
    october = by_month.get(10)

    checks: list[dict] = [
        {
            "name": "detections present",
            "passed": total > 0,
            "detail": f"{total:,} detections in {fire.radius_km:.0f} km radius",
        },
        {
            "name": "sustained activity",
            "passed": active_days >= 10,
            "detail": f"{active_days} active days",
        },
        {
            "name": "intense detections",
            "passed": max_frp is not None and max_frp >= 50,
            "detail": f"peak daily FRP {max_frp:.1f} MW" if max_frp is not None else "no FRP",
        },
    ]

    if fire.key == "amazon-para-2026":
        checks.append(
            {
                "name": "October activity above September",
                "passed": bool(
                    september is not None and october is not None and october > september
                ),
                "detail": f"Sep {september or 0:,} → Oct {october or 0:,}",
            }
        )

    return {
        "fire": fire,
        "region_id": str(region.id),
        "summary": summary,
        "total": total,
        "active_days": active_days,
        "peak": peak,
        "max_frp": max_frp,
        "months": months,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def _markdown(results: list[dict]) -> str:
    lines = [
        "# Reference fire validation",
        "",
        "Measured against the stored FIRMS detections with the regional engine. "
        "Each fire is a radius region analysed for the period it was reported in. "
        "Counts are detections, not fires.",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
    ]
    for result in results:
        fire: ReferenceFire = result["fire"]
        lines += [
            f"## {fire.name} — {fire.country}",
            "",
            f"- Centre: {fire.latitude:.3f}, {fire.longitude:.3f} · radius {fire.radius_km:.0f} km",
            f"- Period: {fire.start} → {fire.end}",
            f"- Region id: `{result['region_id']}`",
            "- Sources: " + ", ".join(fire.sources),
            "",
            f"**Result: {'PASS' if result['passed'] else 'FAIL'}**",
            "",
            "| Check | Result | Measurement |",
            "| --- | --- | --- |",
        ]
        for check in result["checks"]:
            lines.append(
                f"| {check['name']} | {'pass' if check['passed'] else 'fail'} | {check['detail']} |"
            )
        peak = result["peak"]
        lines += [
            "",
            f"- Detections: **{result['total']:,}** over {result['active_days']} active days",
            (
                f"- Peak day: **{peak['date']}** with {peak['detections']:,} detections"
                if peak
                else "- Peak day: none"
            ),
            (
                f"- Peak daily FRP: **{result['max_frp']:.1f} MW**"
                if result["max_frp"] is not None
                else "- Peak daily FRP: not reported"
            ),
        ]
        for month in result["months"]:
            lines.append(
                f"- {month['year']}-{month['month']:02d}: {month['detections']:,} detections "
                f"({month['coverage'] * 100:.0f}% coverage)"
            )
        lines += ["", f"_{fire.expected}_", ""]
        if fire.note:
            lines += [fire.note, ""]
    lines += [
        "## Limitations",
        "",
        "- A radius is a screening area; the reported event may not fill it and other fires "
        "may fall inside it.",
        "- FIRMS detections are thermal anomalies, not a fire perimeter or a damage estimate.",
        "- The comparison is qualitative. A PASS shows the platform reproduces the reported "
        "activity; it is not an accuracy score against burned area.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate against reference fires")
    parser.add_argument("--key", help="Only this reference fire")
    parser.add_argument("--write", action="store_true", help="Write docs/validation report")
    args = parser.parse_args()

    selected = [
        fire for fire in REFERENCE_FIRES if args.key is None or fire.key == args.key
    ]
    if not selected:
        raise SystemExit(f"Unknown reference fire {args.key!r}")

    results = []
    with session_scope() as session:
        for fire in selected:
            print(f"\n{fire.name} ({fire.country}) - {fire.start} -> {fire.end}")
            result = _evaluate(fire, session)
            results.append(result)
            for check in result["checks"]:
                mark = "PASS" if check["passed"] else "FAIL"
                print(f"  [{mark}] {check['name']}: {check['detail']}")
            peak = result["peak"]
            if peak:
                print(f"  peak day {peak['date']} with {peak['detections']:,} detections")
            print(f"  {result['total']:,} detections over {result['active_days']} active days")

    if args.write:
        repo_root = Path(__file__).resolve().parents[2]
        target = repo_root / "docs" / "validation" / "reference_fires.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_markdown(results), encoding="utf-8")
        print(f"\nWrote {target}")

    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
