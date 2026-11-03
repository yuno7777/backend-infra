from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.core.errors import ConflictError, ForbiddenError, NotFoundError
from backend.app.core.security import hash_token, new_api_key_token
from backend.app.models.auth import ApiKey
from backend.app.models.tenants import Role, User, Workspace
from backend.app.repositories import identity as identity_repo
from backend.app.repositories import tokens as token_repo
from backend.app.services.audit_service import record_audit


def _now() -> datetime:
    return datetime.now(UTC)


def meets_role(actual: Role, required: Role) -> bool:
    rank = {Role.member: 0, Role.admin: 1, Role.owner: 2}
    return rank[actual] >= rank[required]


async def create_workspace(
    session: AsyncSession, *, actor: User, name: str
) -> tuple[Workspace, Role]:
    workspace = await identity_repo.create_workspace(session, name=name, created_by=actor.id)
    membership = await identity_repo.add_membership(
        session, workspace_id=workspace.id, user_id=actor.id, role=Role.owner
    )
    await record_audit(
        session,
        workspace_id=workspace.id,
        action="workspace.create",
        resource_type="workspace",
        resource_id=str(workspace.id),
        actor_user_id=actor.id,
        detail={"name": name},
    )
    return workspace, membership.role


async def require_workspace_role(
    session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, required: Role
) -> Role:
    membership = await identity_repo.get_membership(
        session, workspace_id=workspace_id, user_id=user_id
    )
    if membership is None:
        # Existence-oracle avoidance: foreign workspaces look like they do not exist.
        raise NotFoundError("Workspace not found.")
    if not meets_role(membership.role, required):
        raise ForbiddenError("Insufficient role for this operation.")
    return membership.role


async def add_member(
    session: AsyncSession, *, workspace_id: uuid.UUID, actor: User, target_user_id: uuid.UUID, role: Role
) -> User:
    existing = await identity_repo.get_membership(
        session, workspace_id=workspace_id, user_id=target_user_id
    )
    if existing is not None:
        raise ConflictError("conflict", "User is already a member of this workspace.")
    target = await identity_repo.get_user(session, target_user_id)
    if target is None:
        # Do not leak whether the user exists outside the workspace context.
        raise NotFoundError("User not found.")
    await identity_repo.add_membership(
        session, workspace_id=workspace_id, user_id=target_user_id, role=role
    )
    await record_audit(
        session,
        workspace_id=workspace_id,
        action="member.add",
        resource_type="membership",
        resource_id=str(target_user_id),
        actor_user_id=actor.id,
        detail={"role": role.value},
    )
    return target


async def remove_member(
    session: AsyncSession, *, workspace_id: uuid.UUID, actor: User, target_user_id: uuid.UUID
) -> None:
    target_membership = await identity_repo.get_membership(
        session, workspace_id=workspace_id, user_id=target_user_id
    )
    if target_membership is None:
        raise NotFoundError("Membership not found.")
    actor_membership = await identity_repo.get_membership(
        session, workspace_id=workspace_id, user_id=actor.id
    )
    if actor_membership is None:
        raise ForbiddenError("Insufficient role for this operation.")
    if target_membership.role == Role.owner:
        if not meets_role(actor_membership.role, Role.owner):
            raise ForbiddenError("Only owners can remove owners.")
        remaining = await identity_repo.count_owners(
            session, workspace_id=workspace_id, excluding_user=target_user_id
        )
        if remaining == 0:
            raise ConflictError("conflict", "Cannot remove the last owner of a workspace.")
    await identity_repo.remove_membership(session, workspace_id=workspace_id, user_id=target_user_id)
    await record_audit(
        session,
        workspace_id=workspace_id,
        action="member.remove",
        resource_type="membership",
        resource_id=str(target_user_id),
        actor_user_id=actor.id,
        detail={"removed_role": target_membership.role.value},
    )


async def create_api_key(
    session: AsyncSession, settings: Settings, *, workspace_id: uuid.UUID, actor: User, name: str
) -> tuple[ApiKey, str]:
    plaintext = new_api_key_token()
    token_hash = hash_token(plaintext, pepper=settings.token_hash_pepper)
    row = await token_repo.create_api_key(
        session,
        workspace_id=workspace_id,
        created_by=actor.id,
        name=name,
        token_hash=token_hash,
    )
    await record_audit(
        session,
        workspace_id=workspace_id,
        action="api_key.create",
        resource_type="api_key",
        resource_id=str(row.id),
        actor_user_id=actor.id,
        detail={"name": name},
    )
    return row, plaintext


async def revoke_api_key(
    session: AsyncSession, *, workspace_id: uuid.UUID, actor: User, api_key_id: uuid.UUID
) -> None:
    row = await token_repo.get_api_key(session, workspace_id=workspace_id, api_key_id=api_key_id)
    if row is None:
        raise NotFoundError("API key not found.")
    if row.revoked_at is not None:
        raise ConflictError("conflict", "API key is already revoked.")
    await token_repo.revoke_api_key(session, row.id, when=_now())
    await record_audit(
        session,
        workspace_id=workspace_id,
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=str(row.id),
        actor_user_id=actor.id,
        detail={"name": row.name},
    )
