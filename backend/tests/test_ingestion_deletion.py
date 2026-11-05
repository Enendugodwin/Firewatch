"""Delete one ingestion run's data without leaving the store inconsistent."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.db.models import FireObservation, IngestionPartition, IngestionRun, RawObservation
from app.db.session import session_scope
from app.services.ingestion import ingest_csv_text

MOD = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight\n"
    "9.1,8.2,330.1,1.0,1.0,2026-12-01,1010,Terra,MODIS,80,6.1,290.2,12.5,D\n"
    "9.2,8.3,331.2,1.0,1.0,2026-12-01,1015,Terra,MODIS,70,6.1,291.1,10.0,D\n"
)


def test_preview_and_delete_an_ingestion_run(client, loaded_fixture) -> None:
    result = ingest_csv_text(
        "MODIS_SP", MOD, start_date=date(2026, 12, 1), end_date=date(2026, 12, 1)
    )
    assert result.records_inserted == 2
    with session_scope() as session:
        run = session.get(IngestionRun, result.run_id)
        assert run is not None
        run_id = str(run.id)

    preview = client.get(f"/api/v1/admin/ingestion/runs/{run_id}/preview")
    assert preview.status_code == 200, preview.text
    assert preview.json()["observations"] == 2
    assert preview.json()["raw_observations"] == 2

    refused = client.post(
        f"/api/v1/admin/ingestion/runs/{run_id}/delete", json={"confirm": False}
    )
    assert refused.status_code == 400

    deleted = client.post(
        f"/api/v1/admin/ingestion/runs/{run_id}/delete", json={"confirm": True}
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    with session_scope() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(FireObservation)
                .where(FireObservation.run_id == run_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(RawObservation)
                .where(RawObservation.run_id == run_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(IngestionPartition)
                .where(IngestionPartition.date_start == date(2026, 12, 1))
            )
            == 0
        )
        run = session.get(IngestionRun, run_id)
        assert run is not None and run.status == "deleted"

    again = client.post(
        f"/api/v1/admin/ingestion/runs/{run_id}/delete", json={"confirm": True}
    )
    assert again.status_code == 409
