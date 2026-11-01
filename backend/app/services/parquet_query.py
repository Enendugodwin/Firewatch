"""DuckDB analytics over exported Parquet.

DuckDB reads Parquet directly with predicate and projection pushdown, so a query
over the exported datasets touches only the columns and months it needs. This is
the offline counterpart to the PostgreSQL rollups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def _connect() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(database=":memory:")
    connection.execute("SET threads TO 2")
    # Parquet stores timestamptz; analyse it in UTC so day buckets never depend
    # on the workstation's time zone.
    connection.execute("SET TimeZone='UTC'")
    return connection


def row_count(path: Path) -> int:
    with _connect() as connection:
        row = connection.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()
    return int(row[0]) if row else 0


def summarise(path: Path) -> dict[str, Any]:
    """Columns, rows and coverage for one dataset file.

    Detections carry ``acquired_at``; the analytics rollup carries ``day``. Both
    are reported through the same shape so verification works for either.
    """
    with _connect() as connection:
        columns = [
            column[0]
            for column in connection.execute(
                "SELECT * FROM read_parquet(?) LIMIT 0", [str(path)]
            ).description
        ]
        time_column = next(
            (name for name in ("acquired_at", "day") if name in columns), None
        )
        if time_column:
            row = connection.execute(
                f"SELECT count(*), min({time_column}), max({time_column}) "
                "FROM read_parquet(?)",
                [str(path)],
            ).fetchone()
        else:
            counted = connection.execute(
                "SELECT count(*) FROM read_parquet(?)", [str(path)]
            ).fetchone()
            row = (counted[0] if counted else 0, None, None)
    values = row or (0, None, None)
    return {
        "columns": columns,
        "rows": int(values[0] or 0),
        "first_acquired_at": str(values[1]) if values[1] else None,
        "last_acquired_at": str(values[2]) if values[2] else None,
        "size_bytes": path.stat().st_size,
    }


def sensor_totals(root: Path) -> list[dict[str, Any]]:
    """Per-sensor detection totals across every exported Parquet file."""
    pattern = str(root / "harmonized" / "**" / "*.parquet")
    with _connect() as connection:
        rows = connection.execute(
            "SELECT sensor, count(*) AS detections, round(sum(frp_mw), 2) AS frp_sum "
            f"FROM read_parquet('{pattern}', hive_partitioning = true) "
            "GROUP BY sensor ORDER BY detections DESC"
        ).fetchall()
    return [
        {"sensor": row[0], "detections": int(row[1]), "frp_sum_mw": float(row[2] or 0)}
        for row in rows
    ]
