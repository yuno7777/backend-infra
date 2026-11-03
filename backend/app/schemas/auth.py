from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.models.tenants import Role


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorResponse
    request_id: str


# --- auth ---


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    token: str
    user: UserOut


class UserOut(BaseModel):
    id: uuid.UUID
    email: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    workspaces: list[WorkspaceRef]


class WorkspaceRef(BaseModel):
    id: uuid.UUID
    name: str
    role: Role


# --- workspaces / memberships / api keys ---


class WorkspaceCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    role: Role


class WorkspaceListOut(BaseModel):
    data: list[WorkspaceOut]


class MemberAddIn(BaseModel):
    user_id: uuid.UUID
    role: Literal[Role.admin, Role.member]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: Role


class MemberListOut(BaseModel):
    data: list[MemberOut]


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreatedOut(ApiKeyOut):
    token_once: str


class ApiKeyListOut(BaseModel):
    data: list[ApiKeyOut]


UserOut.model_rebuild()
TokenOut.model_rebuild()
