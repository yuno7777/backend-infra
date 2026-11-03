from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UUIDPk


class ReportFormat(str, enum.Enum):
    json = "json"
    csv = "csv"


class Report(UUIDPk, TimestampMixin, Base):
    """Reference workload artifact. One per job (job_id unique)."""

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_reports_job_id"),
        Index("ix_reports_ws_created", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    format: Mapped[ReportFormat] = mapped_column(nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)  # relative to settings.data_dir
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)

    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finalized_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
