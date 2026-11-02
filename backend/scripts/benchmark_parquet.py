"""Parquet compression benchmark on real exported observations.

Samples rows from the existing harmonized export, rewrites the same frame with
each codec, and measures size, write time, read time and a simple aggregation.
Nothing is uploaded and the sample file is deleted.

    python -m scripts.benchmark_parquet
    python -m scripts.benchmark_parquet --rows 500000 --markdown
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import duckdb
import polars as pl

from app.core.config import get_settings
from app.services.datasets import dataset_root, scan_datasets

CODECS = ("zstd", "snappy", "gzip", "uncompressed")


def _sample(rows: int) -> tuple[pl.DataFrame, Path | None]:
    root = dataset_root(get_settings().local_data_directory)
    entries = [entry for entry in scan_datasets(root) if entry.get("kind") == "harmonized"]
    if not entries:
        raise SystemExit("No harmonized Parquet export found; run the dataset export first.")
    entries.sort(key=lambda entry: entry.get("records", 0), reverse=True)
    source = Path(entries[0]["local_path"])
    frame = pl.read_parquet(source).head(rows)
    return frame, source


def main() -> int:
    parser = argparse.ArgumentParser(description="Parquet codec benchmark")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    frame, source = _sample(args.rows)
    print(f"Source: {source}")
    print(f"Rows: {frame.height:,}  Columns: {frame.width}")

    rows = []
    with tempfile.TemporaryDirectory(prefix="firewatch-bench-") as directory:
        for codec in CODECS:
            target = Path(directory) / f"sample-{codec}.parquet"
            started = time.perf_counter()
            frame.write_parquet(target, compression=codec, statistics=True)
            write_seconds = time.perf_counter() - started

            started = time.perf_counter()
            reread = pl.read_parquet(target)
            read_seconds = time.perf_counter() - started

            # Warm the file cache so the codec comparison is not a cold-read race.
            duckdb.sql(
                f"SELECT sensor, count(*) AS n, sum(frp_mw) AS frp "
                f"FROM read_parquet('{target.as_posix()}') GROUP BY sensor"
            ).fetchall()
            started = time.perf_counter()
            duckdb.sql(
                f"SELECT sensor, count(*) AS n, sum(frp_mw) AS frp "
                f"FROM read_parquet('{target.as_posix()}') GROUP BY sensor"
            ).fetchall()
            query_seconds = time.perf_counter() - started

            size = target.stat().st_size
            rows.append(
                {
                    "codec": codec,
                    "bytes": size,
                    "size_mb": round(size / 1024 / 1024, 1),
                    "write_s": round(write_seconds, 2),
                    "read_s": round(read_seconds, 2),
                    "duckdb_s": round(query_seconds, 3),
                    "matches": reread.height == frame.height,
                }
            )
            target.unlink()

    baseline = next(row for row in rows if row["codec"] == "uncompressed")["bytes"]
    for row in rows:
        row["ratio"] = round(baseline / row["bytes"], 2) if row["bytes"] else None

    if args.markdown:
        print()
        print(
            "| Codec | Size | Ratio vs raw | Write (s) | Read (s) | "
            "DuckDB agg (s) | Row count intact |"
        )
        print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
        for row in rows:
            print(
                f"| {row['codec']} | {row['size_mb']} MB | {row['ratio']}x | "
                f"{row['write_s']} | {row['read_s']} | {row['duckdb_s']} | "
                f"{'yes' if row['matches'] else 'no'} |"
            )
    else:
        for row in rows:
            print(
                f"{row['codec']:12s} {row['size_mb']:8.1f} MB  ratio {row['ratio']:5.2f}x  "
                f"write {row['write_s']:6.2f}s  read {row['read_s']:6.2f}s  "
                f"duckdb {row['duckdb_s']:6.3f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
