"""Relabel availability rows that fall outside a product's reported coverage.

``empty`` means "the source observed this day and returned no detections". When a
request falls outside a product's coverage window the API returns a header-only
200, which ingestion used to record as ``empty``. That made unprocessed days look
quiet in the calendar. Coverage is definitive for standard-processing products,
so this script relabels those rows: after the coverage end they become
``not_yet_available``, before the coverage start ``missing``.

Near-real-time products are deliberately excluded: their coverage is a rolling
window, and relabelling old rows would erase a genuine record of what was observed.

Usage:
    python -m scripts.repair_availability            # dry run
    python -m scripts.repair_availability --apply
"""

from __future__ import annotations

import argparse

from sqlalchemy import select, update

from app.core.logging import configure_logging
from app.db.models import DataSource, SourceAvailability
from app.db.session import session_scope
from app.services.firms.client import FirmsAuthError, FirmsError
from app.services.ingestion import build_client
from app.services.sources import FIRMS_SOURCES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the relabelled rows")
    args = parser.parse_args()

    configure_logging()
    client = build_client()
    sp_sources = [source for source in FIRMS_SOURCES if source.is_standard_processing]

    total_changed = 0
    with session_scope() as session:
        for source in sp_sources:
            row = session.scalars(
                select(DataSource).where(DataSource.source_code == source.code)
            ).first()
            if row is None:
                print(f"{source.code}: not registered, skipped")
                continue
            try:
                coverage = client.fetch_availability(source.code)
            except (FirmsAuthError, FirmsError) as exc:
                print(f"{source.code}: coverage unavailable ({exc}), skipped")
                continue
            if coverage.min_date is None or coverage.max_date is None:
                print(f"{source.code}: coverage has no range, skipped")
                continue

            after = session.execute(
                select(SourceAvailability.observation_date)
                .where(
                    SourceAvailability.source_id == row.id,
                    SourceAvailability.status.in_(("available", "empty")),
                    SourceAvailability.observation_date > coverage.max_date,
                )
                .order_by(SourceAvailability.observation_date)
            ).scalars().all()
            before = session.execute(
                select(SourceAvailability.observation_date)
                .where(
                    SourceAvailability.source_id == row.id,
                    SourceAvailability.status.in_(("available", "empty")),
                    SourceAvailability.observation_date < coverage.min_date,
                )
                .order_by(SourceAvailability.observation_date)
            ).scalars().all()

            print(
                f"{source.code} coverage {coverage.min_date} .. {coverage.max_date}: "
                f"{len(after)} row(s) after coverage, {len(before)} before"
                + (f" ({after[0]} .. {after[-1]})" if after else "")
            )
            if not args.apply:
                continue

            if after:
                session.execute(
                    update(SourceAvailability)
                    .where(
                        SourceAvailability.source_id == row.id,
                        SourceAvailability.status.in_(("available", "empty")),
                        SourceAvailability.observation_date > coverage.max_date,
                    )
                    .values(status="not_yet_available")
                )
            if before:
                session.execute(
                    update(SourceAvailability)
                    .where(
                        SourceAvailability.source_id == row.id,
                        SourceAvailability.status.in_(("available", "empty")),
                        SourceAvailability.observation_date < coverage.min_date,
                    )
                    .values(status="missing")
                )
            total_changed += len(after) + len(before)

    if args.apply:
        print(f"\nRelabelled {total_changed} row(s).")
    else:
        print("\nDry run; pass --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
