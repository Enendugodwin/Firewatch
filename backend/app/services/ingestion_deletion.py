"""Safely remove the data produced by one ingestion run.

Deleting an ingestion run must not leave the store lying. Besides the canonical
observations and raw payloads, this removes match rows that reference them, event
memberships (and now-empty events), availability for the run's window, the
resumable partitions so the window can be fetched again, harmonization coverage
for the same days, and then rebuilds the rollups for the range.

The run row itself is kept and marked ``deleted`` with a note: the audit trail
survives, the data does not.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.dialect import dialect_name
from app.db.models import (
    EventObservation,
    FireEvent,
    FireObservation,
    HarmonizationCoverage,
    IngestionPartition,
    IngestionRun,
    ObservationMatch,
    RawObservation,
    SourceAvailability,
)
from app.services import rollups
from app.services.harmonization import scope_key


class RunNotFound(LookupError):
    pass


def _run(session: Session, run_id: uuid.UUID) -> IngestionRun:
    run = session.get(IngestionRun, run_id)
    if run is None:
        raise RunNotFound("No ingestion run with that identifier.")
    return run


def _window(run: IngestionRun) -> tuple[date, date]:
    params = run.query_parameters or {}
    try:
        start = date.fromisoformat(str(params.get("start_date")))
        end = date.fromisoformat(str(params.get("end_date")))
    except ValueError as exc:
        raise ValueError("The run does not record a usable date window.") from exc
    return start, end


def _match_count(session: Session, run_id: uuid.UUID) -> int:
    ids = select(FireObservation.id).where(FireObservation.run_id == run_id)
    return int(
        session.scalar(
            select(func.count())
            .select_from(ObservationMatch)
            .where(
                (ObservationMatch.observation_a_id.in_(ids))
                | (ObservationMatch.observation_b_id.in_(ids))
            )
        )
        or 0
    )


def preview(session: Session, run_id: uuid.UUID) -> dict[str, Any]:
    run = _run(session, run_id)
    start, end = _window(run)
    params = run.query_parameters or {}
    return {
        "run_id": str(run.id),
        "source_code": run.source.source_code if run.source else None,
        "status": run.status,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "observations": int(
            session.scalar(
                select(func.count())
                .select_from(FireObservation)
                .where(FireObservation.run_id == run.id)
            )
            or 0
        ),
        "raw_observations": int(
            session.scalar(
                select(func.count())
                .select_from(RawObservation)
                .where(RawObservation.run_id == run.id)
            )
            or 0
        ),
        "matches": _match_count(session, run.id),
        "partitions": int(
            session.scalar(
                select(func.count())
                .select_from(IngestionPartition)
                .where(
                    IngestionPartition.source_id == run.source_id,
                    IngestionPartition.tile_key == str(params.get("tile", "world")),
                    IngestionPartition.date_start <= end,
                    IngestionPartition.date_end >= start,
                )
            )
            or 0
        ),
        "already_deleted": run.status == "deleted",
    }


def delete_run(session: Session, run_id: uuid.UUID) -> dict[str, Any]:
    run = _run(session, run_id)
    if run.status == "deleted":
        raise ValueError("That run's data has already been deleted.")
    start, end = _window(run)
    params = run.query_parameters or {}
    tile_key = str(params.get("tile", "world"))
    bbox = params.get("bbox")
    scope = scope_key(None)
    if bbox:
        from app.services.observation_queries import BBox

        scope = scope_key(BBox.parse(str(bbox)))

    before = preview(session, run.id)
    if dialect_name(session) == "postgresql":
        _delete_postgres(session, run, start, end, tile_key, scope)
    else:
        _delete_portable(session, run, start, end, tile_key, scope)

    run.status = "deleted"
    run.error_message = "Data removed through the admin portal."
    session.commit()
    rollups.refresh_rollup_range(session, start, end)
    return {**before, "deleted": True}


def _delete_postgres(
    session: Session,
    run: IngestionRun,
    start: date,
    end: date,
    tile_key: str,
    scope: str,
) -> None:
    session.execute(text("SET LOCAL statement_timeout = 0"))
    session.execute(text("SET LOCAL session_replication_role = replica"))
    session.execute(text("DROP TABLE IF EXISTS doomed_observations"))
    session.execute(text("DROP TABLE IF EXISTS doomed_raw_payloads"))
    session.execute(
        text(
            "CREATE TEMP TABLE doomed_observations ON COMMIT DROP AS "
            "SELECT id FROM fire_observations WHERE run_id = :run"
        ),
        {"run": run.id},
    )
    session.execute(
        text(
            "CREATE TEMP TABLE doomed_raw_payloads ON COMMIT DROP AS "
            "SELECT id FROM raw_observations WHERE run_id = :run"
        ),
        {"run": run.id},
    )
    session.execute(
        text(
            "DELETE FROM event_observations eo USING doomed_observations d "
            "WHERE eo.observation_id = d.id"
        )
    )
    session.execute(
        text(
            "DELETE FROM observation_matches m USING doomed_observations d "
            "WHERE m.observation_a_id = d.id OR m.observation_b_id = d.id"
        )
    )
    session.execute(
        text(
            "DELETE FROM fire_observations o USING doomed_observations d WHERE o.id = d.id"
        )
    )
    session.execute(
        text(
            "DELETE FROM raw_observations r USING doomed_raw_payloads d WHERE r.id = d.id"
        )
    )
    session.execute(
        text(
            "DELETE FROM fire_events e WHERE NOT EXISTS "
            "(SELECT 1 FROM event_observations eo WHERE eo.event_id = e.id)"
        )
    )
    session.execute(
        text(
            "DELETE FROM source_availability WHERE source_id = :source "
            "AND observation_date BETWEEN :start AND :end"
        ),
        {"source": run.source_id, "start": start, "end": end},
    )
    session.execute(
        text(
            "DELETE FROM ingestion_partitions WHERE source_id = :source "
            "AND tile_key = :tile AND date_start <= :end AND date_end >= :start"
        ),
        {"source": run.source_id, "tile": tile_key, "start": start, "end": end},
    )
    session.execute(
        text(
            "DELETE FROM harmonization_coverage WHERE scope = :scope "
            "AND day BETWEEN :start AND :end"
        ),
        {"scope": scope, "start": start, "end": end},
    )


def _delete_portable(
    session: Session,
    run: IngestionRun,
    start: date,
    end: date,
    tile_key: str,
    scope: str,
) -> None:
    ids = list(
        session.scalars(select(FireObservation.id).where(FireObservation.run_id == run.id))
    )
    for offset in range(0, len(ids), 400):
        chunk = ids[offset : offset + 400]
        session.execute(
            delete(EventObservation).where(EventObservation.observation_id.in_(chunk))
        )
        session.execute(
            delete(ObservationMatch).where(
                (ObservationMatch.observation_a_id.in_(chunk))
                | (ObservationMatch.observation_b_id.in_(chunk))
            )
        )
        session.execute(delete(FireObservation).where(FireObservation.id.in_(chunk)))
    session.execute(delete(RawObservation).where(RawObservation.run_id == run.id))
    members = select(EventObservation.event_id)
    session.execute(delete(FireEvent).where(~FireEvent.id.in_(members)))
    session.execute(
        delete(SourceAvailability).where(
            SourceAvailability.source_id == run.source_id,
            SourceAvailability.observation_date >= start,
            SourceAvailability.observation_date <= end,
        )
    )
    session.execute(
        delete(IngestionPartition).where(
            IngestionPartition.source_id == run.source_id,
            IngestionPartition.tile_key == tile_key,
            IngestionPartition.date_start <= end,
            IngestionPartition.date_end >= start,
        )
    )
    session.execute(
        delete(HarmonizationCoverage).where(
            HarmonizationCoverage.scope == scope,
            HarmonizationCoverage.day >= start,
            HarmonizationCoverage.day <= end,
        )
    )
