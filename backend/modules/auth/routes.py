"""Authentication routes - JWT, memberships, tenant selection, and RBAC."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from core.auth import (
    current_user,
    decode_token,
    hash_password,
    make_token,
    require_permission,
    verify_password,
)
from core.db import db
from core.models import new_uuid
from core.permissions import effective_permissions
from core.repo import insert_entity

router = APIRouter()


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TenantSelectionIn(BaseModel):
    selection_token: str
    membership_id: str


class SwitchTenantIn(BaseModel):
    membership_id: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "trader"


def _membership_summary(user: dict, tenant: dict, membership: dict) -> dict:
    return {
        "membership_id": membership["id"],
        "tenant_id": tenant["id"],
        "tenant_name": tenant["name"],
        "tenant_slug": tenant.get("slug"),
        "role": membership["role"],
        "branch_scope": membership.get("branch_scope", "selected"),
        "branch_ids": membership.get("branch_ids", []),
        "user_id": user["id"],
        "user_name": user["name"],
        "email": user["email"],
    }


def _public_user(user: dict, tenant: dict, membership: dict) -> dict:
    permissions = effective_permissions(membership, user.get("role"))
    role = membership["role"]
    branch_scope = membership.get("branch_scope", "selected")
    branch_ids = membership.get("branch_ids", [])
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": role,
        "tenant_id": tenant["id"],
        "tenant": {"id": tenant["id"], "name": tenant["name"], "slug": tenant.get("slug")},
        "membership": {
            "id": membership["id"],
            "role": role,
            "branch_scope": branch_scope,
            "branch_ids": branch_ids,
            "permissions": permissions,
        },
        "permissions": permissions,
        "branch_scope": branch_scope,
        "branch_ids": branch_ids,
    }


async def _active_memberships_for_user(user: dict) -> list[dict]:
    memberships = []
    cursor = db.tenant_memberships.find(
        {"user_id": user["id"], "status": "active", "deleted_at": None},
        {"_id": 0},
    )
    async for membership in cursor:
        tenant = await db.tenants.find_one(
            {"id": membership["tenant_id"], "status": "active", "deleted_at": None},
            {"_id": 0},
        )
        if tenant:
            memberships.append({"user": user, "tenant": tenant, "membership": membership})
    return memberships


def _token_response(user: dict, tenant: dict, membership: dict) -> dict:
    public_user = _public_user(user, tenant, membership)
    return {
        "access_token": make_token(
            user["id"],
            tenant["id"],
            public_user["role"],
            "access",
            membership["id"],
            public_user["branch_scope"],
            public_user["branch_ids"],
        ),
        "refresh_token": make_token(
            user["id"],
            tenant["id"],
            public_user["role"],
            "refresh",
            membership["id"],
            public_user["branch_scope"],
            public_user["branch_ids"],
        ),
        "token_type": "bearer",
        "user": public_user,
    }


@router.post("/login")
async def login(payload: LoginIn):
    candidates = [
        user async for user in db.users.find(
            {"email": payload.email.lower(), "deleted_at": None}, {"_id": 0}
        )
    ]
    verified = None
    for user in candidates:
        if verify_password(payload.password, user.get("password_hash", "")):
            verified = user
            break
    if not verified:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais invalidas")

    memberships = await _active_memberships_for_user(verified)
    if not memberships:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Acesso sem tenant ativo")
    if len(memberships) > 1:
        return {
            "tenant_selection_required": True,
            "selection_token": make_token(verified["id"], "", "", "tenant_selection"),
            "memberships": [
                _membership_summary(item["user"], item["tenant"], item["membership"])
                for item in memberships
            ],
        }
    item = memberships[0]
    return _token_response(item["user"], item["tenant"], item["membership"])


@router.post("/select-tenant")
async def select_tenant(payload: TenantSelectionIn):
    try:
        data = decode_token(payload.selection_token)
        if data.get("kind") != "tenant_selection":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")

    user = await db.users.find_one(
        {"id": data["sub"], "deleted_at": None}, {"_id": 0}
    )
    membership = await db.tenant_memberships.find_one(
        {
            "id": payload.membership_id,
            "user_id": data["sub"],
            "status": "active",
            "deleted_at": None,
        },
        {"_id": 0},
    )
    if not user or not membership:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Membership invalida")
    tenant = await db.tenants.find_one(
        {"id": membership["tenant_id"], "status": "active", "deleted_at": None},
        {"_id": 0},
    )
    if not tenant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tenant indisponivel")
    return _token_response(user, tenant, membership)


@router.post("/switch-tenant")
async def switch_tenant(payload: SwitchTenantIn, user: dict = Depends(current_user)):
    membership = await db.tenant_memberships.find_one(
        {
            "id": payload.membership_id,
            "user_id": user["id"],
            "status": "active",
            "deleted_at": None,
        },
        {"_id": 0},
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership nao encontrada")
    tenant = await db.tenants.find_one(
        {"id": membership["tenant_id"], "status": "active", "deleted_at": None},
        {"_id": 0},
    )
    if not tenant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tenant indisponivel")
    return _token_response(user, tenant, membership)


@router.get("/memberships")
async def memberships(user: dict = Depends(current_user)):
    items = await _active_memberships_for_user(user)
    return {
        "items": [
            _membership_summary(item["user"], item["tenant"], item["membership"])
            for item in items
        ]
    }


@router.post("/refresh")
async def refresh(payload: RefreshIn):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("kind") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido")
    return {
        "access_token": make_token(
            data["sub"],
            data["tenant_id"],
            data["role"],
            "access",
            data.get("membership_id"),
            data.get("branch_scope"),
            data.get("branch_ids"),
        ),
        "token_type": "bearer",
    }


@router.post("/register")
async def register(payload: RegisterIn, user: dict = Depends(require_permission("users.invite"))):
    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": user["tenant_id"]})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email ja registrado")
    new = await insert_entity(
        "users",
        {
            "email": payload.email.lower(),
            "name": payload.name,
            "password_hash": hash_password(payload.password),
            "role": payload.role,
            "tenant_id": user["tenant_id"],
            "status": "active",
        },
        user=user,
    )
    await db.tenant_memberships.insert_one(
        {
            "id": new_uuid(),
            "tenant_id": user["tenant_id"],
            "user_id": new["id"],
            "role": payload.role,
            "branch_scope": "selected",
            "branch_ids": user.get("branch_ids", []),
            "extra_permissions": [],
            "denied_permissions": [],
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }
    )
    new.pop("password_hash", None)
    return new


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return user
