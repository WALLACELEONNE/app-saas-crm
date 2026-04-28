"""Pipeline module — Sales stages, Opportunities and Interactions (history)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.auth import current_user
from core.crud import make_crud_router
from core.repo import (insert_entity, update_entity, find_one, list_entities,
                       soft_delete)
from core.db import db
from core.models import utcnow

# ----- Stages -----
class StageCreate(BaseModel):
    name: str
    order: int
    color: Optional[str] = None


class StageUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None
    color: Optional[str] = None


# ----- Opportunities -----
class OppCreate(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    stage_id: str
    stage_name: Optional[str] = None
    title: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    volume: Optional[float] = None
    unit: Optional[str] = "ton"
    value: float = 0
    currency: str = "BRL"
    probability: int = 0
    expected_close: Optional[str] = None
    notes: Optional[str] = None
    history: list[dict] = Field(default_factory=list)


class OppUpdate(BaseModel):
    client_id: Optional[str] = None
    stage_id: Optional[str] = None
    stage_name: Optional[str] = None
    title: Optional[str] = None
    value: Optional[float] = None
    probability: Optional[int] = None
    expected_close: Optional[str] = None
    notes: Optional[str] = None


class StageMove(BaseModel):
    stage_id: str
    stage_name: Optional[str] = None


class InteractionCreate(BaseModel):
    type: str  # call/email/meeting/note
    notes: str


# ---- Routers ----
router = APIRouter()
stages_router = make_crud_router("pipeline_stages", StageCreate, StageUpdate)
opps_router = make_crud_router("opportunities", OppCreate, OppUpdate,
                                search_fields=["title", "client_name"])

router.include_router(stages_router, prefix="/stages")
router.include_router(opps_router, prefix="/opportunities")


@router.get("/board")
async def board(user: dict = Depends(current_user)):
    """Kanban board — stages with their opportunities grouped."""
    stages = await list_entities("pipeline_stages", user["tenant_id"],
                                 sort=[("order", 1)], limit=100)
    opps = await list_entities("opportunities", user["tenant_id"], limit=500,
                               sort=[("seq_id", -1)])
    by_stage: dict[str, list] = {s["id"]: [] for s in stages}
    for o in opps:
        by_stage.setdefault(o.get("stage_id"), []).append(o)
    total_value = sum(o.get("value", 0) for o in opps)
    return {
        "stages": [{**s, "opportunities": by_stage.get(s["id"], []),
                    "total_value": sum(o.get("value", 0) for o in by_stage.get(s["id"], []))}
                   for s in stages],
        "total_value": total_value,
        "total_opportunities": len(opps),
    }


@router.post("/opportunities/{opp_id}/move")
async def move_stage(opp_id: str, payload: StageMove, user: dict = Depends(current_user)):
    stage = await find_one("pipeline_stages", payload.stage_id, user["tenant_id"])
    if not stage:
        raise HTTPException(404, "Estágio inválido")
    opp = await find_one("opportunities", opp_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada")
    history = opp.get("history", [])
    history.append({
        "type": "stage_change",
        "from": opp.get("stage_name"),
        "to": stage["name"],
        "by": user.get("email"),
        "at": utcnow().isoformat(),
    })
    return await update_entity("opportunities", opp_id, user["tenant_id"], {
        "stage_id": stage["id"], "stage_name": stage["name"], "history": history,
    }, user)


@router.post("/opportunities/{opp_id}/interactions")
async def add_interaction(opp_id: str, payload: InteractionCreate,
                          user: dict = Depends(current_user)):
    opp = await find_one("opportunities", opp_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade não encontrada")
    inter = await insert_entity("interactions", {
        "tenant_id": user["tenant_id"],
        "opportunity_id": opp_id,
        "type": payload.type,
        "notes": payload.notes,
    }, user)
    history = opp.get("history", [])
    history.append({"type": "interaction", "kind": payload.type,
                     "notes": payload.notes, "by": user.get("email"),
                     "at": utcnow().isoformat()})
    await update_entity("opportunities", opp_id, user["tenant_id"],
                       {"history": history}, user)
    return inter


@router.get("/opportunities/{opp_id}/interactions")
async def list_interactions(opp_id: str, user: dict = Depends(current_user)):
    return await list_entities("interactions", user["tenant_id"],
                               {"opportunity_id": opp_id},
                               sort=[("seq_id", -1)], limit=200)
