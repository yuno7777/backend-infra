from __future__ import annotations

from fastapi import APIRouter, status

from backend.app.api.deps import DbSession, PrincipalDep, SettingsDep
from backend.app.core.errors import UnauthenticatedError
from backend.app.schemas import auth as auth_schemas
from backend.app.services import auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/register", response_model=auth_schemas.TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: auth_schemas.RegisterIn, db: DbSession, settings: SettingsDep):
    user, _workspace, _membership = await auth_service.register_user(
        db, settings, email=body.email, password=body.password
    )
    token, _ = await auth_service.login(db, settings, email=body.email, password=body.password)
    return auth_schemas.TokenOut(token=token, user=auth_schemas.UserOut(id=user.id, email=user.email))


@router.post("/login", response_model=auth_schemas.TokenOut)
async def login(body: auth_schemas.LoginIn, db: DbSession, settings: SettingsDep):
    token, user = await auth_service.login(db, settings, email=body.email, password=body.password)
    return auth_schemas.TokenOut(token=token, user=auth_schemas.UserOut(id=user.id, email=user.email))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: PrincipalDep, db: DbSession, settings: SettingsDep):
    if principal.via != "session" or not principal.session_token:
        raise UnauthenticatedError("Logout requires a session token.")
    await auth_service.logout(db, settings, token=principal.session_token)
    return None


@router.get("/me", response_model=auth_schemas.MeOut)
async def me(principal: PrincipalDep, db: DbSession):
    from backend.app.repositories import identity as identity_repo

    pairs = await identity_repo.list_memberships_for_user(db, user_id=principal.user.id)
    return auth_schemas.MeOut(
        id=principal.user.id,
        email=principal.user.email,
        workspaces=[
            auth_schemas.WorkspaceRef(id=ws.id, name=ws.name, role=m.role) for ws, m in pairs
        ],
    )
