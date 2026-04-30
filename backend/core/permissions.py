"""Role permissions and tenant/branch access helpers."""
from __future__ import annotations

import os
from fastapi import HTTPException, status


DEFAULT_BRANCH_ID = os.environ.get("DEFAULT_BRANCH_ID", "branch-default")

ALL_PERMISSIONS = {
    "dashboard.view",
    "clients.view", "clients.create", "clients.update", "clients.delete",
    "pipeline.view", "pipeline.create", "pipeline.update", "pipeline.delete", "pipeline.move",
    "contracts.view", "contracts.create", "contracts.update", "contracts.delete", "contracts.approve",
    "orders.view", "orders.create", "orders.update", "orders.delete", "orders.update_status",
    "products.view", "products.create", "products.update", "products.delete",
    "logistics.view", "logistics.create", "logistics.update", "logistics.delete",
    "support.view", "support.create", "support.update", "support.delete",
    "ai.use", "ai.configure",
    "erp.view", "erp.test_connector", "erp.configure", "erp.retry",
    "audit.view",
    "users.view", "users.invite", "users.update", "users.disable",
    "branches.view", "branches.manage",
    "lgpd.export", "lgpd.anonymize",
    "settings.view", "settings.manage",
}

ROLE_PERMISSIONS = {
    "platform_admin": ALL_PERMISSIONS,
    "tenant_owner": ALL_PERMISSIONS,
    "tenant_admin": ALL_PERMISSIONS - {"settings.manage"},
    "branch_manager": {
        "dashboard.view",
        "clients.view", "clients.create", "clients.update",
        "pipeline.view", "pipeline.create", "pipeline.update", "pipeline.move",
        "contracts.view", "contracts.create", "contracts.update",
        "orders.view", "orders.create", "orders.update", "orders.update_status",
        "products.view",
        "logistics.view", "logistics.create", "logistics.update",
        "support.view", "support.update",
        "ai.use", "erp.view", "audit.view", "branches.view",
    },
    "commercial_manager": {
        "dashboard.view",
        "clients.view", "clients.create", "clients.update",
        "pipeline.view", "pipeline.create", "pipeline.update", "pipeline.move",
        "contracts.view", "contracts.create", "contracts.update",
        "orders.view", "orders.create",
        "products.view", "logistics.view", "support.view", "ai.use", "erp.view",
    },
    "trader": {
        "dashboard.view",
        "clients.view", "clients.create", "clients.update",
        "pipeline.view", "pipeline.move",
        "contracts.view", "contracts.create", "contracts.update",
        "orders.view", "orders.create",
        "products.view", "logistics.view", "support.view", "ai.use",
    },
    "logistics": {
        "dashboard.view", "clients.view", "contracts.view", "orders.view",
        "orders.update_status", "products.view",
        "logistics.view", "logistics.create", "logistics.update", "support.view",
    },
    "support": {
        "dashboard.view", "clients.view", "orders.view",
        "support.view", "support.create", "support.update", "ai.use",
    },
    "finance": {
        "dashboard.view", "clients.view", "contracts.view", "contracts.approve",
        "orders.view", "products.view", "logistics.view", "erp.view",
    },
    "auditor": {
        "dashboard.view", "clients.view", "pipeline.view", "contracts.view",
        "orders.view", "products.view", "logistics.view", "support.view",
        "erp.view", "audit.view",
    },
    "read_only": {
        "dashboard.view", "clients.view", "pipeline.view", "contracts.view",
        "orders.view", "products.view", "logistics.view", "support.view",
    },
    # Backward-compatible legacy roles.
    "admin": ALL_PERMISSIONS,
}

COLLECTION_MODULE = {
    "clients": "clients",
    "pipeline_stages": "pipeline",
    "opportunities": "pipeline",
    "interactions": "pipeline",
    "contracts": "contracts",
    "orders": "orders",
    "products": "products",
    "vehicles": "logistics",
    "cargas": "logistics",
    "tickets": "support",
}

BRANCH_SCOPED_COLLECTIONS = {
    "clients",
    "opportunities",
    "interactions",
    "contracts",
    "orders",
    "vehicles",
    "cargas",
    "tickets",
    "ai_sessions",
}


def permissions_for_role(role: str) -> set[str]:
    return set(ROLE_PERMISSIONS.get(role, set()))


def effective_permissions(membership: dict | None, fallback_role: str | None = None) -> list[str]:
    role = (membership or {}).get("role") or fallback_role or "read_only"
    permissions = permissions_for_role(role)
    permissions.update((membership or {}).get("extra_permissions") or [])
    permissions.difference_update((membership or {}).get("denied_permissions") or [])
    return sorted(permissions)


def has_permission(user: dict, permission: str) -> bool:
    return permission in set(user.get("permissions") or [])


def ensure_permission(user: dict, permission: str) -> None:
    if not has_permission(user, permission):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permissao insuficiente")


def collection_permission(collection: str, action: str) -> str | None:
    module = COLLECTION_MODULE.get(collection)
    if not module:
        return None
    return f"{module}.{action}"


def ensure_collection_permission(user: dict, collection: str, action: str) -> None:
    permission = collection_permission(collection, action)
    if permission:
        ensure_permission(user, permission)


def is_branch_scoped(collection: str) -> bool:
    return collection in BRANCH_SCOPED_COLLECTIONS


def scoped_query(user: dict, collection: str, query: dict | None = None) -> dict:
    q = dict(query or {})
    if not is_branch_scoped(collection):
        return q
    if user.get("branch_scope") == "selected":
        branch_ids = list(user.get("branch_ids") or [])
        q["branch_id"] = {"$in": branch_ids}
    return q


def ensure_branch_access(user: dict, branch_id: str | None) -> None:
    if not branch_id:
        return
    if user.get("branch_scope") == "all":
        return
    if branch_id not in set(user.get("branch_ids") or []):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Filial nao permitida")


def apply_branch_scope(data: dict, user: dict, collection: str) -> dict:
    data = dict(data)
    if not is_branch_scoped(collection):
        data.pop("branch_id", None)
        return data
    branch_id = data.get("branch_id")
    if branch_id:
        ensure_branch_access(user, branch_id)
        return data
    branch_ids = list(user.get("branch_ids") or [])
    data["branch_id"] = branch_ids[0] if branch_ids else DEFAULT_BRANCH_ID
    ensure_branch_access(user, data["branch_id"])
    return data


def ensure_document_access(user: dict, collection: str, doc: dict | None) -> None:
    if not doc:
        return
    if doc.get("tenant_id") != user.get("tenant_id"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nao encontrado")
    if is_branch_scoped(collection):
        ensure_branch_access(user, doc.get("branch_id"))
