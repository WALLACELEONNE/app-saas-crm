"""
AI Agents — 3 GPT-5.2 agents via emergentintegrations:
1. Marketing/Prospection — lead analysis, approach suggestion
2. Sales/Post-sale — pipeline next steps, negotiation summary, follow-up alerts
3. Customer Channel — multi-turn chat with CRM context (orders, contracts, status)
"""
import os
import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from emergentintegrations.llm.chat import LlmChat, UserMessage

from core.auth import current_user
from core.db import db
from core.repo import insert_entity, find_one, list_entities
from core.models import utcnow, new_uuid

router = APIRouter()
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
DEFAULT_MODEL = ("openai", "gpt-5.2")


# --------- Helpers ---------
def _system_for(agent: str) -> str:
    return {
        "marketing": (
            "Você é o **Agente de Marketing & Prospecção** do Agro CRM, especialista em agronegócio brasileiro. "
            "Sua missão: analisar perfis de produtores e empresas, gerar leads qualificados, sugerir abordagens "
            "comerciais (cold mail, WhatsApp, visita) e priorizar contas. Use linguagem direta, técnica, "
            "considerando ciclo agrícola, cultura, região, área plantada e potencial de barter. "
            "Responda em português, com bullet points e ações concretas."
        ),
        "sales": (
            "Você é o **Agente de Vendas & Pós-venda** do Agro CRM. Sua missão: analisar oportunidades no "
            "pipeline e sugerir os próximos passos, resumir negociações em uma narrativa concisa, gerar "
            "alertas de follow-up e identificar riscos de perda. Considere preço de mercado, sazonalidade e "
            "histórico de interações. Sempre proponha 3 próximas ações concretas, ordenadas por impacto."
        ),
        "channel": (
            "Você é o **Agente de Canal do Cliente** — assistente conversacional do Agro CRM para clientes "
            "(produtores, cooperativas e empresas). Use SOMENTE o contexto fornecido pelo CRM (pedidos, "
            "contratos, status logístico, tickets) para responder. Quando não tiver dado, diga que vai "
            "verificar com o time comercial. Seja cordial, claro, em português e use formato curto."
        ),
    }[agent]


async def _build_channel_context(tenant_id: str, client_id: Optional[str]) -> str:
    """Inject CRM context for the customer channel agent."""
    if not client_id:
        return "Sem cliente vinculado a esta sessão."
    cli = await find_one("clients", client_id, tenant_id)
    if not cli:
        return "Cliente não encontrado."
    orders = await list_entities("orders", tenant_id, {"client_id": client_id}, limit=10,
                                 sort=[("seq_id", -1)])
    contracts = await list_entities("contracts", tenant_id, {"client_id": client_id}, limit=10,
                                    sort=[("seq_id", -1)])
    tickets = await list_entities("tickets", tenant_id, {"client_id": client_id}, limit=5,
                                  sort=[("seq_id", -1)])

    ctx = {
        "client": {"name": cli.get("name"), "region": cli.get("region"),
                   "classification": cli.get("classification")},
        "contracts": [{"seq_id": c.get("seq_id"), "type": c.get("type"),
                       "product": c.get("product_name"), "volume": c.get("volume"),
                       "status": c.get("status")} for c in contracts],
        "orders": [{"seq_id": o.get("seq_id"), "type": o.get("type"),
                    "total": o.get("total"), "status": o.get("status"),
                    "logistic_status": o.get("logistic_status")} for o in orders],
        "tickets": [{"seq_id": t.get("seq_id"), "subject": t.get("subject"),
                     "status": t.get("status"), "priority": t.get("priority")} for t in tickets],
    }
    return f"# CONTEXTO DO CLIENTE (do CRM)\n```json\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n```"


# --------- Marketing/Prospection agent ---------
class ProspectionRequest(BaseModel):
    client_id: str


@router.post("/marketing/analyze-client")
async def analyze_client(payload: ProspectionRequest, user: dict = Depends(current_user)):
    cli = await find_one("clients", payload.client_id, user["tenant_id"])
    if not cli:
        raise HTTPException(404, "Cliente não encontrado")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY não configurada")

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"marketing-{payload.client_id}-{user['id']}",
        system_message=_system_for("marketing"),
    ).with_model(*DEFAULT_MODEL)

    prompt = (
        "Analise o perfil deste cliente e produza:\n"
        "1) Score de potencial (0-100) com justificativa\n"
        "2) Cultura/insumos prováveis com maior fit\n"
        "3) Sugestão de abordagem (canal + tema central + 2 ganchos)\n"
        "4) Riscos e objeções esperadas\n\n"
        f"PERFIL DO CLIENTE:\n```json\n{json.dumps({k: v for k, v in cli.items() if k not in ('_id',)}, ensure_ascii=False, indent=2, default=str)}\n```"
    )
    msg = UserMessage(text=prompt)
    response = await chat.send_message(msg)
    out = {
        "agent": "marketing",
        "client_id": payload.client_id,
        "client_name": cli.get("name"),
        "analysis": response,
        "generated_at": utcnow().isoformat(),
    }
    await db.ai_outputs.insert_one({**out, "id": new_uuid(), "tenant_id": user["tenant_id"]})
    return out


