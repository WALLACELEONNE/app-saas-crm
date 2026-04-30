"""Tenant-scoped ERP integration routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.auth import current_user
from core.db import db
from core.events import event_bus
from core.models import new_uuid, utcnow
from core.permissions import ensure_permission
from .circuit_breaker import breaker
from .worker import erp_worker

router = APIRouter()
SUPPORTED_VENDORS = {
    "sap": "SAP S/4HANA",
    "oracle": "Oracle EBS",
    "siagri": "Siagri Agribusiness",
}


@router.get("/connectors")
async def connectors(user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    active = await erp_worker.connectors_for_tenant(user["tenant_id"])
    out = []
    for vendor, name in SUPPORTED_VENDORS.items():
        connector = active.get(vendor)
        out.append({
            "vendor": vendor,
            "name": connector.name if connector else name,
            "topics": list(connector.topics) if connector else [],
            "endpoint": connector.endpoint if connector else None,
            "enabled": connector is not None,
            "transport": ["REST", "Webhook"],
        })
    return {"connectors": out}


class ConnectorConfig(BaseModel):
    endpoint: Optional[str] = None
    headers: Optional[dict] = None
    enabled: Optional[bool] = None


@router.post("/connectors/{vendor}/configure")
async def configure_connector(vendor: str, payload: ConnectorConfig,
                              user: dict = Depends(current_user)):
    ensure_permission(user, "erp.configure")
    if vendor not in SUPPORTED_VENDORS:
        raise HTTPException(404, "Conector nao suportado")
    cfg = {}
    if payload.endpoint:
        cfg["endpoint"] = payload.endpoint
    if payload.headers:
        cfg["headers"] = payload.headers
    await db.connector_configs.update_one(
        {"tenant_id": user["tenant_id"], "vendor": vendor},
        {"$set": {
            "tenant_id": user["tenant_id"],
            "vendor": vendor,
            "config": cfg,
            "enabled": payload.enabled is not False,
            "updated_at": utcnow(),
        }},
        upsert=True,
    )
    active = await erp_worker.connectors_for_tenant(user["tenant_id"])
    return {
        "vendor": vendor,
        "config": cfg,
        "enabled": vendor in active,
        "endpoint": active[vendor].endpoint if vendor in active else None,
    }


class TestEvent(BaseModel):
    topic: str = "clients.create"
    payload: dict = Field(default_factory=dict)


@router.post("/connectors/{vendor}/test")
async def test_connector(vendor: str, evt: TestEvent, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.test_connector")
    active = await erp_worker.connectors_for_tenant(user["tenant_id"])
    if vendor not in active:
        raise HTTPException(404, "Conector nao habilitado")
    if not breaker.can_call(vendor):
        return {
            "vendor": vendor,
            "result": {
                "ok": False,
                "status_code": 0,
                "skipped": True,
                "response": "circuit_open: vendor temporarily skipped",
                "latency_ms": 0,
                "endpoint": active[vendor].endpoint,
                "payload_summary": {"topic": evt.topic},
            },
        }
    payload = dict(evt.payload or {})
    after = dict(payload.get("after") or {})
    after.setdefault("tenant_id", user["tenant_id"])
    payload["after"] = after
    res = await active[vendor].deliver({
        "topic": evt.topic,
        "payload": payload,
        "tenant_id": user["tenant_id"],
    })
    if res["ok"]:
        breaker.record_success(vendor)
    else:
        breaker.record_failure(vendor)
    return {"vendor": vendor, "result": res}


@router.get("/outbox")
async def outbox(status: Optional[str] = None,
                 limit: int = Query(50, le=200),
                 user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    q: dict = {"tenant_id": user["tenant_id"]}
    if status:
        q["status"] = status
    cursor = db.outbox_events.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [doc async for doc in cursor]
    counts = {}
    async for d in db.outbox_events.aggregate([
        {"$match": {"tenant_id": user["tenant_id"]}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]):
        counts[d["_id"]] = d["count"]
    return {"items": items, "counts": counts}


@router.post("/outbox/{event_id}/retry")
async def retry_outbox(event_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.retry")
    res = await db.outbox_events.update_one(
        {"id": event_id, "tenant_id": user["tenant_id"], "status": {"$in": ["failed", "delivered"]}},
        {"$set": {"status": "pending", "attempts": 0,
                  "next_attempt_at": utcnow(), "updated_at": utcnow()}},
    )
    if not res.modified_count:
        raise HTTPException(404, "Evento nao encontrado ou nao retentavel")
    return {"retried": True, "id": event_id}


@router.get("/deliveries")
async def deliveries(vendor: Optional[str] = None,
                     limit: int = Query(50, le=200),
                     user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    q: dict = {"tenant_id": user["tenant_id"]}
    if vendor:
        q["vendor"] = vendor
    cursor = db.connector_deliveries.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return {"items": [doc async for doc in cursor]}


@router.get("/circuit-breakers")
async def circuit_breakers(user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    info = breaker.info()
    seen = {i["vendor"] for i in info}
    active = await erp_worker.connectors_for_tenant(user["tenant_id"])
    for vendor in active:
        if vendor not in seen:
            info.append({
                "vendor": vendor, "state": "closed",
                "failures_in_window": 0, "threshold": 5,
                "window_sec": 60, "cooldown_sec": 30, "opened_at": None,
            })
    return {"breakers": info}


@router.post("/circuit-breakers/{vendor}/reset")
async def reset_breaker(vendor: str, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.configure")
    breaker.reset(vendor)
    return {"vendor": vendor, "state": "closed"}


@router.get("/dlq")
async def dlq_list(limit: int = Query(50, le=200), user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    cursor = db.dead_letter_queue.find(
        {"tenant_id": user["tenant_id"]}, {"_id": 0}
    ).sort("moved_at", -1).limit(limit)
    items = [doc async for doc in cursor]
    total = await db.dead_letter_queue.count_documents({"tenant_id": user["tenant_id"]})
    return {"items": items, "total": total}


@router.post("/dlq/{dlq_id}/replay")
async def dlq_replay(dlq_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.retry")
    doc = await db.dead_letter_queue.find_one(
        {"id": dlq_id, "tenant_id": user["tenant_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "DLQ entry nao encontrada")
    new = {
        "id": new_uuid(),
        "tenant_id": doc.get("tenant_id"),
        "topic": doc.get("topic"),
        "payload": doc.get("payload"),
        "status": "pending",
        "attempts": 0,
        "last_error": None,
        "next_attempt_at": utcnow(),
        "deliveries": [],
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "replayed_from_dlq": dlq_id,
    }
    await db.outbox_events.insert_one(new)
    await db.dead_letter_queue.update_one(
        {"id": dlq_id, "tenant_id": user["tenant_id"]},
        {"$set": {"replayed_at": utcnow(), "replayed_to": new["id"]}},
    )
    return {"replayed": True, "outbox_id": new["id"]}


@router.delete("/dlq/{dlq_id}")
async def dlq_purge(dlq_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.configure")
    res = await db.dead_letter_queue.delete_one({"id": dlq_id, "tenant_id": user["tenant_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "DLQ entry nao encontrada")
    return {"purged": True, "id": dlq_id}


@router.post("/webhook/{source}")
async def webhook(source: str, request: Request):
    body = await request.json()
    tenant_id = request.headers.get("x-tenant-id") or body.get("tenant_id")
    evt = {
        "id": new_uuid(),
        "tenant_id": tenant_id,
        "source": source,
        "type": body.get("type", "unknown"),
        "payload": body,
        "received_at": utcnow(),
    }
    await db.integration_events.insert_one(evt)
    event_bus.publish(f"integration.{source}.{evt['type']}", body)
    return {"received": True, "id": evt["id"]}


@router.post("/_simulator/{vendor}")
async def simulator(vendor: str, request: Request):
    body = await request.json()
    sim = {
        "id": new_uuid(),
        "tenant_id": request.headers.get("x-tenant-id"),
        "vendor": vendor,
        "received_at": utcnow(),
        "body": body,
    }
    await db.simulator_log.insert_one(sim)
    return {
        "vendor": vendor,
        "ack": True,
        "received_at": sim["received_at"].isoformat(),
        "vendor_ref": f"{vendor.upper()}-{sim['id'][:8]}",
    }


@router.get("/_simulator/{vendor}/log")
async def simulator_log(vendor: str, limit: int = 50, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    cursor = db.simulator_log.find(
        {"vendor": vendor, "tenant_id": user["tenant_id"]}, {"_id": 0}
    ).sort("received_at", -1).limit(limit)
    return {"items": [doc async for doc in cursor]}


@router.get("/events")
async def events(limit: int = 50, user: dict = Depends(current_user)):
    ensure_permission(user, "erp.view")
    items = list(event_bus.history)[-limit:]
    return {"items": list(reversed(items)), "total": len(event_bus.history)}


@router.get("/integration-events")
async def integration_events(user: dict = Depends(current_user), limit: int = 50):
    ensure_permission(user, "erp.view")
    cursor = db.integration_events.find(
        {"tenant_id": user["tenant_id"]}, {"_id": 0}
    ).sort("received_at", -1).limit(limit)
    return [doc async for doc in cursor]
