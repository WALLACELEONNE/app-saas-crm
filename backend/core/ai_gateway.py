"""LLM gateway with provider abstraction, cache, usage metering, and rate limits."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from core.db import db
from core.models import new_uuid, utcnow


AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-5.2")
AI_TIMEOUT_SEC = float(os.environ.get("AI_TIMEOUT_SEC", "45"))
AI_MAX_INPUT_CHARS = int(os.environ.get("AI_MAX_INPUT_CHARS", "12000"))
AI_MAX_OUTPUT_TOKENS = int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "700"))
AI_CACHE_TTL_SECONDS = int(os.environ.get("AI_CACHE_TTL_SECONDS", "86400"))
AI_USER_PER_MINUTE = int(os.environ.get("AI_USER_PER_MINUTE", "6"))
AI_USER_DAILY_LIMIT = int(os.environ.get("AI_USER_DAILY_LIMIT", "80"))
AI_TENANT_DAILY_LIMIT = int(os.environ.get("AI_TENANT_DAILY_LIMIT", "500"))
AI_MONTHLY_TOKEN_BUDGET = int(os.environ.get("AI_MONTHLY_TOKEN_BUDGET", "2000000"))


def _period_start(kind: str) -> datetime:
    now = datetime.now(timezone.utc)
    if kind == "minute":
        return now - timedelta(minutes=1)
    if kind == "day":
        return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    if kind == "month":
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return now


def _estimate_tokens(text: str) -> int:
    # Conservative enough for budgeting without tokenizer dependency.
    return max(1, len(text) // 4)


def _cache_key(agent: str, model: str, system: str, prompt: str) -> str:
    raw = f"{agent}\n{model}\n{system}\n{prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _extract_text(response: dict[str, Any]) -> str:
    if response.get("output_text"):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _provider_error(resp: httpx.Response) -> tuple[str, Optional[str]]:
    try:
        data = resp.json()
    except ValueError:
        return f"Erro no provedor LLM: HTTP {resp.status_code}", None
    err = data.get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        return f"Erro no provedor LLM: HTTP {resp.status_code}", None
    code = err.get("code") or err.get("type")
    message = err.get("message") or f"HTTP {resp.status_code}"
    if code == "insufficient_quota":
        return "Cota ou billing da OpenAI insuficiente para esta chave/projeto.", code
    if resp.status_code == 429:
        return f"Provedor LLM retornou rate limit: {message[:180]}", code
    return f"Erro no provedor LLM ({code or resp.status_code}): {message[:180]}", code


async def _effective_policy(tenant_id: str) -> dict[str, int]:
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0, "ai_policy": 1})
    policy = (tenant or {}).get("ai_policy") or {}
    return {
        "user_per_minute": int(policy.get("user_per_minute", AI_USER_PER_MINUTE)),
        "user_daily_limit": int(policy.get("user_daily_limit", AI_USER_DAILY_LIMIT)),
        "tenant_daily_limit": int(policy.get("tenant_daily_limit", AI_TENANT_DAILY_LIMIT)),
        "monthly_token_budget": int(policy.get("monthly_token_budget", AI_MONTHLY_TOKEN_BUDGET)),
        "max_input_chars": int(policy.get("max_input_chars", AI_MAX_INPUT_CHARS)),
        "max_output_tokens": int(policy.get("max_output_tokens", AI_MAX_OUTPUT_TOKENS)),
        "cache_ttl_seconds": int(policy.get("cache_ttl_seconds", AI_CACHE_TTL_SECONDS)),
    }


async def _usage_count(query: dict, since: datetime) -> int:
    q = dict(query)
    q["created_at"] = {"$gte": since}
    return await db.ai_usage.count_documents(q)


async def _monthly_tokens(tenant_id: str) -> int:
    total = 0
    async for row in db.ai_usage.aggregate([
        {"$match": {
            "tenant_id": tenant_id,
            "status": {"$ne": "blocked"},
            "created_at": {"$gte": _period_start("month")},
        }},
        {"$group": {"_id": None, "tokens": {"$sum": "$total_tokens"}}},
    ]):
        total = int(row.get("tokens") or 0)
    return total


async def _record_ai_usage(
    *,
    user: dict,
    agent: str,
    provider: str,
    model: str,
    status_text: str,
    usage: dict,
    started: datetime,
    metadata: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    await db.ai_usage.insert_one({
        "id": new_uuid(),
        "tenant_id": user["tenant_id"],
        "branch_id": (user.get("branch_ids") or [None])[0],
        "user_id": user["id"],
        "agent": agent,
        "provider": provider,
        "model": model,
        "status": status_text,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "estimated": usage["estimated"],
        "metadata": metadata or {},
        "error": error,
        "created_at": started,
    })


async def _enforce_limits(user: dict, agent: str, estimated_input_tokens: int, policy: dict) -> None:
    tenant_id = user["tenant_id"]
    user_id = user["id"]
    minute_count = await _usage_count(
        {"tenant_id": tenant_id, "user_id": user_id, "status": {"$ne": "blocked"}},
        _period_start("minute"),
    )
    if minute_count >= policy["user_per_minute"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Limite de IA por minuto atingido")
    user_daily = await _usage_count(
        {"tenant_id": tenant_id, "user_id": user_id, "status": {"$ne": "blocked"}},
        _period_start("day"),
    )
    if user_daily >= policy["user_daily_limit"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Limite diario de IA do usuario atingido")
    tenant_daily = await _usage_count(
        {"tenant_id": tenant_id, "status": {"$ne": "blocked"}},
        _period_start("day"),
    )
    if tenant_daily >= policy["tenant_daily_limit"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Limite diario de IA do tenant atingido")
    projected_tokens = await _monthly_tokens(tenant_id) + estimated_input_tokens + policy["max_output_tokens"]
    if projected_tokens > policy["monthly_token_budget"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Orcamento mensal estimado de IA atingido")


async def generate_text(
    *,
    agent: str,
    system: str,
    prompt: str,
    user: dict,
    cache: bool = True,
    model: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Generate text through the configured provider with cost controls."""
    policy = await _effective_policy(user["tenant_id"])
    if len(prompt) > policy["max_input_chars"]:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Prompt de IA excede o limite configurado")
    model = model or AI_MODEL
    key = _cache_key(agent, model, system, prompt)
    if cache:
        cached = await db.ai_cache.find_one(
            {
                "tenant_id": user["tenant_id"],
                "cache_key": key,
                "expires_at": {"$gt": utcnow()},
            },
            {"_id": 0},
        )
        if cached:
            return {"text": cached["text"], "cached": True, "usage": cached.get("usage", {})}

    input_tokens = _estimate_tokens(system + "\n" + prompt)
    started = utcnow()
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": 0,
        "total_tokens": input_tokens,
        "estimated": True,
    }
    try:
        await _enforce_limits(user, agent, input_tokens, policy)
    except HTTPException as exc:
        await _record_ai_usage(
            user=user,
            agent=agent,
            provider="policy",
            model=model,
            status_text="blocked",
            usage=usage,
            started=started,
            metadata=metadata,
            error=str(exc.detail),
        )
        raise

    provider = AI_PROVIDER
    status_text = "ok"
    text = ""
    error = None

    try:
        if provider == "openai" and OPENAI_API_KEY:
            async with httpx.AsyncClient(timeout=AI_TIMEOUT_SEC) as client:
                resp = await client.post(
                    f"{OPENAI_BASE_URL}/responses",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "instructions": system,
                        "input": prompt,
                        "max_output_tokens": policy["max_output_tokens"],
                        "store": False,
                    },
                )
            if resp.status_code == 429:
                detail, code = _provider_error(resp)
                error = code or detail
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail)
            if resp.status_code >= 400:
                detail, code = _provider_error(resp)
                error = code or detail
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail)
            data = resp.json()
            text = _extract_text(data)
            api_usage = data.get("usage") or {}
            input_used = api_usage.get("input_tokens") or input_tokens
            output_used = api_usage.get("output_tokens") or _estimate_tokens(text)
            usage = {
                "input_tokens": int(input_used),
                "output_tokens": int(output_used),
                "total_tokens": int(api_usage.get("total_tokens") or input_used + output_used),
                "estimated": False,
            }
        else:
            provider = "stub"
            text = "IA em modo seguro: configure OPENAI_API_KEY para ativar respostas LLM reais."
            usage["output_tokens"] = _estimate_tokens(text)
            usage["total_tokens"] += usage["output_tokens"]
    except HTTPException as exc:
        status_text = "blocked"
        error = error or str(exc.detail)
        raise
    except Exception as exc:
        status_text = "error"
        error = f"{exc.__class__.__name__}: {str(exc)[:300]}"
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Falha ao chamar provedor LLM")
    finally:
        await _record_ai_usage(
            user=user,
            agent=agent,
            provider=provider,
            model=model,
            status_text=status_text,
            usage=usage,
            started=started,
            metadata=metadata,
            error=error,
        )

    if cache and text:
        await db.ai_cache.update_one(
            {"tenant_id": user["tenant_id"], "cache_key": key},
            {"$set": {
                "tenant_id": user["tenant_id"],
                "cache_key": key,
                "agent": agent,
                "model": model,
                "text": text,
                "usage": usage,
                "created_at": utcnow(),
                "expires_at": utcnow() + timedelta(seconds=policy["cache_ttl_seconds"]),
            }},
            upsert=True,
        )
    return {"text": text, "cached": False, "usage": usage}


