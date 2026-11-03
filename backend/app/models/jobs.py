from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPk
from backend.app.domain.jobs import JobStatus


class Job(UUIDPk, TimestampMixin, Base):
    """API-facing durable job record. Queue tables remain transport internals."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_ws_created", "workspace_id", "created_at"),
        Index("ix_jobs_ws_status", "workspace_id", "status"),
        CheckConstraint("max_attempts >= 1 AND max_attempts <= 10", name="ck_jobs_max_attempts"),
        CheckConstraint("timeout_seconds >= 1 AND timeout_seconds <= 3600", name="ck_jobs_timeout"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(nullable=False, index=True)

    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    idempotency_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("idempotency_keys.id"), nullable=True, unique=True
    )

    attempts_rows: Mapped[list["JobAttempt"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobAttempt(Base):
    """One execution attempt per row; forensics feed `GET /jobs/{id}` for admins."""

    __tablename__ = "job_attempts"
    __table_args__ = (
        Index("uq_job_attempts_job_n", "job_id", "n", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="attempts_rows")
