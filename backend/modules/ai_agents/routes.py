"""AI Agents with centralized LLM gateway, cache, metering, and rate limits."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.ai_gateway import generate_text, usage_summary
from core.auth import current_user, require_permission
from core.db import db
from core.models import new_uuid, utcnow
from core.permissions import ensure_document_access, ensure_permission
from core.repo import find_one, insert_entity, list_entities, write_audit

router = APIRouter()


def _system_for(agent: str) -> str:
    return {
        "marketing": (
            "Voce e o Agente de Marketing e Prospeccao do Agro CRM, especialista em agronegocio brasileiro. "
            "Analise produtores e empresas, sugira abordagens comerciais e priorize contas. "
            "Responda em portugues, com bullets curtos e acoes concretas."
        ),
        "sales": (
            "Voce e o Agente de Vendas e Pos-venda do Agro CRM. Analise oportunidades, riscos, proximos passos "
            "e follow-ups. Sempre proponha 3 acoes concretas ordenadas por impacto."
        ),
        "channel": (
            "Voce e o Agente de Canal do Cliente do Agro CRM. Use somente o contexto fornecido pelo CRM. "
            "Quando nao tiver dado suficiente, diga que vai verificar com o time comercial. Seja curto e claro. "
            "Formate a resposta para tela de CRM: use no maximo 1 paragrafo inicial, bullets curtos, "
            "titulos em negrito apenas quando ajudarem a leitura, e nunca exponha campos tecnicos como ids internos."
        ),
    }[agent]


def _compact_doc(doc: dict, omit: set[str] | None = None) -> dict:
    omit = omit or set()
    return {k: v for k, v in doc.items() if k not in {"_id", "password_hash"} | omit}


async def _build_channel_context(user: dict, client_id: Optional[str]) -> str:
    if not client_id:
        return "Sem cliente vinculado a esta sessao."
    cli = await find_one("clients", client_id, user["tenant_id"])
    if not cli:
        return "Cliente nao encontrado."
    ensure_document_access(user, "clients", cli)
    orders = await list_entities(
        "orders", user["tenant_id"], {"client_id": client_id}, limit=10, sort=[("seq_id", -1)]
    )
    contracts = await list_entities(
        "contracts", user["tenant_id"], {"client_id": client_id}, limit=10, sort=[("seq_id", -1)]
    )
    tickets = await list_entities(
        "tickets", user["tenant_id"], {"client_id": client_id}, limit=5, sort=[("seq_id", -1)]
    )
    ctx = {
        "client": {
            "name": cli.get("name"),
            "region": cli.get("region"),
            "classification": cli.get("classification"),
        },
        "contracts": [
            {
                "seq_id": c.get("seq_id"),
                "type": c.get("type"),
                "product": c.get("product_name"),
                "volume": c.get("volume"),
                "status": c.get("status"),
            }
            for c in contracts
        ],
        "orders": [
            {
                "seq_id": o.get("seq_id"),
                "type": o.get("type"),
                "total": o.get("total"),
                "status": o.get("status"),
                "logistic_status": o.get("logistic_status"),
            }
            for o in orders
        ],
        "tickets": [
            {
                "seq_id": t.get("seq_id"),
                "subject": t.get("subject"),
                "status": t.get("status"),
                "priority": t.get("priority"),
            }
            for t in tickets
        ],
    }
    return f"# CONTEXTO DO CLIENTE (CRM)\n```json\n{json.dumps(ctx, ensure_ascii=False, indent=2, default=str)}\n```"


class ProspectionRequest(BaseModel):
    client_id: str


@router.post("/marketing/analyze-client")
async def analyze_client(payload: ProspectionRequest, user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    cli = await find_one("clients", payload.client_id, user["tenant_id"])
    if not cli:
        raise HTTPException(404, "Cliente nao encontrado")
    ensure_document_access(user, "clients", cli)

    prompt = (
        "Analise o perfil deste cliente e produza:\n"
        "1) Score de potencial (0-100) com justificativa\n"
        "2) Culturas/insumos provaveis com maior fit\n"
        "3) Abordagem recomendada (canal + tema + 2 ganchos)\n"
        "4) Riscos e objecoes esperadas\n\n"
        f"PERFIL:\n```json\n{json.dumps(_compact_doc(cli), ensure_ascii=False, indent=2, default=str)}\n```"
    )
    result = await generate_text(
        agent="marketing",
        system=_system_for("marketing"),
        prompt=prompt,
        user=user,
        cache=True,
        metadata={"client_id": payload.client_id},
    )
    out = {
        "agent": "marketing",
        "client_id": payload.client_id,
        "client_name": cli.get("name"),
        "analysis": result["text"],
        "cached": result["cached"],
        "usage": result["usage"],
        "generated_at": utcnow().isoformat(),
    }
    await db.ai_outputs.insert_one({**out, "id": new_uuid(), "tenant_id": user["tenant_id"], "branch_id": cli.get("branch_id")})
    return out


class OppSummaryRequest(BaseModel):
    opportunity_id: str


@router.post("/sales/summarize-opportunity")
async def summarize_opp(payload: OppSummaryRequest, user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    opp = await find_one("opportunities", payload.opportunity_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade nao encontrada")
    ensure_document_access(user, "opportunities", opp)
    cli = await find_one("clients", opp.get("client_id"), user["tenant_id"])
    interactions = await list_entities(
        "interactions",
        user["tenant_id"],
        {"opportunity_id": payload.opportunity_id},
        limit=25,
        sort=[("seq_id", -1)],
    )
    payload_json = json.dumps(
        {
            "opportunity": _compact_doc(opp),
            "client": {
                "name": (cli or {}).get("name"),
                "region": (cli or {}).get("region"),
                "classification": (cli or {}).get("classification"),
            },
            "interactions": [
                {"type": i.get("type"), "notes": i.get("notes"), "at": i.get("created_at")}
                for i in interactions
            ],
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    prompt = (
        "Resuma a negociacao em ate 5 bullets, depois liste 3 proximas acoes concretas "
        "ordenadas por impacto e finalize com alerta de risco se houver.\n\n"
        f"DADOS:\n```json\n{payload_json}\n```"
    )
    result = await generate_text(
        agent="sales",
        system=_system_for("sales"),
        prompt=prompt,
        user=user,
        cache=True,
        metadata={"opportunity_id": payload.opportunity_id},
    )
    out = {
        "agent": "sales",
        "opportunity_id": payload.opportunity_id,
        "summary": result["text"],
        "cached": result["cached"],
        "usage": result["usage"],
        "generated_at": utcnow().isoformat(),
    }
    await db.ai_outputs.insert_one({**out, "id": new_uuid(), "tenant_id": user["tenant_id"], "branch_id": opp.get("branch_id")})
    return out


class ChatStart(BaseModel):
    client_id: Optional[str] = None
    title: Optional[str] = None


class ChatMessage(BaseModel):
    text: str


@router.post("/channel/sessions")
async def start_session(payload: ChatStart, user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    branch_id = None
    if payload.client_id:
        cli = await find_one("clients", payload.client_id, user["tenant_id"])
        if not cli:
            raise HTTPException(404, "Cliente nao encontrado")
        ensure_document_access(user, "clients", cli)
        branch_id = cli.get("branch_id")
    session = await insert_entity(
        "ai_sessions",
        {
            "tenant_id": user["tenant_id"],
            "branch_id": branch_id,
            "agent": "channel",
            "user_id": user["id"],
            "client_id": payload.client_id,
            "title": payload.title or "Nova conversa",
            "messages": [],
        },
        user,
    )
    return session


@router.get("/channel/sessions")
async def list_sessions(user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    return await list_entities(
        "ai_sessions",
        user["tenant_id"],
        {"user_id": user["id"]},
        limit=50,
        sort=[("updated_at", -1)],
    )


@router.get("/channel/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    s = await find_one("ai_sessions", session_id, user["tenant_id"])
    if not s:
        raise HTTPException(404, "Sessao nao encontrada")
    ensure_document_access(user, "ai_sessions", s)
    return s


@router.post("/channel/sessions/{session_id}/messages")
async def send_message(session_id: str, payload: ChatMessage, user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    s = await find_one("ai_sessions", session_id, user["tenant_id"])
    if not s:
        raise HTTPException(404, "Sessao nao encontrada")
    ensure_document_access(user, "ai_sessions", s)

    history = (s.get("messages") or [])[-12:]
    ctx = await _build_channel_context(user, s.get("client_id"))
    prompt = (
        f"{ctx}\n\n"
        f"HISTORICO RECENTE:\n```json\n{json.dumps(history, ensure_ascii=False, indent=2, default=str)}\n```\n\n"
        f"MENSAGEM DO USUARIO:\n{payload.text}"
    )
    result = await generate_text(
        agent="channel",
        system=_system_for("channel"),
        prompt=prompt,
        user=user,
        cache=False,
        metadata={"session_id": session_id, "client_id": s.get("client_id")},
    )
    now = utcnow().isoformat()
    user_msg = {"role": "user", "text": payload.text, "at": now}
    ai_msg = {"role": "assistant", "text": result["text"], "at": now, "usage": result["usage"]}
    new_messages = s.get("messages", []) + [user_msg, ai_msg]
    await db.ai_sessions.update_one(
        {"id": session_id, "tenant_id": user["tenant_id"]},
        {"$set": {"messages": new_messages, "updated_at": utcnow()}},
    )
    return {"reply": result["text"], "messages": new_messages, "usage": result["usage"]}


@router.get("/usage")
async def ai_usage(user: dict = Depends(current_user)):
    ensure_permission(user, "ai.use")
    return await usage_summary(user)


class AiPolicyPatch(BaseModel):
    user_per_minute: Optional[int] = None
    user_daily_limit: Optional[int] = None
    tenant_daily_limit: Optional[int] = None
    monthly_token_budget: Optional[int] = None
    max_input_chars: Optional[int] = None
    max_output_tokens: Optional[int] = None
    cache_ttl_seconds: Optional[int] = None


@router.patch("/settings")
async def update_ai_settings(payload: AiPolicyPatch, user: dict = Depends(require_permission("ai.configure"))):
    current = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0, "ai_policy": 1})
    before = (current or {}).get("ai_policy") or {}
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    for key, value in patch.items():
        if value < 1:
            raise HTTPException(422, f"{key} deve ser maior que zero")
    after = {**before, **patch}
    await db.tenants.update_one({"id": user["tenant_id"]}, {"$set": {"ai_policy": after, "updated_at": utcnow()}})
    await write_audit("tenants", user["tenant_id"], "ai_policy_update", {"ai_policy": before}, {"ai_policy": after}, user)
    return {"ai_policy": after}
