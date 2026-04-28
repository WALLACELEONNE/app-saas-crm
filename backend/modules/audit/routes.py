"""Audit log routes."""
from fastapi import APIRouter, Depends, Query
from core.auth import current_user
from core.db import db

router = APIRouter()


@router.get("")
async def list_audit(
    entity: str = Query(None),
    skip: int = 0, limit: int = Query(50, le=200),
    user: dict = Depends(current_user),
):
    q: dict = {"tenant_id": user["tenant_id"]}
    if entity:
        q["entity"] = entity
    cursor = db.audit_logs.find(q, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
    items = [doc async for doc in cursor]
    total = await db.audit_logs.count_documents(q)
    return {"items": items, "total": total, "skip": skip, "limit": limit}
