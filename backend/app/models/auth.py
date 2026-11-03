from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPk


class Session(UUIDPk, TimestampMixin, Base):
    """Opaque bearer tokens for password logins. Only a peppered SHA-256 is stored."""

    __tablename__ = "sessions"
    __table_args__ = (Index("uq_sessions_token_hash", "token_hash", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821


class ApiKey(UUIDPk, TimestampMixin, Base):
    """Workspace-scoped programmatic tokens. Plaintext is returned exactly once."""

    __tablename__ = "api_keys"
    __table_args__ = (Index("uq_api_keys_token_hash", "token_hash", unique=True),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
