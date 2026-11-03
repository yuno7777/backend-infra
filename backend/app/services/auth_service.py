from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core import security
from backend.app.core.config import Settings
from backend.app.core.errors import ConflictError, ForbiddenError, UnauthenticatedError
from backend.app.models.tenants import Membership, Role, User, Workspace
from backend.app.repositories import identity as identity_repo
from backend.app.repositories import tokens as token_repo
from backend.app.services.audit_service import record_audit


def _now() -> datetime:
    return datetime.now(UTC)


async def register_user(
    session: AsyncSession, settings: Settings, *, email: str, password: str
) -> tuple[User, Workspace, Membership]:
    """Create user + personal workspace (owner) + audit rows in one transaction.

    Returns the user so the route can issue a session immediately.
    """
    existing = await identity_repo.get_user_by_email(session, email=email)
    if existing is not None:
        raise ConflictError("conflict", "An account with this email already exists.")

    user = await identity_repo.create_user(
        session, email=email, password_hash=security.hash_password(password)
    )
    workspace = await identity_repo.create_workspace(
        session, name=f"{email.lower()}'s workspace", created_by=user.id
    )
    membership = await identity_repo.add_membership(
        session, workspace_id=workspace.id, user_id=user.id, role=Role.owner
    )
    await record_audit(
        session,
        workspace_id=workspace.id,
        action="user.register",
        resource_type="user",
        resource_id=str(user.id),
        actor_user_id=user.id,
        detail={"email": user.email},
    )
    await record_audit(
        session,
        workspace_id=workspace.id,
        action="workspace.create",
        resource_type="workspace",
        resource_id=str(workspace.id),
        actor_user_id=user.id,
        detail={"name": workspace.name, "personal": True},
    )
    return user, workspace, membership


async def login(
    session: AsyncSession, settings: Settings, *, email: str, password: str
) -> tuple[str, User]:
    """Verify credentials and mint an opaque session token. Generic failure message."""
    user = await identity_repo.get_user_by_email(session, email=email)
    if user is None:
        security.verify_password(password, None)
        raise UnauthenticatedError("Invalid email or password.")

    if not security.verify_password(password, user.password_hash):
        raise UnauthenticatedError("Invalid email or password.")

    if not user.is_active:
        raise ForbiddenError("This account is deactivated.")

    token = security.new_session_token()
    token_hash = security.hash_token(token, pepper=settings.token_hash_pepper)
    expires = _now() + timedelta(days=7)
    await token_repo.create_session(session, user_id=user.id, token_hash=token_hash, expires_at=expires)

    memberships = await identity_repo.list_memberships_for_user(session, user_id=user.id)
    for _ws, _m in memberships:
        await record_audit(
            session,
            workspace_id=_ws.id,
            action="auth.login",
            resource_type="session",
            resource_id=token_hash[:12],
            actor_user_id=user.id,
            detail={"via": "password"},
        )
    return token, user


async def logout(session: AsyncSession, settings: Settings, *, token: str) -> None:
    token_hash = security.hash_token(token, pepper=settings.token_hash_pepper)
    row = await token_repo.get_active_session_by_hash(session, token_hash)
    if row is not None:
        await token_repo.revoke_session_now(session, row.id, when=_now())


async def auth_by_session_token(
    session: AsyncSession, settings: Settings, *, token: str
) -> tuple[User, dict[uuid.UUID, Membership]]:
    token_hash = security.hash_token(token, pepper=settings.token_hash_pepper)
    row = await token_repo.get_active_session_by_hash(session, token_hash)
    if row is None:
        raise UnauthenticatedError("Session token is invalid or expired.")
    user = await identity_repo.get_user(session, row.user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("Session token is invalid or expired.")
    memberships = await identity_repo.list_memberships_for_user(session, user_id=user.id)
    return user, {m.workspace_id: m for _ws, m in memberships}


async def auth_by_api_key(
    session: AsyncSession, settings: Settings, *, token: str
) -> tuple[User, uuid.UUID, Role]:
    """API keys carry exactly one workspace membership."""
    token_hash = security.hash_token(token, pepper=settings.token_hash_pepper)
    row = await token_repo.get_active_api_key_by_hash(session, token_hash)
    if row is None:
        raise UnauthenticatedError("API key is invalid or revoked.")
    if row.expires_at is not None and row.expires_at < _now():
        raise UnauthenticatedError("API key is expired.")
    user = await identity_repo.get_user(session, row.created_by)
    if user is None or not user.is_active:
        raise UnauthenticatedError("API key is invalid or revoked.")
    await token_repo.mark_api_key_used(session, row.id, when=_now())
    membership = await identity_repo.get_membership(
        session, workspace_id=row.workspace_id, user_id=user.id
    )
    if membership is None:
        raise UnauthenticatedError("API key is invalid or revoked.")
    return user, row.workspace_id, membership.role
