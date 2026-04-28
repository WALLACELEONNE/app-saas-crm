"""Atomic sequential ID generator (per collection) — for SEQ_ID rastreável."""
from core.db import db


async def next_seq(name: str) -> int:
    res = await db.counters.find_one_and_update(
        {"name": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return int(res["seq"])
