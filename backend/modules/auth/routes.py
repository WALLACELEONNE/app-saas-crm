"""Authentication routes — JWT + refresh token, RBAC seeded."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from core.db import db
from core.auth import (verify_password, make_token, decode_token,
                        current_user, hash_password)
from core.repo import insert_entity

router = APIRouter()
TENANT = os.environ.get("DEFAULT_TENANT_ID", "tenant-default")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "trader"


@router.post("/login")
async def login(payload: LoginIn):
    user = await db.users.find_one({"email": payload.email.lower(), "tenant_id": TENANT})
    if not user or user.get("deleted_at"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    return {
        "access_token": make_token(user["id"], user["tenant_id"], user["role"], "access"),
        "refresh_token": make_token(user["id"], user["tenant_id"], user["role"], "refresh"),
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "name": user["name"],
                 "role": user["role"], "tenant_id": user["tenant_id"]},
    }


@router.post("/refresh")
async def refresh(payload: RefreshIn):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("kind") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    return {
        "access_token": make_token(data["sub"], data["tenant_id"], data["role"], "access"),
        "token_type": "bearer",
    }


@router.post("/register")
async def register(payload: RegisterIn, user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas admin pode registrar")
    existing = await db.users.find_one({"email": payload.email.lower(), "tenant_id": user["tenant_id"]})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email já registrado")
    new = await insert_entity("users", {
        "email": payload.email.lower(),
        "name": payload.name,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "tenant_id": user["tenant_id"],
    }, user=user)
    new.pop("password_hash", None)
    return new


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return user