async def usage_summary(user: dict) -> dict:
    policy = await _effective_policy(user["tenant_id"])

    async def aggregate(since: datetime, match_extra: Optional[dict] = None) -> dict:
        match = {"tenant_id": user["tenant_id"], "created_at": {"$gte": since}}
        if match_extra:
            match.update(match_extra)
        row = None
        async for item in db.ai_usage.aggregate([
            {"$match": match},
            {"$group": {
                "_id": None,
                "calls": {"$sum": {"$cond": [{"$ne": ["$status", "blocked"]}, 1, 0]}},
                "tokens": {"$sum": {"$cond": [{"$ne": ["$status", "blocked"]}, "$total_tokens", 0]}},
                "blocked": {"$sum": {"$cond": [{"$eq": ["$status", "blocked"]}, 1, 0]}},
                "errors": {"$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
            }},
        ]):
            row = item
        return {
            "calls": int((row or {}).get("calls") or 0),
            "tokens": int((row or {}).get("tokens") or 0),
            "blocked": int((row or {}).get("blocked") or 0),
            "errors": int((row or {}).get("errors") or 0),
        }

    return {
        "provider": "openai" if OPENAI_API_KEY and AI_PROVIDER == "openai" else "stub",
        "model": AI_MODEL,
        "policy": policy,
        "user_day": await aggregate(_period_start("day"), {"user_id": user["id"]}),
        "tenant_day": await aggregate(_period_start("day")),
        "tenant_month": await aggregate(_period_start("month")),
    }
