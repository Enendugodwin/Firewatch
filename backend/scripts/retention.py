"""Apply the raw-payload retention policy.

Raw payloads are provenance only. Canonical observations, matches, events and
rollups are untouched, so the calendar and every analysis stay available after
this runs. Dry run by default:

    python -m scripts.retention                 # show what would go
    python -m scripts.retention --apply         # delete payloads past 90 days
    python -m scripts.retention --days 60 --apply
    python -m scripts.retention --apply --vacuum

``--vacuum`` rewrites ``raw_observations`` (PostgreSQL only) so the disk space is
returned; it needs an exclusive lock and takes minutes on a large store. Without
it the rows are gone and the space is reusable by the table, not by the OS.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import get_engine, session_scope
from app.services.raw_archive import retention_preview, run_retention

logger = get_logger(__name__)


def _vacuum() -> None:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        logger.info("vacuum_skipped", reason="only PostgreSQL supports VACUUM FULL here")
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM (FULL, ANALYZE) raw_observations"))
    logger.info("vacuum_complete", table="raw_observations")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=None, help="Retention window (default: setting)"
    )
    parser.add_argument("--apply", action="store_true", help="Delete (default: dry run)")
    parser.add_argument("--vacuum", action="store_true", help="VACUUM FULL after deleting")
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()

    with session_scope() as session:
        preview = retention_preview(session, settings, days=args.days)
        print(
            f"Retention: keep {preview['days']} days; cutoff {preview['cutoff']}\n"
            f"  oldest payload: {preview['oldest_day'] or 'none'}\n"
            f"  payload rows before cutoff: {preview['rows']:,}"
        )
        if not args.apply:
            print("Dry run. Re-run with --apply to delete.")
            return 0

        result = run_retention(session, settings, days=args.days, apply=True)
        print(f"  deleted: {result.get('rows_deleted', 0):,} raw payload rows")

    if args.vacuum:
        _vacuum()

    with session_scope() as session:
        from sqlalchemy import func, select

        from app.db.models import RawObservation

        total = session.scalar(select(func.count()).select_from(RawObservation)) or 0
        print(f"  raw payload rows remaining: {total:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
