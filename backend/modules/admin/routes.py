"""Tenant administration: branches, users, roles, and effective permissions."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from core.auth import current_user
from core.db import db
from core.models import new_uuid, utcnow
from core.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS, effective_permissions, ensure_permission
from core.auth import hash_password
from core.repo import write_audit

router = APIRouter()
EXPORT_COLLECTIONS = [
    "tenants", "branches", "tenant_memberships", "users",
    "clients", "products", "pipeline_stages", "opportunities", "interactions",
    "contracts", "orders", "vehicles", "cargas", "tickets",
    "audit_logs",
]
EXPORT_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "headers",
}


class BranchIn(BaseModel):
    name: str
    code: str
    document: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_headquarters: bool = False
    status: str = "active"


class BranchPatch(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    document: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_headquarters: Optional[bool] = None
    status: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    role: str = "trader"
    branch_scope: str = "selected"
    branch_ids: list[str] = Field(default_factory=list)
    extra_permissions: list[str] = Field(default_factory=list)
    denied_permissions: list[str] = Field(default_factory=list)


class MembershipPatch(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    branch_scope: Optional[str] = None
    branch_ids: Optional[list[str]] = None
    extra_permissions: Optional[list[str]] = None
    denied_permissions: Optional[list[str]] = None
    status: Optional[str] = None
    user_status: Optional[str] = None


def _can_assign_role(actor: dict, role: str) -> bool:
    actor_role = actor.get("role")
    if actor_role in {"platform_admin", "tenant_owner"}:
        return role != "platform_admin" or actor_role == "platform_admin"
    if actor_role == "tenant_admin":
        return role not in {"platform_admin", "tenant_owner"}
    return False


def _validate_role(actor: dict, role: str) -> None:
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Role invalida")
    if not _can_assign_role(actor, role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role nao permitida")


def _validate_permissions(values: list[str] | None, actor: dict | None = None) -> list[str]:
    values = values or []
    invalid = sorted(set(values) - set(ALL_PERMISSIONS))
    if invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Permissoes invalidas: {', '.join(invalid)}")
    if actor and actor.get("role") not in {"platform_admin", "tenant_owner"}:
        outside_actor = sorted(set(values) - set(actor.get("permissions") or []))
        if outside_actor:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permissao extra nao permitida")
    return sorted(set(values))


async def _validate_branches(tenant_id: str, branch_scope: str, branch_ids: list[str]) -> list[str]:
    if branch_scope not in {"all", "selected"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "branch_scope invalido")
    if branch_scope == "all":
        return []
    if not branch_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Selecione ao menos uma filial")
    count = await db.branches.count_documents({
        "tenant_id": tenant_id,
        "id": {"$in": branch_ids},
        "deleted_at": None,
        "status": "active",
    })
    if count != len(set(branch_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Filial invalida")
    return sorted(set(branch_ids))


async def _user_row(user_doc: dict, membership: dict, branch_map: dict[str, str]) -> dict:
    branch_ids = membership.get("branch_ids", [])
    return {
        "id": user_doc["id"],
        "email": user_doc["email"],
        "name": user_doc["name"],
        "status": user_doc.get("status", "active"),
        "membership_id": membership["id"],
        "role": membership["role"],
        "membership_status": membership.get("status", "active"),
        "branch_scope": membership.get("branch_scope", "selected"),
        "branch_ids": branch_ids,
        "branch_names": [branch_map.get(bid, bid) for bid in branch_ids],
        "extra_permissions": membership.get("extra_permissions", []),
        "denied_permissions": membership.get("denied_permissions", []),
        "effective_permissions": effective_permissions(membership, user_doc.get("role")),
    }


@router.get("/roles")
async def roles(user: dict = Depends(current_user)):
    ensure_permission(user, "users.view")
    return {
        "permissions": sorted(ALL_PERMISSIONS),
        "roles": [
            {"id": role, "permissions": sorted(perms)}
            for role, perms in sorted(ROLE_PERMISSIONS.items())
            if role != "admin"
        ],
    }


@router.get("/branches")
async def list_branches(user: dict = Depends(current_user)):
    ensure_permission(user, "branches.view")
    cursor = db.branches.find(
        {"tenant_id": user["tenant_id"], "deleted_at": None},
        {"_id": 0},
    ).sort([("is_headquarters", -1), ("name", 1)])
    return {"items": [doc async for doc in cursor]}


@router.post("/branches", status_code=201)
async def create_branch(payload: BranchIn, user: dict = Depends(current_user)):
    ensure_permission(user, "branches.manage")
    code = payload.code.strip().upper()
    existing = await db.branches.find_one({
        "tenant_id": user["tenant_id"],
        "code": code,
        "deleted_at": None,
    })
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Codigo de filial ja existe")
    doc = payload.model_dump()
    doc.update({
        "id": new_uuid(),
        "tenant_id": user["tenant_id"],
        "code": code,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "deleted_at": None,
    })
    await db.branches.insert_one(doc)
    after = await db.branches.find_one({"id": doc["id"]}, {"_id": 0})
    await write_audit("branches", doc["id"], "create", None, after, user)
    return after


@router.patch("/branches/{branch_id}")
async def update_branch(branch_id: str, payload: BranchPatch, user: dict = Depends(current_user)):
    ensure_permission(user, "branches.manage")
    before = await db.branches.find_one(
        {"id": branch_id, "tenant_id": user["tenant_id"], "deleted_at": None},
        {"_id": 0},
    )
    if not before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Filial nao encontrada")
    patch = payload.model_dump(exclude_unset=True)
    if "code" in patch and patch["code"]:
        patch["code"] = patch["code"].strip().upper()
    patch["updated_at"] = utcnow()
    await db.branches.update_one({"id": branch_id}, {"$set": patch})
    after = await db.branches.find_one({"id": branch_id}, {"_id": 0})
    await write_audit("branches", branch_id, "update", before, after, user)
    return after


@router.get("/users")
async def list_users(skip: int = 0, limit: int = Query(50, le=200), user: dict = Depends(current_user)):
    ensure_permission(user, "users.view")
    branch_map = {
        doc["id"]: doc["name"]
        async for doc in db.branches.find({"tenant_id": user["tenant_id"]}, {"_id": 0, "id": 1, "name": 1})
    }
    q = {"tenant_id": user["tenant_id"], "deleted_at": None}
    cursor = db.tenant_memberships.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    rows = []
    async for membership in cursor:
        user_doc = await db.users.find_one({"id": membership["user_id"], "deleted_at": None}, {"_id": 0, "password_hash": 0})
        if user_doc:
            rows.append(await _user_row(user_doc, membership, branch_map))
    total = await db.tenant_memberships.count_documents(q)
    return {"items": rows, "total": total, "skip": skip, "limit": limit}


@router.post("/users", status_code=201)
async def create_user(payload: UserCreate, user: dict = Depends(current_user)):
    ensure_permission(user, "users.invite")
    _validate_role(user, payload.role)
    extra = _validate_permissions(payload.extra_permissions, user)
    denied = _validate_permissions(payload.denied_permissions)
    branch_ids = await _validate_branches(user["tenant_id"], payload.branch_scope, payload.branch_ids)

    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": user["tenant_id"], "deleted_at": None})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email ja registrado")
    now = datetime.now(timezone.utc)
    user_doc = {
        "id": new_uuid(),
        "tenant_id": user["tenant_id"],
        "email": payload.email.lower(),
        "name": payload.name,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "created_by": user["id"],
        "updated_by": user["id"],
    }
    membership = {
        "id": new_uuid(),
        "tenant_id": user["tenant_id"],
        "user_id": user_doc["id"],
        "role": payload.role,
        "branch_scope": payload.branch_scope,
        "branch_ids": branch_ids,
        "extra_permissions": extra,
        "denied_permissions": denied,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    await db.users.insert_one(user_doc)
    await db.tenant_memberships.insert_one(membership)
    safe_user = {k: v for k, v in user_doc.items() if k != "password_hash"}
    await write_audit("users", user_doc["id"], "create", None, safe_user, user)
    await write_audit("tenant_memberships", membership["id"], "create", None, membership, user)
    branch_map = {
        doc["id"]: doc["name"]
        async for doc in db.branches.find({"tenant_id": user["tenant_id"]}, {"_id": 0, "id": 1, "name": 1})
    }
    return await _user_row(safe_user, membership, branch_map)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: MembershipPatch, user: dict = Depends(current_user)):
    if payload.status == "suspended" or payload.user_status == "suspended":
        ensure_permission(user, "users.disable")
    else:
        ensure_permission(user, "users.update")
    target_user = await db.users.find_one({"id": user_id, "tenant_id": user["tenant_id"], "deleted_at": None}, {"_id": 0, "password_hash": 0})
    membership = await db.tenant_memberships.find_one({"user_id": user_id, "tenant_id": user["tenant_id"], "deleted_at": None}, {"_id": 0})
    if not target_user or not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario nao encontrado")
    if target_user["id"] == user["id"] and (payload.status == "suspended" or payload.user_status == "suspended"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nao suspenda seu proprio acesso")

    membership_patch = {}
    if payload.role is not None:
        _validate_role(user, payload.role)
        membership_patch["role"] = payload.role
    branch_scope = payload.branch_scope if payload.branch_scope is not None else membership.get("branch_scope", "selected")
    branch_ids = payload.branch_ids if payload.branch_ids is not None else membership.get("branch_ids", [])
    if payload.branch_scope is not None or payload.branch_ids is not None:
        membership_patch["branch_scope"] = branch_scope
        membership_patch["branch_ids"] = await _validate_branches(user["tenant_id"], branch_scope, branch_ids)
    if payload.extra_permissions is not None:
        membership_patch["extra_permissions"] = _validate_permissions(payload.extra_permissions, user)
    if payload.denied_permissions is not None:
        membership_patch["denied_permissions"] = _validate_permissions(payload.denied_permissions)
    if payload.status is not None:
        if payload.status not in {"active", "suspended"}:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Status invalido")
        membership_patch["status"] = payload.status

    user_patch = {}
    if payload.name is not None:
        user_patch["name"] = payload.name
    if payload.role is not None:
        user_patch["role"] = payload.role
    if payload.user_status is not None:
        if payload.user_status not in {"active", "suspended"}:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Status de usuario invalido")
        user_patch["status"] = payload.user_status

    if membership_patch:
        membership_patch["updated_at"] = utcnow()
        before = dict(membership)
        await db.tenant_memberships.update_one({"id": membership["id"]}, {"$set": membership_patch})
        membership = await db.tenant_memberships.find_one({"id": membership["id"]}, {"_id": 0})
        await write_audit("tenant_memberships", membership["id"], "update", before, membership, user)
    if user_patch:
        user_patch["updated_at"] = utcnow()
        user_patch["updated_by"] = user["id"]
        before_user = dict(target_user)
        await db.users.update_one({"id": user_id, "tenant_id": user["tenant_id"]}, {"$set": user_patch})
        target_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
        await write_audit("users", user_id, "update", before_user, target_user, user)

    branch_map = {
        doc["id"]: doc["name"]
        async for doc in db.branches.find({"tenant_id": user["tenant_id"]}, {"_id": 0, "id": 1, "name": 1})
    }
    return await _user_row(target_user, membership, branch_map)


def _export_safe(collection: str, doc: dict) -> dict:
    return _scrub_export({k: v for k, v in doc.items() if k != "_id"})


def _scrub_export(value):
    if isinstance(value, dict):
        return {
            k: _scrub_export(v)
            for k, v in value.items()
            if k.lower() not in EXPORT_SENSITIVE_KEYS and k != "_id"
        }
    if isinstance(value, list):
        return [_scrub_export(v) for v in value]
    return value


@router.get("/lgpd/export")
async def export_tenant_data(user: dict = Depends(current_user)):
    ensure_permission(user, "lgpd.export")
    payload = {
        "tenant_id": user["tenant_id"],
        "exported_at": utcnow(),
        "exported_by": user["id"],
        "collections": {},
    }
    for collection in EXPORT_COLLECTIONS:
        if collection == "tenants":
            query = {"id": user["tenant_id"]}
        elif collection == "users":
            membership_user_ids = [
                m["user_id"]
                async for m in db.tenant_memberships.find(
                    {"tenant_id": user["tenant_id"], "deleted_at": None},
                    {"_id": 0, "user_id": 1},
                )
            ]
            query = {"id": {"$in": membership_user_ids}, "deleted_at": None}
        else:
            query = {"tenant_id": user["tenant_id"]}
        cursor = db[collection].find(query, {"_id": 0}).limit(10000)
        payload["collections"][collection] = [_export_safe(collection, doc) async for doc in cursor]
    await write_audit("lgpd", user["tenant_id"], "export", None, {"collections": list(payload["collections"].keys())}, user)
    return payload


@router.post("/lgpd/clients/{client_id}/anonymize")
async def anonymize_client(client_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "lgpd.anonymize")
    before = await db.clients.find_one(
        {"id": client_id, "tenant_id": user["tenant_id"], "deleted_at": None},
        {"_id": 0},
    )
    if not before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente nao encontrado")
    anon_name = f"Cliente anonimizado #{before.get('seq_id', '')}".strip()
    now = utcnow()
    patch = {
        "name": anon_name,
        "doc": None,
        "contacts": [],
        "notes": None,
        "lgpd_anonymized_at": now,
        "lgpd_anonymized_by": user["id"],
        "updated_at": now,
        "updated_by": user["id"],
    }
    await db.clients.update_one({"id": client_id, "tenant_id": user["tenant_id"]}, {"$set": patch})
    for collection in ("contracts", "orders", "opportunities", "tickets"):
        await db[collection].update_many(
            {"tenant_id": user["tenant_id"], "client_id": client_id},
            {"$set": {"client_name": anon_name, "updated_at": now, "updated_by": user["id"]}},
        )
    after = await db.clients.find_one({"id": client_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    await write_audit("clients", client_id, "lgpd_anonymize", before, after, user)
    return {"anonymized": True, "client_id": client_id, "name": anon_name}
