"""Pipeline module - sales stages, opportunities and interactions."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.auth import current_user
from core.crud import make_crud_router
from core.repo import insert_entity, update_entity, find_one, list_entities
from core.models import utcnow
from core.permissions import (
    apply_branch_scope,
    ensure_document_access,
    ensure_permission,
    scoped_query,
)


class StageCreate(BaseModel):
    name: str
    order: int
    color: Optional[str] = None


class StageUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None
    color: Optional[str] = None


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
    type: str
    notes: str


router = APIRouter()
stages_router = make_crud_router("pipeline_stages", StageCreate, StageUpdate)
opps_router = make_crud_router(
    "opportunities", OppCreate, OppUpdate, search_fields=["title", "client_name"]
)

router.include_router(stages_router, prefix="/stages")
router.include_router(opps_router, prefix="/opportunities")


@router.get("/board")
async def board(user: dict = Depends(current_user)):
    ensure_permission(user, "pipeline.view")
    stages = await list_entities(
        "pipeline_stages", user["tenant_id"], sort=[("order", 1)], limit=100
    )
    opps = await list_entities(
        "opportunities",
        user["tenant_id"],
        scoped_query(user, "opportunities"),
        limit=500,
        sort=[("seq_id", -1)],
    )
    by_stage: dict[str, list] = {s["id"]: [] for s in stages}
    for opp in opps:
        by_stage.setdefault(opp.get("stage_id"), []).append(opp)
    return {
        "stages": [
            {
                **stage,
                "opportunities": by_stage.get(stage["id"], []),
                "total_value": sum(o.get("value", 0) for o in by_stage.get(stage["id"], [])),
            }
            for stage in stages
        ],
        "total_value": sum(o.get("value", 0) for o in opps),
        "total_opportunities": len(opps),
    }


@router.post("/opportunities/{opp_id}/move")
async def move_stage(opp_id: str, payload: StageMove, user: dict = Depends(current_user)):
    ensure_permission(user, "pipeline.move")
    stage = await find_one("pipeline_stages", payload.stage_id, user["tenant_id"])
    if not stage:
        raise HTTPException(404, "Estagio invalido")
    opp = await find_one("opportunities", opp_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade nao encontrada")
    ensure_document_access(user, "opportunities", opp)
    history = opp.get("history", [])
    history.append({
        "type": "stage_change",
        "from": opp.get("stage_name"),
        "to": stage["name"],
        "by": user.get("email"),
        "at": utcnow().isoformat(),
    })
    return await update_entity(
        "opportunities",
        opp_id,
        user["tenant_id"],
        {"stage_id": stage["id"], "stage_name": stage["name"], "history": history},
        user,
    )


@router.post("/opportunities/{opp_id}/interactions")
async def add_interaction(
    opp_id: str, payload: InteractionCreate, user: dict = Depends(current_user)
):
    ensure_permission(user, "pipeline.update")
    opp = await find_one("opportunities", opp_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade nao encontrada")
    ensure_document_access(user, "opportunities", opp)
    inter = await insert_entity(
        "interactions",
        apply_branch_scope(
            {
                "tenant_id": user["tenant_id"],
                "opportunity_id": opp_id,
                "type": payload.type,
                "notes": payload.notes,
            },
            user,
            "interactions",
        ),
        user,
    )
    history = opp.get("history", [])
    history.append({
        "type": "interaction",
        "kind": payload.type,
        "notes": payload.notes,
        "by": user.get("email"),
        "at": utcnow().isoformat(),
    })
    await update_entity("opportunities", opp_id, user["tenant_id"], {"history": history}, user)
    return inter


@router.get("/opportunities/{opp_id}/interactions")
async def list_interactions(opp_id: str, user: dict = Depends(current_user)):
    ensure_permission(user, "pipeline.view")
    opp = await find_one("opportunities", opp_id, user["tenant_id"])
    if not opp:
        raise HTTPException(404, "Oportunidade nao encontrada")
    ensure_document_access(user, "opportunities", opp)
    return await list_entities(
        "interactions",
        user["tenant_id"],
        scoped_query(user, "interactions", {"opportunity_id": opp_id}),
        sort=[("seq_id", -1)],
        limit=200,
    )
