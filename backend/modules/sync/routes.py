"""
Mobile Sync API — Offline-first bidirectional sync (incremental, last-write-wins +
versionamento por updated_at e seq_id). Usa fila de eventos do EventBus para push.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from core.auth import current_user
from core.db import db
from core.models import utcnow, new_uuid

router = APIRouter()

# Entities exposed to mobile sync
SYNCABLE = ["clients", "products", "contracts", "orders", "opportunities",
            "pipeline_stages", "interactions", "tickets"]


class SyncPullQuery(BaseModel):
    since: Optional[str] = None  # ISO8601 — last successful sync
    entities: Optional[list[str]] = None
    limit: int = 500


class SyncRecord(BaseModel):
    entity: str
    op: str  # upsert | delete
    data: dict


class SyncPushPayload(BaseModel):
    device_id: str
    records: list[SyncRecord]


@router.post("/pull")
async def pull(query: SyncPullQuery, user: dict = Depends(current_user)):
    """Server -> mobile: incremental pull since last_sync_at."""
    since: Optional[datetime] = None
    if query.since:
        try:
            since = datetime.fromisoformat(query.since.replace("Z", "+00:00"))
        except Exception:
            since = None

    targets = query.entities or SYNCABLE
    out = {}
    for ent in targets:
        if ent not in SYNCABLE:
            continue
        q: dict = {"tenant_id": user["tenant_id"]}
        if since:
            q["updated_at"] = {"$gt": since}
        cursor = db[ent].find(q, {"_id": 0}).sort("updated_at", 1).limit(query.limit)
        out[ent] = [doc async for doc in cursor]

    return {"server_time": utcnow().isoformat(),
            "since": query.since,
            "records": out}


@router.post("/push")
async def push(payload: SyncPushPayload, user: dict = Depends(current_user)):
    """Mobile -> server: bulk upsert with last-write-wins by updated_at."""
    accepted, conflicts = [], []
    for rec in payload.records:
        if rec.entity not in SYNCABLE:
            conflicts.append({"id": rec.data.get("id"), "reason": "entity not syncable"})
            continue
        data = dict(rec.data)
        data["tenant_id"] = user["tenant_id"]
        rid = data.get("id") or new_uuid()
        data["id"] = rid

        existing = await db[rec.entity].find_one({"id": rid, "tenant_id": user["tenant_id"]},
                                                  {"_id": 0})
        if existing:
            srv_t = existing.get("updated_at")
            cli_t = data.get("updated_at")
            if isinstance(cli_t, str):
                try:
                    cli_t = datetime.fromisoformat(cli_t.replace("Z", "+00:00"))
                except Exception:
                    cli_t = utcnow()
            if not rec.force and isinstance(srv_t, datetime) and isinstance(cli_t, datetime) and srv_t > cli_t:
                conflicts.append({
                    "id": rid,
                    "entity": rec.entity,
                    "reason": "server_newer",
                    "server_updated_at": srv_t.isoformat(),
                    "client_updated_at": cli_t.isoformat() if isinstance(cli_t, datetime) else None,
                    "server": existing,
                    "client": dict(rec.data),
                })
                continue
            data["updated_at"] = utcnow() if rec.force else (cli_t if isinstance(cli_t, datetime) else utcnow())
            if rec.op == "delete":
                data["deleted_at"] = utcnow()
            await db[rec.entity].update_one(
                {"id": rid, "tenant_id": user["tenant_id"]},
                {"$set": data},
            )
        else:
            data.setdefault("created_at", utcnow())
            data["updated_at"] = utcnow()
            data.setdefault("seq_id", 0)
            if rec.op == "delete":
                data["deleted_at"] = utcnow()
            await db[rec.entity].insert_one(data)
        accepted.append(rid)

    # Log sync event
    await db.sync_events.insert_one({
        "id": new_uuid(),
        "tenant_id": user["tenant_id"],
        "device_id": payload.device_id,
        "user_id": user["id"],
        "accepted": len(accepted),
        "conflicts": len(conflicts),
        "timestamp": utcnow(),
    })

    return {"accepted_ids": accepted, "conflicts": conflicts,
            "server_time": utcnow().isoformat()}


@router.get("/info")
async def info(user: dict = Depends(current_user)):
    """Mobile clients call this to get sync metadata + entity contract."""
    return {
        "strategy": "incremental_bidirectional_lww",
        "conflict_resolution": "last-write-wins (updated_at) + server seq_id",
        "syncable_entities": SYNCABLE,
        "endpoints": {
            "pull": "/api/sync/pull",
            "push": "/api/sync/push",
        },
        "retry_policy": {"backoff": "exponential", "max_retries": 6},
        "server_time": utcnow().isoformat(),
    }
