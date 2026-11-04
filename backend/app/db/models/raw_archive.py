"""Bookkeeping for raw-payload exports and their deletion.

Raw payloads are optional provenance. The console can export them for a date
range, download the archive, and then delete the payloads for that exact range.
A row here is the receipt that proves what was exported (row count and SHA-256)
before the raw rows are removed.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class RawExport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "raw_exports"

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Path relative to the raw-export root, never user supplied.
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    #: ready | deleted
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_deleted: Mapped[int | None] = mapped_column(Integer)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<RawExport {self.start_date}..{self.end_date} {self.status}>"
