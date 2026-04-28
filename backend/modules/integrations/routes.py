"""
ERP Integrations Hub — connector registry, worker control, durable outbox,
delivery tracking, and a built-in simulator endpoint that records inbound
calls (used as default destination for connectors when no real ERP URL
is configured).
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from pydantic import BaseModel, Field
from core.auth import current_user
from core.events import event_bus
from core.db import db
from core.models import utcnow, new_uuid
from .worker import erp_worker
from .connectors import build_connector
from .circuit_breaker import breaker

router = APIRouter()


@router.get("/connectors")
async def connectors(user: dict = Depends(current_user)):
    """List available + currently enabled connectors with live config."""
    out = []
    for vendor, c in erp_worker.connectors.items():
        out.append({
            "vendor": vendor, "name": c.name,
            "topics": list(c.topics),
            "endpoint": c.endpoint,
            "enabled": vendor in erp_worker.enabled_vendors,
            "transport": ["REST", "Webhook"],
        })
    # Also expose vendors the system knows about even if not enabled:
    for vendor, name in [("sap", "SAP S/4HANA"), ("oracle", "Oracle EBS"),
                         ("siagri", "Siagri Agribusiness")]:
        if vendor not in erp_worker.connectors:
            out.append({"vendor": vendor, "name": name, "topics": [], "endpoint": None,
                        "enabled": False, "transport": ["REST"]})
    return {"connectors": out}


class ConnectorConfig(BaseModel):
    endpoint: Optional[str] = None
    headers: Optional[dict] = None
    enabled: Optional[bool] = None


@router.post("/connectors/{vendor}/configure")
async def configure_connector(vendor: str, payload: ConnectorConfig,
                              user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admin pode configurar conectores")
    if vendor not in {"sap", "oracle", "siagri"}:
        raise HTTPException(404, "Conector não suportado")
    cfg = {}
    if payload.endpoint: cfg["endpoint"] = payload.endpoint
    if payload.headers:  cfg["headers"] = payload.headers
    if payload.enabled is False:
        erp_worker.enabled_vendors.discard(vendor)
        erp_worker.connectors.pop(vendor, None)
    else:
        erp_worker.enabled_vendors.add(vendor)
        erp_worker.connectors[vendor] = build_connector(vendor, cfg)
    # Persist config
    await db.connector_configs.update_one(
        {"vendor": vendor},
        {"$set": {"vendor": vendor, "config": cfg,
                  "enabled": payload.enabled is not False, "updated_at": utcnow()}},
        upsert=True,
    )
    return {"vendor": vendor, "config": cfg,
            "enabled": payload.enabled is not False,
            "endpoint": erp_worker.connectors.get(vendor).endpoint if vendor in erp_worker.connectors else None}


class TestEvent(BaseModel):
    topic: str = "clients.create"
    payload: dict = Field(default_factory=dict)


@router.post("/connectors/{vendor}/test")
async def test_connector(vendor: str, evt: TestEvent, user: dict = Depends(current_user)):
    """Synchronous one-shot dispatch to a connector — bypass the outbox
    but still respect/feed the per-vendor circuit breaker."""
    if vendor not in erp_worker.connectors:
        raise HTTPException(404, "Conector não habilitado")
    if not breaker.can_call(vendor):
        return {"vendor": vendor,
                "result": {"ok": False, "status_code": 0, "skipped": True,
                            "response": "circuit_open: vendor temporarily skipped",
                            "latency_ms": 0,
                            "endpoint": erp_worker.connectors[vendor].endpoint,
                            "payload_summary": {"topic": evt.topic}}}
    connector = erp_worker.connectors[vendor]
    res = await connector.deliver({"topic": evt.topic, "payload": evt.payload})
    if res["ok"]:
        breaker.record_success(vendor)
    else:
        breaker.record_failure(vendor)
    return {"vendor": vendor, "result": res}


@router.get("/outbox")
async def outbox(status: Optional[str] = None,
                 limit: int = Query(50, le=200),
                 user: dict = Depends(current_user)):
    q: dict = {}
    if status:
        q["status"] = status
    cursor = db.outbox_events.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [doc async for doc in cursor]
    counts = {}
    async for d in db.outbox_events.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]):
        counts[d["_id"]] = d["count"]
    return {"items": items, "counts": counts}


@router.post("/outbox/{event_id}/retry")
async def retry_outbox(event_id: str, user: dict = Depends(current_user)):
    res = await db.outbox_events.update_one(
        {"id": event_id, "status": {"$in": ["failed", "delivered"]}},
        {"$set": {"status": "pending", "attempts": 0,
                  "next_attempt_at": utcnow(), "updated_at": utcnow()}},
    )
    if not res.modified_count:
        raise HTTPException(404, "Evento não encontrado ou não retentável")
    return {"retried": True, "id": event_id}


@router.get("/deliveries")
async def deliveries(vendor: Optional[str] = None,
                     limit: int = Query(50, le=200),
                     user: dict = Depends(current_user)):
    q: dict = {}
    if vendor:
        q["vendor"] = vendor
    cursor = db.connector_deliveries.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return {"items": [doc async for doc in cursor]}


# ---- Circuit Breakers ----
@router.get("/circuit-breakers")
async def circuit_breakers(user: dict = Depends(current_user)):
    info = breaker.info()
    # Always include all enabled vendors, even if no failures yet
    seen = {i["vendor"] for i in info}
    for vendor in erp_worker.connectors:
        if vendor not in seen:
            info.append({
                "vendor": vendor, "state": "closed",
                "failures_in_window": 0, "threshold": 5,
                "window_sec": 60, "cooldown_sec": 30, "opened_at": None,
            })
    return {"breakers": info}


@router.post("/circuit-breakers/{vendor}/reset")
async def reset_breaker(vendor: str, user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admin pode resetar breakers")
    breaker.reset(vendor)
    return {"vendor": vendor, "state": "closed"}


# ---- Dead-letter queue ----
@router.get("/dlq")
async def dlq_list(limit: int = Query(50, le=200), user: dict = Depends(current_user)):
    cursor = db.dead_letter_queue.find({}, {"_id": 0}).sort("moved_at", -1).limit(limit)
    items = [doc async for doc in cursor]
    total = await db.dead_letter_queue.count_documents({})
    return {"items": items, "total": total}


@router.post("/dlq/{dlq_id}/replay")
async def dlq_replay(dlq_id: str, user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admin pode reprocessar DLQ")
    doc = await db.dead_letter_queue.find_one({"id": dlq_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "DLQ entry não encontrada")
    # Re-create the outbox event with reset attempts so the worker picks it up.
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
    await db.dead_letter_queue.update_one({"id": dlq_id},
                                          {"$set": {"replayed_at": utcnow(), "replayed_to": new["id"]}})
    return {"replayed": True, "outbox_id": new["id"]}


@router.delete("/dlq/{dlq_id}")
async def dlq_purge(dlq_id: str, user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Apenas admin pode purgar DLQ")
    res = await db.dead_letter_queue.delete_one({"id": dlq_id})
    if not res.deleted_count:
        raise HTTPException(404, "DLQ entry não encontrada")
    return {"purged": True, "id": dlq_id}


# ---- Inbound webhook (real ERPs) ----
@router.post("/webhook/{source}")
async def webhook(source: str, request: Request):
    body = await request.json()
    evt = {
        "id": new_uuid(),
        "source": source,
        "type": body.get("type", "unknown"),
        "payload": body,
        "received_at": utcnow(),
    }
    await db.integration_events.insert_one(evt)
    event_bus.publish(f"integration.{source}.{evt['type']}", body)
    return {"received": True, "id": evt["id"]}


# ---- Built-in ERP simulator (default destination of connectors) ----
@router.post("/_simulator/{vendor}")
async def simulator(vendor: str, request: Request):
    """Records a connector call locally so we can verify outbound deliveries
    end-to-end without a real ERP. Returns an acknowledgment that mimics a
    typical 200 OK from the vendor."""
    body = await request.json()
    sim = {
        "id": new_uuid(),
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
    cursor = db.simulator_log.find({"vendor": vendor}, {"_id": 0}).sort("received_at", -1).limit(limit)
    return {"items": [doc async for doc in cursor]}


# ---- Domain event observability ----
@router.get("/events")
async def events(limit: int = 50, user: dict = Depends(current_user)):
    items = list(event_bus.history)[-limit:]
    return {"items": list(reversed(items)), "total": len(event_bus.history)}


@router.get("/integration-events")
async def integration_events(user: dict = Depends(current_user), limit: int = 50):
    cursor = db.integration_events.find({}, {"_id": 0}).sort("received_at", -1).limit(limit)
    return [doc async for doc in cursor]
