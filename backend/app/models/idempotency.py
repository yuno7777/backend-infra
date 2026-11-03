from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UUIDPk


class IdempotencyState(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"


class IdempotencyKey(UUIDPk, TimestampMixin, Base):
    """Duplicate-write guard: unique per (workspace, key). Response replay source of truth."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        Index("uq_idempotency_ws_key", "workspace_id", "header_key", unique=True),
        Index("ix_idempotency_state", "state"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    header_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[IdempotencyState] = mapped_column(nullable=False, default=IdempotencyState.in_progress)

    response_status: Mapped[int | None] = mapped_column(index=True)  # populated on completion
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
