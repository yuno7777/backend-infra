from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ForbiddenError, UnauthenticatedError
from backend.app.models.tenants import Role, User
from backend.app.services import auth_service, workspace_service


@dataclass
class Principal:
    """Resolved identity: the user + how they authenticated."""

    user: User
    via: str  # "session" | "api_key"
    session_token: str | None = None
    api_key_workspace_id: uuid.UUID | None = None
    api_key_role: Role | None = None


async def get_db_session(
    request: Request,
) -> AsyncSession:
    """Managed DB session per request: one transaction; commit on success, rollback on error."""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def auth_header_token(authorization: str | None) -> str:
    if not authorization:
        raise UnauthenticatedError("Missing Authorization header.")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise UnauthenticatedError("Expected Authorization: Bearer <token>.")
    return value.strip()


async def get_principal(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = auth_header_token(authorization)
    if token.startswith("bk_"):
        user, workspace_id, role = await auth_service.auth_by_api_key(db, settings, token=token)
        return Principal(user=user, via="api_key", api_key_workspace_id=workspace_id, api_key_role=role)
    user, memberships = await auth_service.auth_by_session_token(db, settings, token=token)
    return Principal(user=user, via="session", session_token=token)


async def get_workspace_context(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_workspace_id: Annotated[str | None, Header()] = None,
):
    """Resolve the acting workspace or fail.

    Session principals must pass X-Workspace-Id; API keys are pinned to theirs.
    Returns (workspace_id, role).
    """
    if principal.via == "api_key":
        workspace_id = principal.api_key_workspace_id
        role = principal.api_key_role
        assert workspace_id is not None and role is not None
        return workspace_id, role

    if not x_workspace_id:
        raise UnauthenticatedError("Provide X-Workspace-Id header for workspace-scoped endpoints.")
    try:
        workspace_uuid = uuid.UUID(x_workspace_id)
    except ValueError:
        raise UnauthenticatedError("X-Workspace-Id must be a UUID.") from None

    role = await workspace_service.require_workspace_role(
        db, workspace_id=workspace_uuid, user_id=principal.user.id, required=Role.member
    )
    return workspace_uuid, role


WorkspaceCtx = Annotated[tuple[uuid.UUID, Role], Depends(get_workspace_context)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_role(required: Role):
    async def _dependency(
        context: tuple[uuid.UUID, Role] = Depends(get_workspace_context),  # noqa: B008
    ):
        workspace_id, role = context
        if not workspace_service.meets_role(role, required):
            raise ForbiddenError("Insufficient role for this operation.")
        return workspace_id, role

    return _dependency
