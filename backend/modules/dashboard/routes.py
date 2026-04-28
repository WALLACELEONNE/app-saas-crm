"""Dashboard — Aggregated KPIs for executive view."""
from collections import defaultdict
from fastapi import APIRouter, Depends
from core.auth import current_user
from core.db import db

router = APIRouter()


@router.get("/kpis")
async def kpis(user: dict = Depends(current_user)):
    tid = user["tenant_id"]
    base = {"tenant_id": tid, "deleted_at": None}

    active_contracts = await db.contracts.count_documents({**base, "status": "active"})
    total_clients = await db.clients.count_documents(base)
    open_orders = await db.orders.count_documents(
        {**base, "status": {"$in": ["pending", "confirmed", "in_transit"]}}
    )
    open_tickets = await db.tickets.count_documents({**base, "status": {"$ne": "closed"}})

    # Volume of grains in active contracts
    cursor = db.contracts.aggregate([
        {"$match": {**base, "status": "active"}},
        {"$group": {"_id": None, "volume": {"$sum": "$volume"},
                    "value": {"$sum": {"$multiply": ["$volume", "$price"]}}}},
    ])
    grain_stats = await cursor.to_list(length=1)
    grain_volume = grain_stats[0]["volume"] if grain_stats else 0
    grain_value = grain_stats[0]["value"] if grain_stats else 0

    # Pipeline value by stage
    stages = [s async for s in db.pipeline_stages.find(base, {"_id": 0}).sort("order", 1)]
    opps = [o async for o in db.opportunities.find(base, {"_id": 0})]
    by_stage = defaultdict(lambda: {"count": 0, "value": 0})
    for o in opps:
        sid = o.get("stage_id")
        by_stage[sid]["count"] += 1
        by_stage[sid]["value"] += o.get("value", 0)
    pipeline_by_stage = [
        {"stage": s["name"], "color": s.get("color"),
         "count": by_stage[s["id"]]["count"], "value": by_stage[s["id"]]["value"]}
        for s in stages
    ]

    # Revenue by region (from active contracts)
    revenue_by_region: dict[str, float] = defaultdict(float)
    contracts = [c async for c in db.contracts.find({**base, "status": "active"}, {"_id": 0})]
    for c in contracts:
        cli = await db.clients.find_one({"id": c.get("client_id")}, {"_id": 0, "region": 1})
        region = (cli or {}).get("region", "Sem região")
        revenue_by_region[region] += c.get("volume", 0) * c.get("price", 0)

    # Logistic status
    logistic = defaultdict(int)
    async for c in db.cargas.find(base, {"_id": 0, "status": 1}):
        logistic[c["status"]] += 1

    # Recent activity (audit logs)
    activity = [
        {**a, "_id": None}
        async for a in db.audit_logs.find({"tenant_id": tid}, {"_id": 0}).sort("timestamp", -1).limit(8)
    ]
    for a in activity:
        a.pop("_id", None)
        if isinstance(a.get("timestamp"), object) and not isinstance(a.get("timestamp"), str):
            a["timestamp"] = a["timestamp"].isoformat() if hasattr(a["timestamp"], "isoformat") else str(a["timestamp"])

    return {
        "summary": {
            "active_contracts": active_contracts,
            "total_clients": total_clients,
            "open_orders": open_orders,
            "open_tickets": open_tickets,
            "grain_volume_ton": grain_volume,
            "grain_volume_value_brl": grain_value,
            "pipeline_total_value": sum(s["value"] for s in pipeline_by_stage),
            "pipeline_total_count": sum(s["count"] for s in pipeline_by_stage),
        },
        "pipeline_by_stage": pipeline_by_stage,
        "revenue_by_region": [{"region": k, "value": v}
                              for k, v in sorted(revenue_by_region.items(),
                                                 key=lambda kv: -kv[1])],
        "logistic_status": [{"status": k, "count": v} for k, v in logistic.items()],
        "recent_activity": activity,
    }
