"""
ERP Integrations worker + connectors + simulator + outbox tests.
Covers iteration 2 requirements: durable outbox, vendor connectors (sap/oracle/siagri),
internal simulator endpoint, retry, and admin-only configuration.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@agrocrm.com", "password": "Admin@123"}
TRADER = {"email": "trader@agrocrm.com", "password": "Trader@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {_login(ADMIN)}"})
    return s


@pytest.fixture(scope="module")
def trader():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {_login(TRADER)}"})
    return s


# ---- Connectors registry ----
class TestConnectors:
    def test_list_connectors(self, admin):
        r = admin.get(f"{API}/integrations/connectors", timeout=10)
        assert r.status_code == 200
        body = r.json()
        connectors = {c["vendor"]: c for c in body["connectors"]}
        for v in ("sap", "oracle", "siagri"):
            assert v in connectors, f"missing {v}"
            c = connectors[v]
            assert c["enabled"] is True, f"{v} not enabled: {c}"
            assert c["endpoint"], f"{v} no endpoint"
            assert "_simulator" in c["endpoint"], f"{v} should default to internal simulator"

    def test_test_connector_sap(self, admin):
        body = {"topic": "clients.create",
                "payload": {"after": {"seq_id": 999, "name": "Test", "type": "producer"}}}
        r = admin.post(f"{API}/integrations/connectors/sap/test", json=body, timeout=15)
        assert r.status_code == 200, r.text
        res = r.json()["result"]
        assert res["ok"] is True
        assert res["status_code"] == 200
        assert res["latency_ms"] < 2000

    def test_configure_admin(self, admin):
        # change endpoint to a different valid path (still simulator)
        new_ep = f"{BASE_URL}/api/integrations/_simulator/sap"
        r = admin.post(f"{API}/integrations/connectors/sap/configure",
                       json={"endpoint": new_ep, "enabled": True}, timeout=10)
        assert r.status_code == 200, r.text
        # verify
        r2 = admin.get(f"{API}/integrations/connectors", timeout=10)
        sap = next(c for c in r2.json()["connectors"] if c["vendor"] == "sap")
        assert sap["endpoint"] == new_ep
        assert sap["enabled"] is True

    def test_configure_forbidden_for_trader(self, trader):
        r = trader.post(f"{API}/integrations/connectors/sap/configure",
                        json={"endpoint": "https://example.invalid", "enabled": True}, timeout=10)
        assert r.status_code == 403

    def test_simulator_public(self):
        # No auth header
        r = requests.post(f"{API}/integrations/_simulator/sap",
                          json={"hello": "world"}, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ack"] is True
        assert j["vendor_ref"].startswith("SAP-")


# ---- End-to-end: domain event -> outbox -> dispatch -> simulator ----
class TestOutboxFlow:
    created_client_id = None
    created_contract_id = None

    def test_create_client_emits_event_to_outbox(self, admin):
        payload = {
            "name": f"TEST_ERPClient_{uuid.uuid4().hex[:6]}",
            "type": "producer",
            "region": "MT",
            "culture": ["soja"],
            "classification": "A",
        }
        r = admin.post(f"{API}/clients", json=payload, timeout=10)
        assert r.status_code in (200, 201), r.text
        TestOutboxFlow.created_client_id = r.json()["id"]

        # wait for worker poll (every 2s) + dispatch to finish
        delivered_event = None
        for _ in range(8):  # up to 8s
            time.sleep(1)
            r2 = admin.get(f"{API}/integrations/outbox?limit=200", timeout=10)
            assert r2.status_code == 200
            for e in r2.json()["items"]:
                if (e.get("topic") == "clients.create"
                        and e.get("payload", {}).get("after", {}).get("id") == TestOutboxFlow.created_client_id
                        and e.get("status") == "delivered"):
                    delivered_event = e
                    break
            if delivered_event:
                break
        assert delivered_event, "clients.create event was not delivered within timeout"

    def test_deliveries_for_client_event(self, admin):
        # siagri + sap should have delivered (oracle does NOT subscribe to clients.*)
        r = admin.get(f"{API}/integrations/deliveries?limit=200", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        # filter deliveries linked to our created client
        cid = TestOutboxFlow.created_client_id
        related = [d for d in items
                   if d.get("topic") == "clients.create"
                   and d.get("payload_summary", {}).get("topic") == "clients.create"
                   and d.get("ok") is True]
        # At least one delivery for sap and siagri
        vendors_seen = {d["vendor"] for d in items
                        if d.get("topic") == "clients.create" and d.get("ok") is True}
        assert "sap" in vendors_seen, f"sap missing from clients.create deliveries: {vendors_seen}"
        assert "siagri" in vendors_seen, f"siagri missing: {vendors_seen}"
        assert "oracle" not in {d["vendor"] for d in items
                                if d.get("topic") == "clients.create"}, \
            "oracle should NOT receive clients.* events"
        # All sap/siagri deliveries on clients.create should have status_code 200
        for d in items:
            if d.get("topic") == "clients.create" and d.get("vendor") in ("sap", "siagri"):
                assert d.get("status_code") == 200, d

    def test_create_contract_dispatches_to_all_three(self, admin):
        c = admin.get(f"{API}/clients?limit=1", timeout=10).json()["items"][0]
        p = admin.get(f"{API}/products?limit=1", timeout=10).json()["items"][0]
        r = admin.post(f"{API}/contracts", json={
            "type": "sell", "client_id": c["id"], "product_id": p["id"],
            "volume": 100, "price": 150.5, "currency": "BRL",
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        TestOutboxFlow.created_contract_id = r.json()["id"]

        # Wait for outbox
        vendors_delivered: set = set()
        for _ in range(10):
            time.sleep(1)
            d = admin.get(f"{API}/integrations/deliveries?limit=200", timeout=10).json()["items"]
            for x in d:
                if x.get("topic") == "contracts.create" and x.get("ok") is True:
                    vendors_delivered.add(x["vendor"])
            if {"sap", "oracle", "siagri"}.issubset(vendors_delivered):
                break
        assert {"sap", "oracle", "siagri"}.issubset(vendors_delivered), \
            f"contract not delivered to all vendors: {vendors_delivered}"

    def test_siagri_simulator_log_has_pt_fields(self, admin):
        r = admin.get(f"{API}/integrations/_simulator/siagri/log?limit=50", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        # Look for a Produtor (clients) and ContratoGraos (contracts) entry
        kinds = {it.get("body", {}).get("entidade") for it in items}
        assert "Produtor" in kinds or "Cliente" in kinds, f"no Produtor/Cliente entries: {kinds}"
        assert "ContratoGraos" in kinds, f"no ContratoGraos entry: {kinds}"

    def test_outbox_retry(self, admin):
        # Find a delivered event and retry it
        r = admin.get(f"{API}/integrations/outbox?status=delivered&limit=5", timeout=10)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("No delivered events to retry")
        eid = items[0]["id"]
        r2 = admin.post(f"{API}/integrations/outbox/{eid}/retry", timeout=10)
        assert r2.status_code == 200, r2.text
        assert r2.json()["retried"] is True

    def test_outbox_counters(self, admin):
        r = admin.get(f"{API}/integrations/outbox?limit=1", timeout=10)
        assert r.status_code == 200
        counts = r.json().get("counts", {})
        # delivered should be present and >= 1 from earlier flows
        assert counts.get("delivered", 0) >= 1, counts
