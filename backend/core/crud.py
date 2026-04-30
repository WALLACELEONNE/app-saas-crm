"""Generic CRUD helpers used by simple modules."""
from typing import Optional, Type
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from core.auth import current_user
from core.repo import (
    insert_entity,
    update_entity,
    soft_delete,
    find_one,
    list_entities,
    count_entities,
)
from core.permissions import (
    apply_branch_scope,
    ensure_branch_access,
    ensure_collection_permission,
    ensure_document_access,
    scoped_query,
)


def make_crud_router(
    collection: str,
    create_model: Type[BaseModel],
    update_model: Type[BaseModel],
    search_fields: Optional[list[str]] = None,
    extra_filters: Optional[list[str]] = None,
) -> APIRouter:
    r = APIRouter()
    extra_filters = extra_filters or []
    search_fields = search_fields or []

    @r.get("")
    async def list_all(
        skip: int = 0,
        limit: int = Query(100, le=500),
        q: Optional[str] = None,
        user: dict = Depends(current_user),
    ):
        ensure_collection_permission(user, collection, "view")
        query: dict = {}
        if q and search_fields:
            query["$or"] = [{f: {"$regex": q, "$options": "i"}} for f in search_fields]
        query = scoped_query(user, collection, query)
        items = await list_entities(
            collection, user["tenant_id"], query, skip, limit, sort=[("seq_id", -1)]
        )
        total = await count_entities(collection, user["tenant_id"], query)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    @r.post("", status_code=201)
    async def create(payload: create_model, user: dict = Depends(current_user)):
        ensure_collection_permission(user, collection, "create")
        data = payload.model_dump(exclude_unset=False)
        data["tenant_id"] = user["tenant_id"]
        data = apply_branch_scope(data, user, collection)
        return await insert_entity(collection, data, user=user)

    @r.get("/{entity_id}")
    async def get(entity_id: str, user: dict = Depends(current_user)):
        ensure_collection_permission(user, collection, "view")
        doc = await find_one(collection, entity_id, user["tenant_id"])
        if not doc:
            raise HTTPException(404, "Nao encontrado")
        ensure_document_access(user, collection, doc)
        return doc

    @r.patch("/{entity_id}")
    async def update(entity_id: str, payload: update_model, user: dict = Depends(current_user)):
        ensure_collection_permission(user, collection, "update")
        patch = payload.model_dump(exclude_unset=True)
        if "branch_id" in patch:
            ensure_branch_access(user, patch.get("branch_id"))
        doc = await update_entity(collection, entity_id, user["tenant_id"], patch, user)
        if not doc:
            raise HTTPException(404, "Nao encontrado")
        ensure_document_access(user, collection, doc)
        return doc

    @r.delete("/{entity_id}")
    async def delete(entity_id: str, user: dict = Depends(current_user)):
        ensure_collection_permission(user, collection, "delete")
        doc = await find_one(collection, entity_id, user["tenant_id"])
        if not doc:
            raise HTTPException(404, "Nao encontrado")
        ensure_document_access(user, collection, doc)
        ok = await soft_delete(collection, entity_id, user["tenant_id"], user)
        if not ok:
            raise HTTPException(404, "Nao encontrado")
        return {"deleted": True}

    return r
