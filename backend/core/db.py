"""MongoDB connection + indexes."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    """Create required indexes for performance + uniqueness across tenants."""
    await db.users.create_index("id", unique=True)
    await db.users.create_index([("email", 1), ("tenant_id", 1)], unique=True)
    await db.counters.create_index("name", unique=True)
    await db.tenants.create_index("id", unique=True)
    await db.tenants.create_index("slug", unique=True)
    await db.branches.create_index("id", unique=True)
    await db.branches.create_index([("tenant_id", 1), ("code", 1)], unique=True)
    await db.tenant_memberships.create_index("id", unique=True)
    await db.tenant_memberships.create_index([("tenant_id", 1), ("user_id", 1)], unique=True)
    await db.tenant_memberships.create_index([("tenant_id", 1), ("status", 1)])

    for coll in (
        "clients", "pipeline_stages", "opportunities", "interactions",
        "contracts", "orders", "products", "cargas", "vehicles",
        "tickets", "ai_sessions", "audit_logs", "sync_events",
    ):
        await db[coll].create_index([("tenant_id", 1), ("seq_id", 1)])
        await db[coll].create_index([("tenant_id", 1), ("branch_id", 1)])
        await db[coll].create_index("id", unique=True)
        await db[coll].create_index("deleted_at")
        await db[coll].create_index("updated_at")

    # ERP outbox + deliveries indexes
    await db.outbox_events.create_index("id", unique=True)
    await db.outbox_events.create_index([("status", 1), ("next_attempt_at", 1)])
    await db.outbox_events.create_index("created_at")
    await db.connector_deliveries.create_index([("vendor", 1), ("timestamp", -1)])
    await db.connector_deliveries.create_index("outbox_id")
    try:
        await db.connector_configs.drop_index("vendor_1")
    except Exception:
        pass
    await db.connector_configs.create_index([("tenant_id", 1), ("vendor", 1)], unique=True)
    await db.simulator_log.create_index([("vendor", 1), ("received_at", -1)])
    await db.dead_letter_queue.create_index("id", unique=True)
    await db.dead_letter_queue.create_index("moved_at")
    await db.ai_usage.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.ai_usage.create_index([("tenant_id", 1), ("user_id", 1), ("created_at", -1)])
    await db.ai_usage.create_index([("tenant_id", 1), ("agent", 1), ("created_at", -1)])
    await db.ai_cache.create_index([("tenant_id", 1), ("cache_key", 1)], unique=True)
    await db.ai_cache.create_index("expires_at", expireAfterSeconds=0)
