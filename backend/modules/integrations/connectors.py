"""
ERP Connectors — concrete implementations for SAP S/4HANA, Oracle EBS and
Siagri Agribusiness. Each connector knows how to transform a domain event into
the vendor-specific payload and deliver it via HTTP. In dev / preview, deliveries
default to the built-in simulator (/api/integrations/_simulator/{vendor}) which
records the call and returns 200 OK.
"""
from __future__ import annotations
import os
import time
import httpx
from typing import Optional
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_base() -> str:
    # In prod each connector points to the real ERP; here we default to ourselves
    # (the simulator) so workers can be exercised end-to-end.
    return os.environ.get("INTERNAL_BASE_URL", "http://localhost:8001")


class ConnectorBase:
    vendor: str = "base"
    name: str = "Base"
    topics: tuple[str, ...] = ()  # e.g. ("clients.*", "contracts.*")

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}
        self.endpoint = self.config.get("endpoint") or f"{_http_base()}/api/integrations/_simulator/{self.vendor}"
        self.headers = self.config.get("headers") or {}

    def matches(self, topic: str) -> bool:
        for pat in self.topics:
            if pat == "*" or pat == topic:
                return True
            if pat.endswith(".*") and topic.startswith(pat[:-1]):
                return True
        return False

    def transform(self, event: dict) -> dict:
        """Map the domain event to vendor payload. Default: passthrough."""
        return {
            "vendor": self.vendor,
            "topic": event.get("topic"),
            "data": event.get("payload"),
            "timestamp": _utcnow_iso(),
        }

    async def deliver(self, event: dict) -> dict:
        """Send the transformed event to the ERP endpoint. Returns delivery info."""
        payload = self.transform(event)
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(self.endpoint, json=payload, headers=self.headers)
            return {
                "ok": 200 <= resp.status_code < 300,
                "status_code": resp.status_code,
                "response": _trim_text(resp.text),
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "endpoint": self.endpoint,
                "payload_summary": {"topic": event.get("topic"),
                                    "keys": list((event.get("payload") or {}).keys())[:6]},
            }
        except Exception as e:
            return {
                "ok": False,
                "status_code": 0,
                "response": f"exception: {e.__class__.__name__}: {str(e)[:300]}",
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "endpoint": self.endpoint,
                "payload_summary": {"topic": event.get("topic")},
            }


def _trim_text(s: Optional[str], n: int = 600) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[:n] + "...[trimmed]"


