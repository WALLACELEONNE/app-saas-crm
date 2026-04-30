"""Tenant, branch, and membership bootstrap/migration helpers."""
from __future__ import annotations

import os
from core.db import db
from core.models import new_uuid, utcnow
from core.permissions import DEFAULT_BRANCH_ID, BRANCH_SCOPED_COLLECTIONS


DEFAULT_TENANT_ID = os.environ.get("DEFAULT_TENANT_ID", "tenant-default")
DEFAULT_TENANT_NAME = os.environ.get("DEFAULT_TENANT_NAME", "Agro CRM Demo")
DEFAULT_BRANCH_NAME = os.environ.get("DEFAULT_BRANCH_NAME", "Matriz")


async def ensure_tenant_bootstrap() -> None:
    """Create the default tenant/branch/memberships for existing deployments."""
    now = utcnow()
    await db.tenants.update_one(
        {"id": DEFAULT_TENANT_ID},
        {
            "$setOnInsert": {
                "id": DEFAULT_TENANT_ID,
                "slug": "agro-crm-demo",
                "name": DEFAULT_TENANT_NAME,
                "legal_name": DEFAULT_TENANT_NAME,
                "document": None,
                "status": "active",
                "plan": "demo",
                "data_isolation_mode": "shared_db",
                "data_region": "br",
                "settings": {},
                "security_policy": {},
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        },
        upsert=True,
    )
    await db.branches.update_one(
        {"id": DEFAULT_BRANCH_ID, "tenant_id": DEFAULT_TENANT_ID},
        {
            "$setOnInsert": {
                "id": DEFAULT_BRANCH_ID,
                "tenant_id": DEFAULT_TENANT_ID,
                "name": DEFAULT_BRANCH_NAME,
                "document": None,
                "code": "MATRIZ",
                "city": None,
                "state": None,
                "is_headquarters": True,
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        },
        upsert=True,
    )
    await _ensure_memberships(now)
    await _ensure_branch_ids()


async def _ensure_memberships(now) -> None:
    async for user in db.users.find({"tenant_id": DEFAULT_TENANT_ID, "deleted_at": None}, {"_id": 0}):
        role = _membership_role_for(user)
        branch_scope = "all" if role in {"tenant_owner", "tenant_admin", "platform_admin"} else "selected"
        branch_ids = [DEFAULT_BRANCH_ID]
        await db.tenant_memberships.update_one(
            {"tenant_id": DEFAULT_TENANT_ID, "user_id": user["id"]},
            {
                "$setOnInsert": {
                    "id": new_uuid(),
                    "tenant_id": DEFAULT_TENANT_ID,
                    "user_id": user["id"],
                    "role": role,
                    "branch_scope": branch_scope,
                    "branch_ids": branch_ids,
                    "extra_permissions": [],
                    "denied_permissions": [],
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                    "deleted_at": None,
                }
            },
            upsert=True,
        )


def _membership_role_for(user: dict) -> str:
    email = (user.get("email") or "").lower()
    legacy_role = user.get("role")
    if email == "admin@agrocrm.com" or legacy_role == "admin":
        return "tenant_owner"
    if legacy_role in {"tenant_owner", "tenant_admin", "branch_manager", "commercial_manager",
                       "trader", "logistics", "support", "finance", "auditor", "read_only"}:
        return legacy_role
    return "trader"


async def _ensure_branch_ids() -> None:
    for collection in BRANCH_SCOPED_COLLECTIONS:
        await db[collection].update_many(
            {
                "tenant_id": DEFAULT_TENANT_ID,
                "$or": [{"branch_id": {"$exists": False}}, {"branch_id": None}],
            },
            {"$set": {"branch_id": DEFAULT_BRANCH_ID, "updated_at": utcnow()}},
        )
