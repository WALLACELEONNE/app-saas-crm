"""Seed initial demo data on app startup (idempotent)."""
import os
from core.db import db
from core.auth import hash_password
from core.repo import insert_entity
from core.models import utcnow, new_uuid

TENANT = os.environ.get("DEFAULT_TENANT_ID", "tenant-default")


async def seed_initial_data() -> None:
    # ---- Users ----
    if not await db.users.find_one({"email": "admin@agrocrm.com"}):
        await insert_entity("users", {
            "email": "admin@agrocrm.com",
            "name": "Carlos Andrade",
            "password_hash": hash_password("Admin@123"),
            "role": "admin",
            "tenant_id": TENANT,
        })
    if not await db.users.find_one({"email": "trader@agrocrm.com"}):
        await insert_entity("users", {
            "email": "trader@agrocrm.com",
            "name": "Mariana Souza",
            "password_hash": hash_password("Trader@123"),
            "role": "trader",
            "tenant_id": TENANT,
        })

    # ---- Pipeline stages ----
    if await db.pipeline_stages.count_documents({"tenant_id": TENANT}) == 0:
        for i, (name, color) in enumerate([
            ("Prospecção", "#8BA094"),
            ("Qualificação", "#FACC15"),
            ("Proposta", "#F97316"),
            ("Negociação", "#22C55E"),
            ("Fechamento", "#16A34A"),
        ]):
            await insert_entity("pipeline_stages", {
                "tenant_id": TENANT, "name": name, "order": i, "color": color,
            })

    # ---- Products ----
    if await db.products.count_documents({"tenant_id": TENANT}) == 0:
        products = [
            {"category": "grain", "name": "Soja em Grão", "sku": "SOJ-001", "unit": "ton", "current_price": 142.5, "currency": "BRL"},
            {"category": "grain", "name": "Milho", "sku": "MIL-001", "unit": "ton", "current_price": 64.2, "currency": "BRL"},
            {"category": "grain", "name": "Trigo", "sku": "TRG-001", "unit": "ton", "current_price": 88.0, "currency": "BRL"},
            {"category": "input", "name": "Glifosato 480g/L", "sku": "INS-GLF", "unit": "L", "current_price": 32.9, "currency": "BRL"},
            {"category": "input", "name": "Fertilizante NPK 04-30-10", "sku": "INS-NPK", "unit": "ton", "current_price": 4180.0, "currency": "BRL"},
            {"category": "input", "name": "Sementes Soja Intacta RR2", "sku": "INS-SOJSEM", "unit": "sc", "current_price": 685.0, "currency": "BRL"},
        ]
        for p in products:
            p["tenant_id"] = TENANT
            await insert_entity("products", p)

    # ---- Clients ----
    if await db.clients.count_documents({"tenant_id": TENANT}) == 0:
        clients = [
            {"type": "producer", "name": "Fazenda São Benedito", "doc": "11.222.333/0001-44",
             "region": "MT - Sorriso", "culture": ["soja", "milho"], "potential": "alto",
             "classification": "A", "area_ha": 4500,
             "contacts": [{"name": "João Pereira", "phone": "+55 66 99999-1111", "email": "joao@saobenedito.com"}]},
            {"type": "producer", "name": "Agropecuária Boa Vista", "doc": "22.333.444/0001-55",
             "region": "GO - Rio Verde", "culture": ["soja", "algodão"], "potential": "medio",
             "classification": "B", "area_ha": 1800,
             "contacts": [{"name": "Patrícia Lima", "phone": "+55 64 98888-2222", "email": "patricia@boavista.com"}]},
            {"type": "company", "name": "Cooperativa Coamo Filial Maringá", "doc": "33.444.555/0001-66",
             "region": "PR - Maringá", "culture": ["soja", "trigo", "milho"], "potential": "alto",
             "classification": "A", "area_ha": 0,
             "contacts": [{"name": "Roberto Tanaka", "phone": "+55 44 97777-3333", "email": "tanaka@coamo.com.br"}]},
            {"type": "producer", "name": "Fazenda Três Rios", "doc": "44.555.666/0001-77",
             "region": "BA - Luís Eduardo Magalhães", "culture": ["soja", "milho"], "potential": "alto",
             "classification": "A", "area_ha": 6200,
             "contacts": [{"name": "Eduardo Klein", "phone": "+55 77 96666-4444", "email": "klein@tresrios.com"}]},
            {"type": "producer", "name": "Sítio Boa Esperança", "doc": "55.666.777/0001-88",
             "region": "RS - Passo Fundo", "culture": ["soja", "trigo"], "potential": "baixo",
             "classification": "C", "area_ha": 320,
             "contacts": [{"name": "Vilson Schmitz", "phone": "+55 54 95555-5555", "email": "vilson@boaesperanca.com"}]},
        ]
        for c in clients:
            c["tenant_id"] = TENANT
            await insert_entity("clients", c)

    # ---- Opportunities ----
    if await db.opportunities.count_documents({"tenant_id": TENANT}) == 0:
        stages = [s async for s in db.pipeline_stages.find({"tenant_id": TENANT}, {"_id": 0}).sort("order", 1)]
        clients = [c async for c in db.clients.find({"tenant_id": TENANT}, {"_id": 0})]
        products = [p async for p in db.products.find({"tenant_id": TENANT}, {"_id": 0})]
        if stages and clients and products:
            opps = [
                {"client_id": clients[0]["id"], "client_name": clients[0]["name"],
                 "stage_id": stages[3]["id"], "stage_name": stages[3]["name"],
                 "title": "Venda Soja 5.000 ton — Safra 25/26",
                 "product_id": products[0]["id"], "product_name": products[0]["name"],
                 "volume": 5000, "unit": "ton", "value": 712500, "currency": "BRL",
                 "probability": 70, "expected_close": "2026-03-15"},
                {"client_id": clients[1]["id"], "client_name": clients[1]["name"],
                 "stage_id": stages[1]["id"], "stage_name": stages[1]["name"],
                 "title": "Barter Insumos x Soja — 1.200 ton",
                 "product_id": products[3]["id"], "product_name": products[3]["name"],
                 "volume": 1200, "unit": "ton", "value": 184000, "currency": "BRL",
                 "probability": 40, "expected_close": "2026-04-20"},
                {"client_id": clients[2]["id"], "client_name": clients[2]["name"],
                 "stage_id": stages[2]["id"], "stage_name": stages[2]["name"],
                 "title": "Compra Trigo 8.000 ton",
                 "product_id": products[2]["id"], "product_name": products[2]["name"],
                 "volume": 8000, "unit": "ton", "value": 704000, "currency": "BRL",
                 "probability": 55, "expected_close": "2026-02-28"},
                {"client_id": clients[3]["id"], "client_name": clients[3]["name"],
                 "stage_id": stages[0]["id"], "stage_name": stages[0]["name"],
                 "title": "Aproximação Safra Oeste BA",
                 "product_id": products[0]["id"], "product_name": products[0]["name"],
                 "volume": 12000, "unit": "ton", "value": 1710000, "currency": "BRL",
                 "probability": 20, "expected_close": "2026-05-30"},
                {"client_id": clients[0]["id"], "client_name": clients[0]["name"],
                 "stage_id": stages[4]["id"], "stage_name": stages[4]["name"],
                 "title": "Fertilizante NPK — 600 ton",
                 "product_id": products[4]["id"], "product_name": products[4]["name"],
                 "volume": 600, "unit": "ton", "value": 2508000, "currency": "BRL",
                 "probability": 90, "expected_close": "2026-01-30"},
            ]
            for o in opps:
                o["tenant_id"] = TENANT
                o["history"] = []
                await insert_entity("opportunities", o)

    # ---- Contracts ----
    if await db.contracts.count_documents({"tenant_id": TENANT}) == 0:
        clients = [c async for c in db.clients.find({"tenant_id": TENANT}, {"_id": 0})]
        products = [p async for p in db.products.find({"tenant_id": TENANT}, {"_id": 0})]
        if clients and products:
            for i, ctype in enumerate(["sell", "buy", "barter", "sell"]):
                cli = clients[i % len(clients)]
                prod = products[i % len(products)]
                await insert_entity("contracts", {
                    "tenant_id": TENANT,
                    "type": ctype,
                    "client_id": cli["id"], "client_name": cli["name"],
                    "product_id": prod["id"], "product_name": prod["name"],
                    "volume": [3000, 1500, 900, 4200][i],
                    "unit": "ton",
                    "price": [142.5, 64.2, 0, 142.0][i],
                    "currency": "BRL",
                    "signed_at": "2026-01-1{}".format(i),
                    "delivery_window": "2026-Q2",
                    "status": ["active", "active", "draft", "active"][i],
                })

    # ---- Orders ----
    if await db.orders.count_documents({"tenant_id": TENANT}) == 0:
        contracts = [c async for c in db.contracts.find({"tenant_id": TENANT}, {"_id": 0})]
        for i, ct in enumerate(contracts[:3]):
            await insert_entity("orders", {
                "tenant_id": TENANT,
                "type": "sale" if ct["type"] == "sell" else "purchase",
                "contract_id": ct["id"],
                "client_id": ct["client_id"], "client_name": ct["client_name"],
                "items": [{"product_id": ct["product_id"], "product_name": ct["product_name"],
                          "volume": ct["volume"], "unit": ct["unit"], "price": ct["price"]}],
                "total": ct["volume"] * ct["price"],
                "currency": ct["currency"],
                "status": ["confirmed", "in_transit", "delivered"][i],
                "logistic_status": ["queue", "loading", "delivered"][i],
            })

    # ---- Vehicles + Cargas ----
    if await db.vehicles.count_documents({"tenant_id": TENANT}) == 0:
        for plate, capacity in [("MTA-2A45", 30), ("MTB-9F11", 38), ("PRC-4G88", 28)]:
            await insert_entity("vehicles", {
                "tenant_id": TENANT, "plate": plate, "type": "bitrem",
                "capacity_ton": capacity, "status": "available",
            })

    if await db.cargas.count_documents({"tenant_id": TENANT}) == 0:
        orders = [o async for o in db.orders.find({"tenant_id": TENANT}, {"_id": 0})]
        vehicles = [v async for v in db.vehicles.find({"tenant_id": TENANT}, {"_id": 0})]
        if orders and vehicles:
            for i, o in enumerate(orders):
                v = vehicles[i % len(vehicles)]
                await insert_entity("cargas", {
                    "tenant_id": TENANT,
                    "order_id": o["id"],
                    "vehicle_plate": v["plate"],
                    "driver": ["Roberto Silva", "Carlos Mendes", "Pedro Souza"][i % 3],
                    "origin": ["Sorriso/MT", "Rio Verde/GO", "Maringá/PR"][i % 3],
                    "destination": "Porto de Paranaguá/PR",
                    "status": ["queue", "in_transit", "delivered"][i % 3],
                })

    # ---- Tickets ----
    if await db.tickets.count_documents({"tenant_id": TENANT}) == 0:
        clients = [c async for c in db.clients.find({"tenant_id": TENANT}, {"_id": 0})]
        for i, status in enumerate(["open", "in_progress", "closed"]):
            cli = clients[i % len(clients)]
            await insert_entity("tickets", {
                "tenant_id": TENANT,
                "client_id": cli["id"], "client_name": cli["name"],
                "subject": ["Atraso na entrega", "Discrepância de classificação", "Solicitação de 2ª via NF"][i],
                "description": "Cliente reportou via canal comercial.",
                "priority": ["high", "medium", "low"][i],
                "sla_hours": [4, 24, 72][i],
                "status": status,
                "comments": [],
            })
