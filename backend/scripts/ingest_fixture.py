"""Load the labelled synthetic fixture (demo only).

Synthetic observations are stored with ``is_synthetic = true`` so every API
response and UI view can label them. Nothing here is NASA data.
"""

from __future__ import annotations

import argparse
import csv
import io
from datetime import date
from pathlib import Path

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.services import events as events_service
from app.services import harmonization as harmonization_service
from app.services.ingestion import ingest_csv_text
from app.services.observation_queries import match_counts, sensor_counts

logger = get_logger("scripts.ingest_fixture")

FIXTURES = (
    ("MODIS_SP", "modis_sp.csv"),
    ("VIIRS_SNPP_SP", "viirs_snpp_sp.csv"),
)
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "firms_sample"


def _dates(csv_text: str) -> tuple[date, date]:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    days = sorted({date.fromisoformat(row["acq_date"]) for row in rows})
    return days[0], days[-1]


def load_fixture() -> None:
    for source_code, filename in FIXTURES:
        path = FIXTURE_DIR / filename
        text = path.read_text(encoding="utf-8")
        start, end = _dates(text)
        result = ingest_csv_text(
            source_code, text, start_date=start, end_date=end, is_synthetic=True
        )
        print(
            f"{source_code}: received {result.records_received}, "
            f"inserted {result.records_inserted}, rejected {result.records_rejected}"
        )
        for reason, count in result.rejections.items():
            print(f"  rejected {count}× {reason}")

    harmonization = harmonization_service.run_harmonization(is_synthetic=True)
    events = events_service.run_event_clustering(is_synthetic=True)
    print(
        "harmonization:",
        f"pairs {harmonization['candidate_pairs']}",
        f"probable {harmonization['probable']}",
        f"possible {harmonization['possible']}",
    )
    print("events:", f"{events['events']} estimated events", f"unclustered {events['unclustered']}")

    with session_scope() as session:
        print("stored sensors:", sensor_counts(session))
        print("match statuses:", match_counts(session))
    logger.info("fixture_loaded")


def main() -> int:
    parser = argparse.ArgumentParser(description="Load the synthetic FIREWATCH X fixture")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm that you want labelled synthetic data in this database",
    )
    args = parser.parse_args()
    configure_logging(json_output=False)

    if not args.yes:
        print(
            "This loads SYNTHETIC fixture data (clearly labelled, never NASA observations).\n"
            "Re-run with --yes to proceed."
        )
        return 1

    load_fixture()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
