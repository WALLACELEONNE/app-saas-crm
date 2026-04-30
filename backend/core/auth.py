"""JWT auth + RBAC dependencies."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from core.db import db
from core.permissions import effective_permissions, ensure_permission

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_MIN = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(p: str) -> str:
    return pwd_ctx.hash(p[:72])


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(plain[:72], hashed)
    except Exception:
        return False


def make_token(
    sub: str,
    tenant_id: str,
    role: str,
    kind: str = "access",
    membership_id: Optional[str] = None,
    branch_scope: Optional[str] = None,
    branch_ids: Optional[list[str]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    if kind == "refresh":
        exp = now + timedelta(days=REFRESH_DAYS)
    else:
        exp = now + timedelta(minutes=ACCESS_MIN)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "membership_id": membership_id,
        "branch_scope": branch_scope,
        "branch_ids": branch_ids or [],
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


async def current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = decode_token(token)
        if payload.get("kind") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token kind")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = await db.users.find_one(
        {"id": payload["sub"]}, {"_id": 0, "password_hash": 0}
    )
    if not user or user.get("deleted_at") or user.get("status") == "suspended":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    tenant_id = payload.get("tenant_id")
    membership_id = payload.get("membership_id")
    if not tenant_id or not membership_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tenant context required")
    tenant = await db.tenants.find_one(
        {"id": tenant_id, "status": "active", "deleted_at": None}, {"_id": 0}
    )
    if not tenant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tenant unavailable")
    membership = await db.tenant_memberships.find_one(
        {
            "tenant_id": tenant_id,
            "user_id": user["id"],
            "id": membership_id,
            "status": "active",
            "deleted_at": None,
        },
        {"_id": 0},
    )
    if not membership:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Membership unavailable")
    permissions = effective_permissions(membership, user.get("role"))
    legacy_role = user.get("role")
    user.update({
        "tenant_id": tenant_id,
        "tenant": {"id": tenant["id"], "name": tenant["name"], "slug": tenant.get("slug")},
        "membership_id": membership["id"],
        "membership": {
            "id": membership["id"],
            "role": membership["role"],
            "branch_scope": membership.get("branch_scope", "selected"),
            "branch_ids": membership.get("branch_ids", []),
            "permissions": permissions,
        },
        "legacy_role": legacy_role,
        "role": membership["role"],
        "branch_scope": membership.get("branch_scope", "selected"),
        "branch_ids": membership.get("branch_ids", []),
        "permissions": permissions,
    })
    return user


def require_roles(*roles: str):
    async def _dep(user: dict = Depends(current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _dep


def require_permission(permission: str):
    async def _dep(user: dict = Depends(current_user)) -> dict:
        ensure_permission(user, permission)
        return user

    return _dep


def require_any_permission(permissions: list[str]):
    async def _dep(user: dict = Depends(current_user)) -> dict:
        granted = set(user.get("permissions") or [])
        if not granted.intersection(permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permission")
        return user

    return _dep
