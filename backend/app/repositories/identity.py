from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.tenants import Membership, Role, User, Workspace

# --- users ---


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, *, email: str, password_hash: str | None) -> User:
    user = User(email=email.lower(), password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def deactivate_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(update(User).where(User.id == user_id).values(is_active=False))


# --- workspaces & memberships ---


async def create_workspace(
    session: AsyncSession, *, name: str, created_by: uuid.UUID
) -> Workspace:
    workspace = Workspace(name=name, created_by=created_by)
    session.add(workspace)
    await session.flush()
    return workspace


async def get_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    return result.scalar_one_or_none()


async def add_membership(
    session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, role: Role
) -> Membership:
    membership = Membership(workspace_id=workspace_id, user_id=user_id, role=role)
    session.add(membership)
    await session.flush()
    return membership


async def get_membership(
    session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    result = await session.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_memberships_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Workspace, Membership]]:
    result = await session.execute(
        select(Workspace, Membership)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id)
        .order_by(Workspace.created_at)
    )
    return [(ws, m) for ws, m in result.all()]


async def list_members(
    session: AsyncSession, workspace_id: uuid.UUID
) -> list[tuple[User, Membership]]:
    result = await session.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(Membership.created_at)
    )
    return [(u, m) for u, m in result.all()]


async def remove_membership(
    session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    membership = await get_membership(session, workspace_id=workspace_id, user_id=user_id)
    if membership is None:
        return False
    await session.delete(membership)
    await session.flush()
    return True


async def count_owners(
    session: AsyncSession, *, workspace_id: uuid.UUID, excluding_user: uuid.UUID | None = None
) -> int:
    query = select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.role == Role.owner
    )
    if excluding_user is not None:
        query = query.where(Membership.user_id != excluding_user)
    result = await session.execute(query)
    return len(result.scalars().all())
