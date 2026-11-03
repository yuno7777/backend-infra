from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin, UUIDPk


class WebhookEndpoint(UUIDPk, TimestampMixin, Base):
    """HTTPS endpoints receiving signed lifecycle webhooks; secret rotates by recreate."""

    __tablename__ = "webhook_endpoints"
    __table_args__ = (Index("ix_webhook_endpoints_ws", "workspace_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)  # signing secret; sensitive at rest
    events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deactivated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryState(str, enum.Enum):
    pending = "pending"
    delivering = "delivering"
    delivered = "delivered"
    failed = "failed"  # terminal after attempt budget


class WebhookDelivery(UUIDPk, TimestampMixin, Base):
    """One lifecycle event, one delivery row, with per-attempt history in attempts."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_webhook_deliveries_state", "state"),
        Index("ix_webhook_deliveries_next", "next_attempt_at"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    state: Mapped[DeliveryState] = mapped_column(nullable=False, default=DeliveryState.pending)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=6)

    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    delivered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
