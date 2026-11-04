"""Ingestion: persistence, deduplication, partitions and honest failure modes."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.db.models import (
    FireObservation,
    IngestionPartition,
    IngestionRun,
    RawObservation,
    SourceAvailability,
)
from app.db.session import session_scope
from app.services.firms.client import FirmsAuthError
from app.services.firms.tiles import WORLD, date_windows, global_tiles
from app.services.ingestion import StaticCsvClient, ingest_csv_text, ingest_range

MOD = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight,type\n"
    "8.500,9.100,340.2,1.0,1.0,2026-10-28,1020,Terra,MODIS,85,6.1NRT,301.4,12.4,D,0\n"
    "8.512,9.093,331.8,1.0,1.0,2026-10-28,1110,Terra,MODIS,60,6.1NRT,299.8,6.1,D,0\n"
    "999.0,9.000,330.0,1.0,1.0,2026-10-28,1110,Terra,MODIS,60,6.1NRT,299.8,6.1,D,0\n"
)


def test_ingestion_persists_raw_and_normalized_records() -> None:
    result = ingest_csv_text(
        "MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28)
    )

    assert result.status == "succeeded"
    assert result.records_received == 3
    assert result.records_inserted == 2
    assert result.records_rejected == 1
    assert any("latitude" in reason for reason in result.rejections)

    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(FireObservation)) == 2
        assert session.scalar(select(func.count()).select_from(RawObservation)) == 2

        row = session.scalars(select(FireObservation)).first()
        assert row is not None
        assert row.sensor == "MODIS"
        assert row.is_synthetic is True
        assert row.source_product == "MODIS_SP"
        assert row.source_payload["brightness"] == "340.2"
        assert row.quality_flags["normalizer"] == "normalize-v1"


def test_reingestion_does_not_duplicate_records() -> None:
    ingest_csv_text("MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28))
    second = ingest_csv_text(
        "MODIS_SP",
        MOD,
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
    )

    assert second.records_inserted == 0

    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(FireObservation)) == 2


def test_resume_skips_completed_partitions() -> None:
    ingest_csv_text("MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28))
    again = ingest_range(
        "MODIS_SP",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
        client=StaticCsvClient(MOD),
        is_synthetic=True,
        resume=True,
    )

    assert again.partitions_skipped == 1
    assert again.partitions_completed == 0
    assert again.records_inserted == 0


def test_resume_does_not_skip_a_longer_window() -> None:
    """A one-day partition must not stand in for a four-day window."""
    ingest_csv_text("MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28))
    again = ingest_range(
        "MODIS_SP",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 29),
        client=StaticCsvClient(MOD),
        is_synthetic=True,
        resume=True,
    )

    assert again.partitions_skipped == 0
    assert again.partitions_completed == 1
    assert again.records_inserted == 0  # the same rows are deduplicated


def test_forced_rerun_reprocesses_but_still_deduplicates() -> None:
    ingest_csv_text("MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28))
    again = ingest_range(
        "MODIS_SP",
        start_date=date(2026, 10, 28),
        end_date=date(2026, 10, 28),
        client=StaticCsvClient(MOD),
        is_synthetic=True,
        resume=False,
    )

    assert again.partitions_completed == 1
    assert again.records_inserted == 0
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(FireObservation)) == 2


def test_runs_and_partitions_are_recorded_with_provenance() -> None:
    result = ingest_csv_text(
        "MODIS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28)
    )

    with session_scope() as session:
        run = session.scalars(select(IngestionRun)).first()
        partition = session.scalars(select(IngestionPartition)).first()
        availability = session.scalars(select(SourceAvailability)).all()

    assert run is not None
    assert str(run.id) == result.run_id
    assert run.status == "succeeded"
    assert run.is_synthetic is True
    assert run.query_parameters["bbox"] == WORLD.bbox

    assert partition is not None
    assert partition.status == "succeeded"
    assert partition.tile_key == "world"
    assert partition.records_received == 3

    assert [row.status for row in availability] == ["available"]


def test_missing_key_raises_auth_error_before_any_side_effect() -> None:
    with pytest.raises(FirmsAuthError):
        ingest_range(
            "MODIS_SP",
            start_date=date(2026, 10, 28),
            end_date=date(2026, 10, 28),
        )

    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(FireObservation)) == 0


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(Exception) as excinfo:
        ingest_csv_text(
            "VIIRS_MARS_SP", MOD, start_date=date(2026, 10, 28), end_date=date(2026, 10, 28)
        )
    assert "not registered" in str(excinfo.value)


def test_date_windows_respect_the_five_day_limit() -> None:
    windows = date_windows(date(2026, 1, 1), date(2026, 1, 12))

    assert windows == [
        (date(2026, 1, 1), date(2026, 1, 5)),
        (date(2026, 1, 6), date(2026, 1, 10)),
        (date(2026, 1, 11), date(2026, 1, 12)),
    ]
    with pytest.raises(ValueError):
        date_windows(date(2026, 1, 1), date(2026, 1, 2), max_days=6)


def test_global_tiling_is_deterministic_and_covers_the_globe() -> None:
    tiles = global_tiles()
    assert len(tiles) == 12 * 9
    assert len({tile.key for tile in tiles}) == len(tiles)
    assert sum(
        (tile.east - tile.west) * (tile.north - tile.south) for tile in tiles
    ) == pytest.approx(360 * 180)


def test_bulk_ingest_has_a_statement_budget_longer_than_reads() -> None:
    from app.core.config import get_settings
    from app.services.ingestion import _relax_statement_timeout

    assert get_settings().ingestion_statement_timeout_ms > 60_000
    with session_scope() as session:
        _relax_statement_timeout(session)  # no-op on SQLite, must not raise
