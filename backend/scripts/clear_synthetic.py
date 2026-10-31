"""Remove labelled fixture rows so the database holds only real observations.

Used before demonstrating live NASA data on a development database. Deleting is
scoped to ``is_synthetic = true`` so NASA rows are never touched.
"""

from __future__ import annotations

from sqlalchemy import delete, select

from app.db.models import (
    AlgorithmRun,
    EventObservation,
    FireEvent,
    FireObservation,
    IngestionRun,
    ObservationMatch,
    RawObservation,
    SourceAvailability,
)
from app.db.session import session_scope


def clear_synthetic() -> dict[str, int]:
    removed: dict[str, int] = {}

    with session_scope() as session:
        synthetic_event_ids = list(
            session.scalars(
                select(FireEvent.id)
                .join(AlgorithmRun, FireEvent.run_id == AlgorithmRun.id)
                .where(AlgorithmRun.is_synthetic.is_(True))
            ).all()
        )
        if synthetic_event_ids:
            session.execute(
                delete(EventObservation).where(EventObservation.event_id.in_(synthetic_event_ids))
            )
            session.execute(delete(FireEvent).where(FireEvent.id.in_(synthetic_event_ids)))
            removed["events"] = len(synthetic_event_ids)

        synthetic_ids = list(
            session.scalars(
                select(FireObservation.id).where(FireObservation.is_synthetic.is_(True))
            ).all()
        )
        match_count = 0
        for start in range(0, len(synthetic_ids), 400):
            chunk = synthetic_ids[start : start + 400]
            result = session.execute(
                delete(ObservationMatch).where(ObservationMatch.observation_a_id.in_(chunk))
            )
            match_count += result.rowcount or 0
        removed["matches"] = match_count

        removed["observations"] = (
            session.execute(
                delete(FireObservation).where(FireObservation.is_synthetic.is_(True))
            ).rowcount
            or 0
        )
        removed["raw"] = (
            session.execute(
                delete(RawObservation).where(RawObservation.is_synthetic.is_(True))
            ).rowcount
            or 0
        )
        removed["ingestion_runs"] = (
            session.execute(
                delete(IngestionRun).where(IngestionRun.is_synthetic.is_(True))
            ).rowcount
            or 0
        )
        removed["algorithm_runs"] = (
            session.execute(
                delete(AlgorithmRun).where(AlgorithmRun.is_synthetic.is_(True))
            ).rowcount
            or 0
        )
        # Availability rows are date-scoped, not provenance-scoped: reset them so
        # a real availability check can rewrite them.
        removed["availability"] = session.execute(delete(SourceAvailability)).rowcount or 0

    return removed


if __name__ == "__main__":
    from app.core.logging import configure_logging

    configure_logging(json_output=False)
    print("cleared synthetic rows:", clear_synthetic())
