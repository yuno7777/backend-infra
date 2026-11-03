from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from backend.app.api.deps import DbSession, PrincipalDep, SettingsDep, require_role
from backend.app.core.errors import NotFoundError
from backend.app.models.tenants import Role
from backend.app.repositories import identity as identity_repo
from backend.app.repositories import tokens as token_repo
from backend.app.schemas import auth as auth_schemas
from backend.app.services import workspace_service

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=auth_schemas.WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: auth_schemas.WorkspaceCreateIn, principal: PrincipalDep, db: DbSession):
    workspace, role = await workspace_service.create_workspace(db, actor=principal.user, name=body.name)
    return auth_schemas.WorkspaceOut(id=workspace.id, name=workspace.name, role=role)


@router.get("", response_model=auth_schemas.WorkspaceListOut)
async def list_workspaces(principal: PrincipalDep, db: DbSession):
    pairs = await identity_repo.list_memberships_for_user(db, user_id=principal.user.id)
    return auth_schemas.WorkspaceListOut(
        data=[auth_schemas.WorkspaceOut(id=ws.id, name=ws.name, role=m.role) for ws, m in pairs]
    )


@router.get("/{workspace_id}", response_model=auth_schemas.WorkspaceOut)
async def get_workspace(workspace_id: uuid.UUID, principal: PrincipalDep, db: DbSession):
    role = await workspace_service.require_workspace_role(
        db, workspace_id=workspace_id, user_id=principal.user.id, required=Role.member
    )
    ws = await identity_repo.get_workspace(db, workspace_id)
    if ws is None:
        raise NotFoundError("Workspace not found.")
    return auth_schemas.WorkspaceOut(id=ws.id, name=ws.name, role=role)


@router.post(
    "/{workspace_id}/members",
    response_model=auth_schemas.MemberOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.admin))],
)
async def add_member(
    workspace_id: uuid.UUID,
    body: auth_schemas.MemberAddIn,
    principal: PrincipalDep,
    db: DbSession,
):
    target = await workspace_service.add_member(
        db, workspace_id=workspace_id, actor=principal.user, target_user_id=body.user_id, role=body.role
    )
    return auth_schemas.MemberOut(user_id=target.id, email=target.email, role=body.role)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.admin))],
)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSession,
):
    await workspace_service.remove_member(
        db, workspace_id=workspace_id, actor=principal.user, target_user_id=user_id
    )
    return None


@router.get(
    "/{workspace_id}/members",
    response_model=auth_schemas.MemberListOut,
    dependencies=[Depends(require_role(Role.admin))],
)
async def list_members(workspace_id: uuid.UUID, db: DbSession):
    pairs = await identity_repo.list_members(db, workspace_id)
    return auth_schemas.MemberListOut(
        data=[auth_schemas.MemberOut(user_id=u.id, email=u.email, role=m.role) for u, m in pairs]
    )


@router.post(
    "/{workspace_id}/api-keys",
    response_model=auth_schemas.ApiKeyCreatedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.admin))],
)
async def create_api_key(
    workspace_id: uuid.UUID,
    body: auth_schemas.ApiKeyCreateIn,
    principal: PrincipalDep,
    db: DbSession,
    settings: SettingsDep,
):
    row, plaintext = await workspace_service.create_api_key(
        db, settings, workspace_id=workspace_id, actor=principal.user, name=body.name
    )
    return auth_schemas.ApiKeyCreatedOut(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        token_once=plaintext,
    )


@router.get(
    "/{workspace_id}/api-keys",
    response_model=auth_schemas.ApiKeyListOut,
    dependencies=[Depends(require_role(Role.admin))],
)
async def list_api_keys(workspace_id: uuid.UUID, db: DbSession):
    keys = await token_repo.list_api_keys(db, workspace_id)
    return auth_schemas.ApiKeyListOut(
        data=[
            auth_schemas.ApiKeyOut(
                id=k.id,
                name=k.name,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                revoked_at=k.revoked_at,
            )
            for k in keys
        ]
    )


@router.delete(
    "/{workspace_id}/api-keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(Role.admin))],
)
async def revoke_api_key(
    workspace_id: uuid.UUID,
    api_key_id: uuid.UUID,
    principal: PrincipalDep,
    db: DbSession,
):
    await workspace_service.revoke_api_key(
        db, workspace_id=workspace_id, actor=principal.user, api_key_id=api_key_id
    )
    return None
