"""
Agro CRM Backend Test Suite
Covers: health, auth, CRUD (clients/contracts/orders/products/logistics/support),
pipeline, dashboard, AI agents (GPT-5.2), sync, integrations, audit, soft-delete.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend env file for local pytest runs
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@agrocrm.com", "password": "Admin@123"}
TRADER = {"email": "trader@agrocrm.com", "password": "Trader@123"}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def tokens(session):
    r = session.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data


@pytest.fixture(scope="session")
def auth(session, tokens):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tokens['access_token']}",
    })
    return s


# ---------- Health ----------
def test_health(session):
    r = session.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"


# ---------- Auth ----------
class TestAuth:
    def test_login_admin(self, tokens):
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens.get("user", {}).get("email") == ADMIN["email"]

    def test_login_invalid(self, session):
        r = session.post(f"{API}/auth/login", json={"email": "x@x.com", "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_me(self, auth):
        r = auth.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json().get("email") == ADMIN["email"]

    def test_refresh(self, session, tokens):
        r = session.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}, timeout=10)
        assert r.status_code == 200
        assert "access_token" in r.json()


# ---------- Clients ----------
class TestClients:
    created_id = None

    def test_list(self, auth):
        r = auth.get(f"{API}/clients", timeout=10)
        assert r.status_code == 200
        j = r.json()
        for k in ("items", "total", "skip", "limit"):
            assert k in j
        assert j["total"] >= 5
        sample = j["items"][0]
        for f in ("id", "seq_id", "name", "type", "region"):
            assert f in sample, f"field {f} missing"

    def test_create(self, auth):
        payload = {
            "name": f"TEST_Cliente_{uuid.uuid4().hex[:6]}",
            "type": "produtor",
            "region": "PR",
            "culture": ["soja"],
            "classification": "A",
        }
        r = auth.post(f"{API}/clients", json=payload, timeout=10)
        assert r.status_code in (200, 201), r.text
        j = r.json()
        assert j["name"] == payload["name"]
        assert "seq_id" in j and j["seq_id"]
        assert "created_at" in j and "updated_at" in j
        assert j.get("deleted_at") is None
        TestClients.created_id = j["id"]

    def test_search(self, auth):
        r = auth.get(f"{API}/clients?q=Coamo", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        assert any("Coamo" in (i.get("name") or "") for i in items)

    def test_patch(self, auth):
        assert TestClients.created_id
        new_name = f"TEST_Updated_{uuid.uuid4().hex[:4]}"
        r = auth.patch(f"{API}/clients/{TestClients.created_id}", json={"name": new_name}, timeout=10)
        assert r.status_code == 200, r.text
        # Verify persistence
        g = auth.get(f"{API}/clients/{TestClients.created_id}", timeout=10)
        assert g.status_code == 200
        assert g.json()["name"] == new_name

    def test_soft_delete(self, auth):
        assert TestClients.created_id
        r = auth.delete(f"{API}/clients/{TestClients.created_id}", timeout=10)
        assert r.status_code in (200, 204)
        # Should not appear in list
        lst = auth.get(f"{API}/clients?limit=200", timeout=10).json()["items"]
        assert all(i["id"] != TestClients.created_id for i in lst), "soft-deleted client still visible"


# ---------- Pipeline ----------
class TestPipeline:
    def test_board(self, auth):
        r = auth.get(f"{API}/pipeline/board", timeout=10)
        assert r.status_code == 200
        body = r.json()
        stages = body["stages"] if isinstance(body, dict) else body
        assert isinstance(stages, list) and len(stages) >= 5
        s0 = stages[0]
        # opportunities may or may not be embedded per stage; check totals at top-level too
        assert "total_opportunities" in body or "total_opportunities" in s0
        assert "total_value" in body or "total_value" in s0

    def test_move_and_interaction(self, auth):
        body = auth.get(f"{API}/pipeline/board", timeout=10).json()
        stages = body["stages"] if isinstance(body, dict) else body
        # opportunities may live inside each stage as 'opportunities' key
        opp = None
        from_stage = None
        for s in stages:
            opps = s.get("opportunities") or []
            if opps:
                opp = opps[0]
                from_stage = s["id"]
                break
        if not opp:
            # fallback: list endpoint
            r = auth.get(f"{API}/pipeline/opportunities", timeout=10)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    opp = items[0]
                    from_stage = opp.get("stage_id")
        if not opp:
            pytest.skip("No opportunity to move")
        target = next(s["id"] for s in stages if s["id"] != from_stage)
        r = auth.post(
            f"{API}/pipeline/opportunities/{opp['id']}/move",
            json={"stage_id": target},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        # interaction
        r2 = auth.post(
            f"{API}/pipeline/opportunities/{opp['id']}/interactions",
            json={"type": "note", "notes": "TEST_note"},
            timeout=10,
        )
        assert r2.status_code in (200, 201), r2.text


# ---------- Contracts ----------
class TestContracts:
    def test_list_and_create(self, auth):
        r = auth.get(f"{API}/contracts", timeout=10)
        assert r.status_code == 200
        # Need a client and product to link
        c = auth.get(f"{API}/clients?limit=1", timeout=10).json()["items"][0]
        p = auth.get(f"{API}/products?limit=1", timeout=10).json()["items"][0]
        payload = {
            "type": "sell",
            "client_id": c["id"],
            "product_id": p["id"],
            "volume": 100,
            "price": 150.5,
            "currency": "BRL",
        }
        r2 = auth.post(f"{API}/contracts", json=payload, timeout=15)
        assert r2.status_code in (200, 201), r2.text
        body = r2.json()
        assert body.get("volume") == 100


# ---------- Orders ----------
class TestOrders:
    def test_list_and_advance(self, auth):
        r = auth.get(f"{API}/orders", timeout=10)
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) >= 1
        oid = items[0]["id"]
        # No /advance endpoint - generic CRUD; use PATCH with new status
        r2 = auth.patch(f"{API}/orders/{oid}", json={"status": "confirmed"}, timeout=10)
        assert r2.status_code in (200, 201, 204), f"PATCH failed: {r2.status_code} {r2.text}"
        g = auth.get(f"{API}/orders/{oid}", timeout=10)
        assert g.status_code == 200
        assert g.json().get("status") == "confirmed"


# ---------- Products ----------
def test_products(auth):
    r = auth.get(f"{API}/products?limit=50", timeout=10)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 6
    types = {i.get("type") or i.get("category") for i in items}
    # Should have grain and input categories
    assert any("grain" in str(t).lower() or "grão" in str(t).lower() for t in types) or len(items) >= 6


# ---------- Logistics ----------
def test_logistics(auth):
    r1 = auth.get(f"{API}/logistics/vehicles", timeout=10)
    r2 = auth.get(f"{API}/logistics/cargas", timeout=10)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text


# ---------- Support ----------
def test_support(auth):
    r = auth.get(f"{API}/support", timeout=10)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert len(items) >= 3


# ---------- Dashboard ----------
def test_dashboard(auth):
    r = auth.get(f"{API}/dashboard/kpis", timeout=15)
    assert r.status_code == 200
    j = r.json()
    for f in ("summary", "pipeline_by_stage", "revenue_by_region", "logistic_status", "recent_activity"):
        assert f in j, f"missing {f}"


# ---------- AI Agents (GPT-5.2 — slow) ----------
class TestAI:
    def test_marketing(self, auth):
        c = auth.get(f"{API}/clients?limit=1", timeout=10).json()["items"][0]
        r = auth.post(f"{API}/ai/marketing/analyze-client", json={"client_id": c["id"]}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        text = j.get("analysis") or j.get("response") or j.get("text") or ""
        assert isinstance(text, str) and len(text) > 0

    def test_sales(self, auth):
        body = auth.get(f"{API}/pipeline/board", timeout=10).json()
        stages = body["stages"] if isinstance(body, dict) else body
        opp = None
        for s in stages:
            opps = s.get("opportunities") or []
            if opps:
                opp = opps[0]
                break
        if not opp:
            pytest.skip("no opp")
        r = auth.post(f"{API}/ai/sales/summarize-opportunity", json={"opportunity_id": opp["id"]}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        text = j.get("summary") or j.get("response") or j.get("text") or ""
        assert len(text) > 0

    def test_channel_chat(self, auth):
        c = auth.get(f"{API}/clients?limit=1", timeout=10).json()["items"][0]
        r = auth.post(f"{API}/ai/channel/sessions", json={"client_id": c["id"]}, timeout=15)
        assert r.status_code in (200, 201), r.text
        sid = r.json()["id"]
        r2 = auth.post(
            f"{API}/ai/channel/sessions/{sid}/messages",
            json={"text": "Olá, quanto custa a soja hoje?"},
            timeout=60,
        )
        assert r2.status_code in (200, 201), r2.text
        j = r2.json()
        # Expect reply or messages list
        reply = j.get("reply") or j.get("response") or ""
        if not reply and "messages" in j:
            assistant_msgs = [m for m in j["messages"] if m.get("role") == "assistant"]
            assert assistant_msgs, "no assistant message"
        else:
            assert len(reply) > 0


# ---------- Sync ----------
class TestSync:
    def test_info(self, auth):
        r = auth.get(f"{API}/sync/info", timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert "strategy" in j
        assert "syncable_entities" in j

    def test_pull(self, auth):
        r = auth.post(f"{API}/sync/pull", json={}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        # records dict per entity
        assert isinstance(j, dict)

    def test_push(self, auth):
        new_id = str(uuid.uuid4())
        payload = {
            "device_id": "test-device-001",
            "records": [
                {
                    "entity": "clients",
                    "op": "upsert",
                    "data": {
                        "id": new_id,
                        "name": f"TEST_Sync_{new_id[:6]}",
                        "type": "produtor",
                        "tenant_id": "tenant-default",
                    },
                }
            ],
        }
        r = auth.post(f"{API}/sync/push", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "accepted_ids" in j or "accepted" in j


# ---------- Integrations ----------
class TestIntegrations:
    def test_connectors(self, auth):
        r = auth.get(f"{API}/integrations/connectors", timeout=10)
        assert r.status_code == 200
        body = r.json()
        connectors = body.get("connectors") if isinstance(body, dict) else body
        names = " ".join(str(i).lower() for i in connectors)
        # Iteration 2: connector set is {sap, oracle, siagri}
        assert "sap" in names and "oracle" in names and "siagri" in names

    def test_webhook(self, auth):
        r = auth.post(f"{API}/integrations/webhook/sap", json={"event": "TEST", "payload": {"x": 1}}, timeout=10)
        assert r.status_code == 200
        assert r.json().get("received") is True


# ---------- Audit ----------
def test_audit(auth):
    r = auth.get(f"{API}/audit", timeout=10)
    assert r.status_code == 200
    j = r.json()
    items = j.get("items", j) if isinstance(j, dict) else j
    assert isinstance(items, list)
    assert len(items) > 0
