"""Generic repository helpers — ensures tenant scoping, soft-delete filter, audit."""
from typing import Optional
from datetime import datetime, timezone
from core.db import db
from core.seq import next_seq
from core.models import utcnow, new_uuid


def _strip_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


async def insert_entity(collection: str, data: dict, user: Optional[dict] = None) -> dict:
    data = dict(data)
    data.setdefault("id", new_uuid())
    data["seq_id"] = await next_seq(collection)
    data["created_at"] = utcnow()
    data["updated_at"] = utcnow()
    data.setdefault("deleted_at", None)
    if user:
        data["created_by"] = user.get("id")
        data["updated_by"] = user.get("id")
    await db[collection].insert_one(data)
    after = await db[collection].find_one({"id": data["id"]}, {"_id": 0})
    await _audit(collection, data["id"], "create", None, after, user)
    return _strip_id(after)


async def update_entity(collection: str, entity_id: str, tenant_id: str,
                        patch: dict, user: Optional[dict] = None) -> Optional[dict]:
    before = await db[collection].find_one({"id": entity_id, "tenant_id": tenant_id}, {"_id": 0})
    if not before:
        return None
    patch = dict(patch)
    patch["updated_at"] = utcnow()
    if user:
        patch["updated_by"] = user.get("id")
    await db[collection].update_one({"id": entity_id, "tenant_id": tenant_id}, {"$set": patch})
    after = await db[collection].find_one({"id": entity_id, "tenant_id": tenant_id}, {"_id": 0})
    await _audit(collection, entity_id, "update", before, after, user)
    return after


async def soft_delete(collection: str, entity_id: str, tenant_id: str,
                      user: Optional[dict] = None) -> bool:
    before = await db[collection].find_one({"id": entity_id, "tenant_id": tenant_id}, {"_id": 0})
    if not before or before.get("deleted_at"):
        return False
    now = utcnow()
    await db[collection].update_one(
        {"id": entity_id, "tenant_id": tenant_id},
        {"$set": {"deleted_at": now, "updated_at": now,
                  "updated_by": user.get("id") if user else None}},
    )
    after = await db[collection].find_one({"id": entity_id, "tenant_id": tenant_id}, {"_id": 0})
    await _audit(collection, entity_id, "delete", before, after, user)
    return True


async def find_one(collection: str, entity_id: str, tenant_id: str,
                   include_deleted: bool = False) -> Optional[dict]:
    q = {"id": entity_id, "tenant_id": tenant_id}
    if not include_deleted:
        q["deleted_at"] = None
    return await db[collection].find_one(q, {"_id": 0})


async def list_entities(collection: str, tenant_id: str, query: Optional[dict] = None,
                        skip: int = 0, limit: int = 100, sort: Optional[list] = None,
                        include_deleted: bool = False) -> list[dict]:
    q = dict(query or {})
    q["tenant_id"] = tenant_id
    if not include_deleted:
        q["deleted_at"] = None
    cursor = db[collection].find(q, {"_id": 0})
    if sort:
        cursor = cursor.sort(sort)
    cursor = cursor.skip(skip).limit(limit)
    return [doc async for doc in cursor]


async def count_entities(collection: str, tenant_id: str, query: Optional[dict] = None,
                         include_deleted: bool = False) -> int:
    q = dict(query or {})
    q["tenant_id"] = tenant_id
    if not include_deleted:
        q["deleted_at"] = None
    return await db[collection].count_documents(q)


async def _audit(entity: str, entity_id: str, action: str,
                 before: Optional[dict], after: Optional[dict],
                 user: Optional[dict]) -> None:
    log = {
        "id": new_uuid(),
        "tenant_id": (after or before or {}).get("tenant_id", "tenant-default"),
        "entity": entity,
        "entity_id": entity_id,
        "action": action,
        "before": _safe(before),
        "after": _safe(after),
        "user_id": user.get("id") if user else None,
        "user_email": user.get("email") if user else None,
        "timestamp": utcnow(),
    }
    await db.audit_logs.insert_one(log)
    # Push event for sync + integrations
    from core.events import event_bus
    event_bus.publish(f"{entity}.{action}", {"entity_id": entity_id, "after": _safe(after)})


def _safe(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            out[k] = v.astimezone(timezone.utc).isoformat()
        else:
            out[k] = v
    return out
