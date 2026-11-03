from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.auth import ApiKey, Session

# --- sessions (password login bearer tokens) ---


async def create_session(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime.datetime,
) -> Session:
    row = Session(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row


async def get_active_session_by_hash(
    session: AsyncSession, token_hash: str
) -> Session | None:
    result = await session.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row and row.expires_at.replace(tzinfo=row.expires_at.tzinfo) < datetime.datetime.now(
        row.expires_at.tzinfo or datetime.UTC
    ):
        return None
    return row


async def revoke_session_now(session: AsyncSession, session_id: uuid.UUID, when: datetime.datetime) -> None:
    await session.execute(
        update(Session)
        .where(Session.id == session_id, Session.revoked_at.is_(None))
        .values(revoked_at=when)
    )


async def revoke_all_sessions_for_user(session: AsyncSession, user_id: uuid.UUID, when: datetime.datetime) -> None:
    await session.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=when)
    )


# --- api keys (workspace-scoped programmatic tokens) ---


async def create_api_key(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by: uuid.UUID,
    name: str,
    token_hash: str,
) -> ApiKey:
    row = ApiKey(workspace_id=workspace_id, created_by=created_by, name=name, token_hash=token_hash)
    session.add(row)
    await session.flush()
    return row


async def get_active_api_key_by_hash(session: AsyncSession, token_hash: str) -> ApiKey | None:
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.token_hash == token_hash,
            ApiKey.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_api_keys(session: AsyncSession, workspace_id: uuid.UUID) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.workspace_id == workspace_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_key(
    session: AsyncSession, *, workspace_id: uuid.UUID, api_key_id: uuid.UUID
) -> ApiKey | None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.workspace_id == workspace_id, ApiKey.id == api_key_id)
    )
    return result.scalar_one_or_none()


async def revoke_api_key(session: AsyncSession, api_key_id: uuid.UUID, when: datetime.datetime) -> None:
    await session.execute(
        update(ApiKey).where(ApiKey.id == api_key_id, ApiKey.revoked_at.is_(None)).values(revoked_at=when)
    )


async def mark_api_key_used(session: AsyncSession, api_key_id: uuid.UUID, when: datetime.datetime) -> None:
    # last_used_at is advisory; cheap conditional update per request is acceptable at MVP scale.
    await session.execute(
        update(ApiKey).where(ApiKey.id == api_key_id).values(last_used_at=when)
    )
