"""Run a large detections dataset over an arbitrary date range.

Thin wrapper around ``app.services.history_runner`` so the function used by the
API is the same code exercised here.

    # what would be fetched?
    python -m scripts.history plan --datasets all_history --start 2016-01-01 --end 2024-12-31

    # ingest + harmonize an Amazon decade, resumably
    python -m scripts.history run --datasets modis_history,viirs_snpp_history \
        --start 2016-01-01 --end 2024-12-31 --region amazon --harmonize

    # the same as a durable, pollable job row
    python -m scripts.history run --datasets modis_history --start 2016-01-01 \
        --end 2024-12-31 --region amazon --job
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from app.core.logging import configure_logging
from app.services import history_runner
from app.services.firms.client import FirmsAuthError, FirmsError


def _request(args: argparse.Namespace) -> history_runner.HistoryRequest:
    datasets = tuple(part.strip() for part in args.datasets.split(",") if part.strip())
    return history_runner.HistoryRequest(
        datasets=datasets,
        start=args.start,
        end=args.end,
        region=args.region,
        bbox=args.bbox,
        harmonize=args.harmonize,
        refresh_every=args.refresh_every,
        resume=not args.no_resume,
    )


def _print_plan(plan: history_runner.HistoryPlan) -> None:
    print(
        f"Tile {plan.tile.key} ({plan.tile.bbox}): "
        f"{plan.total_requests} request(s), {plan.total_days} day(s)"
    )
    for source in plan.sources:
        coverage = (
            f"{source.coverage_start} .. {source.coverage_end}"
            if source.coverage_start and source.coverage_end
            else "unknown"
        )
        print(
            f"  {source.source_code:<18} windows={len(source.windows):>4} "
            f"days={source.days:>5} coverage={coverage}"
        )
        if source.note:
            print(f"      note: {source.note}")
    if plan.span:
        print(f"Harmonization span: {plan.span[0]} .. {plan.span[1]}")
    for warning in plan.warnings:
        print(f"  warning: {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "run"):
        cmd = sub.add_parser(name)
        cmd.add_argument(
            "--datasets",
            required=True,
            help="Comma-separated keys: " + ", ".join(sorted(history_runner.DATASETS)),
        )
        cmd.add_argument("--start", required=True, type=date.fromisoformat)
        cmd.add_argument("--end", required=True, type=date.fromisoformat)
        cmd.add_argument("--region", choices=sorted(history_runner.REGIONS))
        cmd.add_argument("--bbox", help="west,south,east,north")
        cmd.add_argument("--harmonize", action="store_true")
        cmd.add_argument("--refresh-every", type=int, default=100)
        cmd.add_argument("--no-resume", action="store_true")
        if name == "run":
            cmd.add_argument(
                "--job",
                action="store_true",
                help="Persist a history_jobs row and run it (same path as the API)",
            )

    args = parser.parse_args()
    configure_logging()

    try:
        request = _request(args)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    try:
        plan = history_runner.plan_history(request)
    except FirmsAuthError as error:
        print(str(error), file=sys.stderr)
        return 2
    except FirmsError as error:
        print(f"Coverage could not be read: {error}", file=sys.stderr)
        return 2

    _print_plan(plan)
    if args.command == "plan":
        return 0
    if plan.total_requests == 0:
        print("Nothing to do: the requested range is outside coverage.")
        return 0

    started = time.perf_counter()
    last_print = 0.0

    def progress(state: dict) -> None:
        nonlocal last_print
        now = time.perf_counter()
        if state.get("phase") == "ingesting" and now - last_print >= 5:
            last_print = now
            print(
                f"  [{state['done']}/{state['total']}] {state['source_code']} "
                f"{state['window_start']}..{state['window_end']} "
                f"inserted={state['inserted']:,} "
                f"(ETA {int((state.get('eta_seconds') or 0) / 60)}m)"
            )
        elif state.get("phase") == "harmonizing" and state.get("processed"):
            if state["processed"] % 50 == 0:
                print(
                    f"  harmonized {state['processed']}/{state['days']} day(s), "
                    f"pairs={state.get('pairs', 0):,}"
                )

    if args.job:
        job_id = history_runner.create_job(request)
        print(f"\nJob {job_id}")
        summary = history_runner.execute_history_job(job_id)
    else:
        summary = history_runner.run_history(request, plan=plan, progress=progress)

    print("\nSummary")
    print(
        f"  requests {summary['requests_completed']}/{summary['total_requests']}; "
        f"inserted {summary['records_inserted']:,}; "
        f"skipped partitions {summary['partitions_skipped']}; "
        f"failed {summary['windows_failed']}"
    )
    for code, inserted in summary["per_source"].items():
        print(f"  {code:<18} inserted {inserted:>10,}")
    if summary.get("harmonization"):
        harmonization = summary["harmonization"]
        print(
            f"  harmonized {harmonization['processed']} day(s) "
            f"(skipped {harmonization['skipped']}), "
            f"pairs {harmonization['pairs']:,}"
        )
    if summary.get("cancelled"):
        print("  cancelled between windows; rerun to resume.")
    print(f"  finished in {(time.perf_counter() - started) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
