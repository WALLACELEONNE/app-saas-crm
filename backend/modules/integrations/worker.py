"""
ERP Worker — durable outbox + dispatcher.

Flow:
1) Domain event published to in-memory EventBus (existing).
2) Worker subscribes to "*", persists every event into MongoDB outbox_events.
3) Background loop polls outbox for "pending" deliveries and dispatches them
   to all matching connectors (SAP, Oracle, Siagri).
4) Each delivery attempt is logged in connector_deliveries with retries
   (exponential backoff). Status: pending → in_progress → delivered | failed.
"""
from __future__ import annotations
import os
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.db import db
from core.events import event_bus
from core.models import new_uuid, utcnow
from .connectors import build_connector, ConnectorBase

log = logging.getLogger("erp_worker")

# Tunables ---------------------------------------------------------------
POLL_INTERVAL_SEC = float(os.environ.get("ERP_WORKER_POLL", "2.0"))
BATCH_SIZE = int(os.environ.get("ERP_WORKER_BATCH", "10"))
MAX_RETRIES = int(os.environ.get("ERP_WORKER_MAX_RETRIES", "5"))


class ErpWorker:
    """Singleton background worker. Started by FastAPI lifespan."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self.connectors: dict[str, ConnectorBase] = {}
        self.enabled_vendors: set[str] = {"sap", "oracle", "siagri"}

    # ---------- lifecycle ----------
    def start(self) -> None:
        if self._task and not self._task.done():
            return
        # Subscribe to ALL events to persist them in the outbox.
        event_bus.subscribe("*", self._on_event)
        # Build default connectors (using simulator endpoints unless configured).
        for v in self.enabled_vendors:
            self.connectors[v] = build_connector(v)
        self._stop.clear()
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run(), name="erp-worker")
            log.info("ERP worker started (connectors=%s)", list(self.connectors.keys()))
        except RuntimeError:
            log.warning("No running loop — worker not started")

    def stop(self) -> None:
        self._stop.set()

    # ---------- event ingestion (outbox write) ----------
    async def _on_event(self, evt: dict) -> None:
        """Persist a copy of every domain event into the outbox.
        Called by the EventBus for every published topic."""
        topic: str = evt.get("topic", "")
        # Avoid recursion: skip integration.* events (they come from inbound webhooks)
        if topic.startswith("integration."):
            return
        # Skip audit_logs internal events if any
        if topic.startswith("audit"):
            return
        try:
            doc = {
                "id": new_uuid(),
                "tenant_id": (evt.get("payload") or {}).get("after", {}).get("tenant_id", "tenant-default"),
                "topic": topic,
                "payload": evt.get("payload") or {},
                "status": "pending",
                "attempts": 0,
                "last_error": None,
                "next_attempt_at": utcnow(),
                "deliveries": [],   # per-vendor delivery results
                "created_at": utcnow(),
                "updated_at": utcnow(),
            }
            await db.outbox_events.insert_one(doc)
        except Exception as e:
            log.error("outbox write failed: %s", e)

    # ---------- main loop ----------
    async def _run(self) -> None:
        await asyncio.sleep(0.5)  # let lifespan finish
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as e:
                log.exception("worker tick error: %s", e)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=POLL_INTERVAL_SEC)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        """Pick a batch of pending events whose next_attempt_at is due, dispatch them."""
        now = utcnow()
        cursor = db.outbox_events.find(
            {"status": "pending", "next_attempt_at": {"$lte": now}},
            {"_id": 0},
        ).sort("created_at", 1).limit(BATCH_SIZE)
        items = [doc async for doc in cursor]
        for item in items:
            await self._dispatch(item)

    async def _dispatch(self, item: dict) -> None:
        oid = item["id"]
        await db.outbox_events.update_one({"id": oid}, {"$set": {"status": "in_progress",
                                                                  "updated_at": utcnow()}})
        deliveries = []
        all_ok = True
        topic = item.get("topic", "")
        for vendor, connector in self.connectors.items():
            if not connector.matches(topic):
                continue
            # Circuit-breaker gate: if OPEN, skip without HTTP attempt.
            if not breaker.can_call(vendor):
                entry = {
                    "id": new_uuid(),
                    "outbox_id": oid,
                    "tenant_id": item.get("tenant_id"),
                    "topic": topic,
                    "vendor": vendor,
                    "ok": False,
                    "status_code": 0,
                    "response": "circuit_open: vendor temporarily skipped",
                    "latency_ms": 0,
                    "endpoint": connector.endpoint,
                    "attempt": item.get("attempts", 0) + 1,
                    "skipped": True,
                    "timestamp": utcnow(),
                }
                await db.connector_deliveries.insert_one(entry)
                deliveries.append({"vendor": vendor, "ok": False, "status_code": 0,
                                   "skipped": True, "reason": "circuit_open"})
                all_ok = False
                continue

            res = await connector.deliver({"topic": topic, "payload": item.get("payload")})
            entry = {
                "id": new_uuid(),
                "outbox_id": oid,
                "tenant_id": item.get("tenant_id"),
                "topic": topic,
                "vendor": vendor,
                "ok": res["ok"],
                "status_code": res["status_code"],
                "response": res["response"],
                "latency_ms": res["latency_ms"],
                "endpoint": res["endpoint"],
                "attempt": item.get("attempts", 0) + 1,
                "timestamp": utcnow(),
            }
            await db.connector_deliveries.insert_one(entry)
            deliveries.append({"vendor": vendor, "ok": res["ok"], "status_code": res["status_code"]})
            if res["ok"]:
                breaker.record_success(vendor)
            else:
                breaker.record_failure(vendor)
                all_ok = False

        attempts = item.get("attempts", 0) + 1
        if all_ok or not deliveries:
            await db.outbox_events.update_one({"id": oid}, {"$set": {
                "status": "delivered" if deliveries else "skipped",
                "attempts": attempts,
                "deliveries": deliveries,
                "last_error": None,
                "updated_at": utcnow(),
                "delivered_at": utcnow(),
            }})
        else:
            if attempts >= MAX_RETRIES:
                # Move to dead-letter queue
                dlq_doc = {
                    "id": new_uuid(),
                    "outbox_id": oid,
                    "tenant_id": item.get("tenant_id"),
                    "topic": topic,
                    "payload": item.get("payload"),
                    "deliveries": deliveries,
                    "attempts": attempts,
                    "reason": "max_retries_exceeded",
                    "moved_at": utcnow(),
                }
                await db.dead_letter_queue.insert_one(dlq_doc)
                await db.outbox_events.update_one({"id": oid}, {"$set": {
                    "status": "dlq",
                    "attempts": attempts,
                    "deliveries": deliveries,
                    "last_error": "max retries reached — moved to DLQ",
                    "updated_at": utcnow(),
                }})
            else:
                # exponential backoff: 5s, 15s, 45s, 2min, 6min
                delay = 5 * (3 ** (attempts - 1))
                await db.outbox_events.update_one({"id": oid}, {"$set": {
                    "status": "pending",
                    "attempts": attempts,
                    "deliveries": deliveries,
                    "next_attempt_at": utcnow() + timedelta(seconds=delay),
                    "last_error": "partial failure",
                    "updated_at": utcnow(),
                }})


erp_worker = ErpWorker()
