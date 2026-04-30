"""
Agro CRM - FastAPI Backend (Modular Monolith)
Standalone CRM for agribusiness trading (grains, barter, inputs).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from core.db import db, ensure_indexes
from core.events import event_bus
from core.seed import seed_initial_data
from core.tenancy import ensure_tenant_bootstrap
from modules.integrations.worker import erp_worker

from modules.auth.routes import router as auth_router
from modules.clients.routes import router as clients_router
from modules.pipeline.routes import router as pipeline_router
from modules.contracts.routes import router as contracts_router
from modules.orders.routes import router as orders_router
from modules.products.routes import router as products_router
from modules.logistics.routes import router as logistics_router
from modules.support.routes import router as support_router
from modules.dashboard.routes import router as dashboard_router
from modules.ai_agents.routes import router as ai_router
from modules.sync.routes import router as sync_router
from modules.integrations.routes import router as integrations_router
from modules.audit.routes import router as audit_router
from modules.admin.routes import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await ensure_tenant_bootstrap()
    if os.environ.get("ENABLE_DEMO_SEED", "false").lower() in {"1", "true", "yes", "on"}:
        await seed_initial_data()
        await ensure_tenant_bootstrap()
    event_bus.start()
    erp_worker.start()
    yield
    erp_worker.stop()
    event_bus.stop()


app = FastAPI(
    title="Agro CRM API",
    version="1.0.0",
    description="Standalone CRM for agribusiness — grain trading, barter, producer relationship.",
    lifespan=lifespan,
)

cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes are prefixed with /api (Kubernetes ingress contract)
API_PREFIX = "/api"

app.include_router(auth_router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(clients_router, prefix=f"{API_PREFIX}/clients", tags=["Clients"])
app.include_router(pipeline_router, prefix=f"{API_PREFIX}/pipeline", tags=["Pipeline"])
app.include_router(contracts_router, prefix=f"{API_PREFIX}/contracts", tags=["Contracts"])
app.include_router(orders_router, prefix=f"{API_PREFIX}/orders", tags=["Orders"])
app.include_router(products_router, prefix=f"{API_PREFIX}/products", tags=["Products"])
app.include_router(logistics_router, prefix=f"{API_PREFIX}/logistics", tags=["Logistics"])
app.include_router(support_router, prefix=f"{API_PREFIX}/support", tags=["Support"])
app.include_router(dashboard_router, prefix=f"{API_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(ai_router, prefix=f"{API_PREFIX}/ai", tags=["AI Agents"])
app.include_router(sync_router, prefix=f"{API_PREFIX}/sync", tags=["Mobile Sync"])
app.include_router(integrations_router, prefix=f"{API_PREFIX}/integrations", tags=["Integrations"])
app.include_router(audit_router, prefix=f"{API_PREFIX}/audit", tags=["Audit"])
app.include_router(admin_router, prefix=f"{API_PREFIX}/admin", tags=["Admin"])


@app.get(f"{API_PREFIX}/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok", "db": "ok", "version": "1.0.0"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)}


@app.get(f"{API_PREFIX}/")
async def root():
    return {"name": "Agro CRM API", "version": "1.0.0"}