# ----------------------------------------------------------------------
# SAP S/4HANA — REST/OData wrapper. In prod this would map to BAPI/IDoc.
# ----------------------------------------------------------------------
class SAPConnector(ConnectorBase):
    vendor = "sap"
    name = "SAP S/4HANA"
    topics = ("clients.*", "contracts.*", "orders.*")

    def transform(self, event: dict) -> dict:
        topic = event.get("topic", "")
        data = event.get("payload", {}) or {}
        after = data.get("after") or {}
        if topic.startswith("clients."):
            return {
                "vendor": "sap",
                "object": "BusinessPartner",
                "operation": _op_from_topic(topic),
                "BusinessPartner": after.get("seq_id"),
                "BusinessPartnerName": after.get("name"),
                "TaxID": after.get("doc"),
                "Country": "BR",
                "Region": after.get("region"),
                "ExternalID": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("contracts."):
            return {
                "vendor": "sap",
                "object": "PurchaseContract" if after.get("type") == "buy" else "SalesContract",
                "operation": _op_from_topic(topic),
                "ContractID": after.get("seq_id"),
                "BusinessPartnerExternalID": after.get("client_id"),
                "Material": after.get("product_name"),
                "Quantity": after.get("volume"),
                "Unit": after.get("unit"),
                "Price": after.get("price"),
                "Currency": after.get("currency", "BRL"),
                "Status": after.get("status"),
                "ExternalID": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("orders."):
            return {
                "vendor": "sap",
                "object": "SalesOrder" if after.get("type") == "sale" else "PurchaseOrder",
                "operation": _op_from_topic(topic),
                "OrderID": after.get("seq_id"),
                "BusinessPartnerExternalID": after.get("client_id"),
                "TotalNetAmount": after.get("total"),
                "Currency": after.get("currency", "BRL"),
                "OverallStatus": after.get("status"),
                "DeliveryStatus": after.get("logistic_status"),
                "ExternalID": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        return super().transform(event)


# ----------------------------------------------------------------------
# Oracle EBS — REST mapping (TradingCommunity + OM modules).
# ----------------------------------------------------------------------
class OracleConnector(ConnectorBase):
    vendor = "oracle"
    name = "Oracle EBS"
    topics = ("contracts.*", "orders.*")

    def transform(self, event: dict) -> dict:
        topic = event.get("topic", "")
        after = (event.get("payload") or {}).get("after") or {}
        if topic.startswith("contracts."):
            return {
                "vendor": "oracle",
                "module": "OM",
                "object": "Contract",
                "action": _op_from_topic(topic),
                "contract_number": after.get("seq_id"),
                "party_id_external": after.get("client_id"),
                "item_name": after.get("product_name"),
                "quantity": after.get("volume"),
                "uom": after.get("unit"),
                "unit_price": after.get("price"),
                "currency_code": after.get("currency", "BRL"),
                "contract_type": after.get("type"),
                "status": after.get("status"),
                "external_ref": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("orders."):
            return {
                "vendor": "oracle",
                "module": "OM",
                "object": "SalesOrder" if after.get("type") == "sale" else "PurchaseOrder",
                "action": _op_from_topic(topic),
                "order_number": after.get("seq_id"),
                "party_id_external": after.get("client_id"),
                "ordered_amount": after.get("total"),
                "currency_code": after.get("currency", "BRL"),
                "header_status": after.get("status"),
                "ship_status": after.get("logistic_status"),
                "external_ref": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        return super().transform(event)


# ----------------------------------------------------------------------
# Siagri Agribusiness — Brazilian agro ERP. REST/JSON API.
# Common entities: Produtor, Contrato, PedidoVenda, Carga, Talhao.
# ----------------------------------------------------------------------
class SiagriConnector(ConnectorBase):
    vendor = "siagri"
    name = "Siagri Agribusiness"
    topics = ("clients.*", "contracts.*", "orders.*", "cargas.*")

    def transform(self, event: dict) -> dict:
        topic = event.get("topic", "")
        after = (event.get("payload") or {}).get("after") or {}
        if topic.startswith("clients."):
            kind = "Produtor" if after.get("type") == "producer" else "Cliente"
            return {
                "vendor": "siagri",
                "entidade": kind,
                "acao": _op_from_topic(topic),
                "codigoExterno": str(after.get("seq_id")),
                "nome": after.get("name"),
                "cpfCnpj": after.get("doc"),
                "regiao": after.get("region"),
                "culturas": after.get("culture"),
                "areaHectares": after.get("area_ha"),
                "potencial": after.get("potential"),
                "tier": after.get("classification"),
                "uuid": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("contracts."):
            tipo_map = {"sell": "Venda", "buy": "Compra", "barter": "Barter"}
            return {
                "vendor": "siagri",
                "entidade": "ContratoGraos",
                "acao": _op_from_topic(topic),
                "numero": after.get("seq_id"),
                "tipo": tipo_map.get(after.get("type"), "Outro"),
                "produtorCodigoExterno": after.get("client_id"),
                "produto": after.get("product_name"),
                "volumeToneladas": after.get("volume"),
                "precoToneladaBRL": after.get("price"),
                "janelaEntrega": after.get("delivery_window"),
                "status": after.get("status"),
                "uuid": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("orders."):
            return {
                "vendor": "siagri",
                "entidade": "PedidoVenda" if after.get("type") == "sale" else "PedidoCompra",
                "acao": _op_from_topic(topic),
                "numero": after.get("seq_id"),
                "produtorCodigoExterno": after.get("client_id"),
                "valorTotalBRL": after.get("total"),
                "statusFinanceiro": after.get("status"),
                "statusLogistico": after.get("logistic_status"),
                "uuid": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        if topic.startswith("cargas."):
            return {
                "vendor": "siagri",
                "entidade": "Carga",
                "acao": _op_from_topic(topic),
                "numero": after.get("seq_id"),
                "placaVeiculo": after.get("vehicle_plate"),
                "motorista": after.get("driver"),
                "origem": after.get("origin"),
                "destino": after.get("destination"),
                "status": after.get("status"),
                "pedidoUuid": after.get("order_id"),
                "uuid": after.get("id"),
                "_topic": topic, "_at": _utcnow_iso(),
            }
        return super().transform(event)


def _op_from_topic(topic: str) -> str:
    if topic.endswith(".create"): return "CREATE"
    if topic.endswith(".update"): return "UPDATE"
    if topic.endswith(".delete"): return "DELETE"
    if topic.endswith(".restore"): return "RESTORE"
    return "UPSERT"


# Factory --------------------------------------------------------------
def build_connector(vendor: str, config: Optional[dict] = None) -> ConnectorBase:
    cls = {
        "sap": SAPConnector,
        "oracle": OracleConnector,
        "siagri": SiagriConnector,
    }.get(vendor, ConnectorBase)
    c = cls(config)
    c.vendor = vendor
    return c
