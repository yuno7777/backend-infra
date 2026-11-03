from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit import AuditEvent


async def record_audit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Emit one audit row. Call inside the same transaction as the change it describes.

    Every auditable event in the MVP happens inside a workspace context (personal
    workspace included), so the workspace id is required.
    """
    await session.execute(
        insert(AuditEvent).values(
            workspace_id=workspace_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_user_id=actor_user_id,
            job_id=job_id,
            detail=detail or {},
        )
    )