# --------- Sales/Post-sale agent ---------
class OppSummaryRequest(BaseModel):
    opportunity_id: str


@router.post("/sales/summarize-opportunity")
async def summarize_opp(payload: OppSummaryRequest, user: dict = Depends(current_user)):
    opp = await find_one("opportunities", payload.opportunity_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY não configurada")

    cli = await find_one("clients", opp.get("client_id"), user["tenant_id"])
    interactions = await list_entities("interactions", user["tenant_id"],
                                       {"opportunity_id": payload.opportunity_id},
                                       limit=50, sort=[("seq_id", -1)])

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"sales-{payload.opportunity_id}-{user['id']}",
        system_message=_system_for("sales"),
    ).with_model(*DEFAULT_MODEL)

    payload_json = json.dumps({
        "opportunity": {k: v for k, v in opp.items() if k != "_id"},
        "client": {"name": (cli or {}).get("name"), "region": (cli or {}).get("region"),
                   "classification": (cli or {}).get("classification")},
        "interactions": [{"type": i.get("type"), "notes": i.get("notes"),
                          "at": i.get("created_at")} for i in interactions],
    }, ensure_ascii=False, indent=2, default=str)

    prompt = (
        "Resuma a negociação em até 5 bullets (status, valor, principais pontos), "
        "depois liste 3 próximas ações concretas ordenadas por impacto, e finalize "
        "com um alerta se houver risco (ou 'sem riscos imediatos').\n\n"
        f"DADOS:\n```json\n{payload_json}\n```"
    )
    response = await chat.send_message(UserMessage(text=prompt))
    out = {
        "agent": "sales",
        "opportunity_id": payload.opportunity_id,
        "summary": response,
        "generated_at": utcnow().isoformat(),
    }
    await db.ai_outputs.insert_one({**out, "id": new_uuid(), "tenant_id": user["tenant_id"]})
    return out


# --------- Customer Channel agent (multi-turn chat) ---------
class ChatStart(BaseModel):
    client_id: Optional[str] = None
    title: Optional[str] = None


class ChatMessage(BaseModel):
    text: str


@router.post("/channel/sessions")
async def start_session(payload: ChatStart, user: dict = Depends(current_user)):
    session = await insert_entity("ai_sessions", {
        "tenant_id": user["tenant_id"],
        "agent": "channel",
        "user_id": user["id"],
        "client_id": payload.client_id,
        "title": payload.title or "Nova conversa",
        "messages": [],
    }, user)
    return session


@router.get("/channel/sessions")
async def list_sessions(user: dict = Depends(current_user)):
    return await list_entities("ai_sessions", user["tenant_id"],
                              {"user_id": user["id"]}, limit=50,
                              sort=[("updated_at", -1)])


@router.get("/channel/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(current_user)):
    s = await find_one("ai_sessions", session_id, user["tenant_id"])
    if not s:
        raise HTTPException(404, "Sessão não encontrada")
    return s


@router.post("/channel/sessions/{session_id}/messages")
async def send_message(session_id: str, payload: ChatMessage,
                       user: dict = Depends(current_user)):
    s = await find_one("ai_sessions", session_id, user["tenant_id"])
    if not s:
        raise HTTPException(404, "Sessão não encontrada")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY não configurada")

    ctx = await _build_channel_context(user["tenant_id"], s.get("client_id"))
    system = _system_for("channel") + "\n\n" + ctx

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"channel-{session_id}",
        system_message=system,
    ).with_model(*DEFAULT_MODEL)

    # Replay prior messages for context (multi-turn)
    for m in s.get("messages", []):
        if m.get("role") == "user":
            await chat.send_message(UserMessage(text=m["text"]))

    response = await chat.send_message(UserMessage(text=payload.text))

    now = utcnow().isoformat()
    user_msg = {"role": "user", "text": payload.text, "at": now}
    ai_msg = {"role": "assistant", "text": response, "at": now}

    new_messages = s.get("messages", []) + [user_msg, ai_msg]
    await db.ai_sessions.update_one(
        {"id": session_id, "tenant_id": user["tenant_id"]},
        {"$set": {"messages": new_messages, "updated_at": utcnow()}},
    )
    return {"reply": response, "messages": new_messages}
