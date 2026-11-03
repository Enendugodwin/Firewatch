"""History runner: planning, ingestion, harmonization, resumption and jobs."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import HarmonizationCoverage, HistoryJob
from app.db.session import session_scope
from app.services import history_runner as runner
from app.services import ingestion
from app.services.firms.client import FirmsClient

KEY = "TESTKEY"
MODIS_HEADER = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_t31,frp,daynight,type\n"
)
VIIRS_HEADER = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight,type\n"
)
DEFAULT_COVERAGE = {"start": "2016-01-01", "end": "2030-12-31"}


def _handler(coverage: dict[str, str] | None = None):
    coverage = coverage or DEFAULT_COVERAGE

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/data_availability/" in url:
            source = url.rsplit("/", 1)[-1]
            start = coverage.get("start", DEFAULT_COVERAGE["start"])
            end = coverage.get("end", DEFAULT_COVERAGE["end"])
            return httpx.Response(200, text=f"min_date,max_date\n{start},{end}\n")

        parts = url.split("/")
        source = parts[7]
        day_range = int(parts[9])
        start = date.fromisoformat(parts[10])

        lines = [MODIS_HEADER if source.startswith("MODIS") else VIIRS_HEADER]
        for offset in range(day_range):
            day = (start + timedelta(days=offset)).isoformat()
            if source.startswith("MODIS"):
                lines.append(
                    f"0.000,0.000,340.2,1.0,1.0,{day},1020,Terra,MODIS,85,6.1NRT,"
                    "301.4,12.4,D,0\n"
                )
            else:
                lines.append(
                    f"0.001,0.001,341.9,0.375,0.375,{day},1025,Suomi-NPP,VIIRS,h,"
                    "2.0NRT,295.2,9.8,D,0\n"
                )
        return httpx.Response(200, text="".join(lines))

    return handle


def _client(coverage: dict[str, str] | None = None) -> FirmsClient:
    return FirmsClient(
        KEY,
        base_url="https://firms.test/api",
        max_retries=1,
        transport=httpx.MockTransport(_handler(coverage)),
        sleep=lambda _seconds: None,
    )


@pytest.fixture(autouse=True)
def _clear_coverage_cache():
    ingestion._COVERAGE_CACHE.clear()
    yield
    ingestion._COVERAGE_CACHE.clear()


def _request(
    *,
    datasets: tuple[str, ...] = ("modis_history", "viirs_snpp_history"),
    start: date = date(2016, 1, 1),
    end: date = date(2016, 1, 3),
    **kwargs,
) -> runner.HistoryRequest:
    kwargs.setdefault("harmonize", True)
    return runner.HistoryRequest(datasets=datasets, start=start, end=end, **kwargs)


def test_plan_clamps_to_reported_coverage_and_splits_windows() -> None:
    client = _client({"start": "2016-01-02", "end": "2016-01-09"})

    plan = runner.plan_history(
        _request(datasets=("modis_history",), start=date(2015, 12, 30), end=date(2016, 1, 10)),
        client=client,
    )

    [source] = plan.sources
    assert source.coverage_start == date(2016, 1, 2)
    assert source.coverage_end == date(2016, 1, 9)
    assert source.windows == [
        (date(2016, 1, 2), date(2016, 1, 6)),
        (date(2016, 1, 7), date(2016, 1, 9)),
    ]
    assert plan.total_requests == 2
    assert plan.total_days == 8
    assert "Clamped" in (source.note or "")


def test_plan_outside_coverage_has_no_windows() -> None:
    client = _client({"start": "2016-01-01", "end": "2016-01-09"})

    plan = runner.plan_history(
        _request(datasets=("modis_history",), start=date(2020, 1, 1), end=date(2020, 1, 5)),
        client=client,
    )

    [source] = plan.sources
    assert source.windows == []
    assert plan.total_requests == 0
    assert "outside the coverage" in (source.note or "")


def test_plan_warns_when_one_sensor_is_missing() -> None:
    plan = runner.plan_history(
        _request(datasets=("modis_history",), harmonize=True), client=_client()
    )

    assert plan.both_sensors is False
    assert any("both sensor families" in warning for warning in plan.warnings)


def test_run_ingests_both_sensors_and_harmonizes_the_span() -> None:
    summary = runner.run_history(
        _request(refresh_every=0), client=_client(), plan=None
    )

    assert summary["cancelled"] is False
    assert summary["total_requests"] == 2
    assert summary["requests_completed"] == 2
    assert summary["records_inserted"] == 6  # 3 days x 2 sensors
    assert summary["per_source"] == {"MODIS_SP": 3, "VIIRS_SNPP_SP": 3}
    assert summary["partitions_completed"] == 2
    assert summary["harmonization"] is not None
    assert summary["harmonization"]["processed"] == 3
    assert summary["harmonization"]["skipped"] == 0
    assert summary["harmonization"]["pairs"] >= 3

    with session_scope() as session:
        covered = session.scalar(
            select(func.count())
            .select_from(HarmonizationCoverage)
            .where(HarmonizationCoverage.scope == "world")
        )
    assert covered == 3


def test_rerun_resumes_instead_of_repeating() -> None:
    runner.run_history(_request(refresh_every=0), client=_client())

    second = runner.run_history(_request(refresh_every=0), client=_client())

    assert second["records_inserted"] == 0
    assert second["partitions_skipped"] == 2
    assert second["harmonization"]["processed"] == 0
    assert second["harmonization"]["skipped"] == 3


def test_progress_reports_phases_and_totals() -> None:
    states: list[dict] = []

    runner.run_history(
        _request(refresh_every=0), client=_client(), progress=states.append
    )

    phases = [state["phase"] for state in states]
    assert phases[0] == "planning"
    assert "ingesting" in phases
    assert "harmonizing" in phases
    assert phases[-1] == "done"
    ingest = next(state for state in states if state["phase"] == "ingesting")
    assert ingest["total"] == 2


def test_should_stop_cancels_between_windows() -> None:
    calls = {"count": 0}

    def stop() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    summary = runner.run_history(
        _request(refresh_every=0), client=_client(), should_stop=stop
    )

    assert summary["cancelled"] is True
    assert summary["requests_completed"] == 1


def test_job_row_records_progress_and_summary() -> None:
    job_id = runner.create_job(_request(refresh_every=0))

    runner.execute_history_job(job_id, client=_client())

    with session_scope() as session:
        job = session.get(HistoryJob, job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.progress["phase"] == "done"
        assert job.summary["records_inserted"] == 6
        assert job.started_at is not None
        assert job.completed_at is not None


def test_a_stale_running_job_can_be_resumed() -> None:
    job_id = runner.create_job(_request(refresh_every=0))
    with session_scope() as session:
        job = session.get(HistoryJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(UTC) - timedelta(hours=2)
        job.updated_at = datetime.now(UTC) - timedelta(hours=2)

    summary = runner.execute_history_job(job_id, client=_client())

    assert summary["records_inserted"] == 6
    with session_scope() as session:
        job = session.get(HistoryJob, job_id)
        assert job.status == "succeeded"


def test_a_live_running_job_is_not_overlapped() -> None:
    job_id = runner.create_job(_request(refresh_every=0))
    with session_scope() as session:
        job = session.get(HistoryJob, job_id)
        job.status = "running"
        job.updated_at = datetime.now(UTC)

    with pytest.raises(RuntimeError):
        runner.execute_history_job(job_id, client=_client())


def test_job_failure_is_persisted() -> None:
    job_id = runner.create_job(_request(datasets=("modis_history",)))

    # No MAP_KEY means planning raises immediately, which is a hard failure.
    unconfigured = FirmsClient(
        None, base_url="https://firms.test/api", max_retries=1, sleep=lambda _s: None
    )

    with pytest.raises(RuntimeError):
        runner.execute_history_job(job_id, client=unconfigured)

    with session_scope() as session:
        job = session.get(HistoryJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert "MAP_KEY" in (job.error_message or "")
        assert job.completed_at is not None


def test_api_lists_datasets_and_regions(client: TestClient) -> None:
    datasets = client.get("/api/v1/history/datasets")
    regions = client.get("/api/v1/history/regions")

    assert datasets.status_code == 200
    keys = {item["key"] for item in datasets.json()}
    assert {"modis_history", "viirs_history", "all_history", "nrt"} <= keys

    assert regions.status_code == 200
    region_keys = {item["key"] for item in regions.json()}
    assert "amazon" in region_keys


def test_api_rejects_an_unknown_job(client: TestClient) -> None:
    assert client.get("/api/v1/history/jobs/not-a-uuid").status_code == 400
    missing = client.get("/api/v1/history/jobs/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


def test_api_requires_a_map_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/history/plan",
        json={
            "datasets": ["modis_history"],
            "start_date": "2016-01-01",
            "end_date": "2016-01-05",
        },
    )

    assert response.status_code == 503
