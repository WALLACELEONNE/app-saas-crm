/**
 * Sync engine — bidirectional pull/push with last-write-wins resolution.
 * Pull: GET deltas since last_sync_at, upsert into SQLite (clears _dirty when server overrides).
 * Push: drain event_queue + dirty rows; resolve conflicts (server_newer → keep server).
 */
import { api } from "../api/client";
import { getDB, SYNCABLE_ENTITIES, upsertEntity, getSyncState, setSyncState } from "./sqlite";
import { listPending, markDelivered, markRetry, queueSize } from "./eventQueue";

const DEVICE_ID_KEY = "device_id";
const LAST_SYNC_KEY = "last_sync_at";

async function deviceId() {
  let id = await getSyncState(DEVICE_ID_KEY);
  if (!id) {
    id = "dev-" + Math.random().toString(36).slice(2, 10);
    await setSyncState(DEVICE_ID_KEY, id);
  }
  return id;
}

export async function pull() {
  const since = await getSyncState(LAST_SYNC_KEY);
  const { data } = await api.post("/sync/pull", { since, entities: SYNCABLE_ENTITIES, limit: 500 });
  let count = 0;
  for (const entity of Object.keys(data.records || {})) {
    if (!SYNCABLE_ENTITIES.includes(entity)) continue;
    for (const row of data.records[entity]) {
      // Don't overwrite local _dirty rows newer than server
      const local = await (await getDB()).getFirstAsync(`SELECT updated_at, _dirty FROM ${entity} WHERE id = ?`, [row.id]);
      if (local?._dirty && local.updated_at && local.updated_at > row.updated_at) continue;
      await upsertEntity(entity, { ...row, _dirty: 0 });
      count++;
    }
  }
  await setSyncState(LAST_SYNC_KEY, data.server_time);
  return { pulled: count, server_time: data.server_time };
}

export async function push() {
  const events = await listPending(50);
  if (!events.length) return { pushed: 0, conflicts: 0 };
  const records = events.map((e) => ({ entity: e.entity, op: e.op, data: JSON.parse(e.data) }));
  const dev = await deviceId();
  try {
    const { data } = await api.post("/sync/push", { device_id: dev, records });
    // accept all
    for (const e of events) {
      await markDelivered(e.id);
    }
    // mark rows as clean if they were dirty
    const db = await getDB();
    for (const r of records) {
      try { await db.runAsync(`UPDATE ${r.entity} SET _dirty = 0 WHERE id = ?`, [r.data.id]); } catch (e) {}
    }
    return { pushed: data.accepted_ids?.length || 0, conflicts: data.conflicts?.length || 0 };
  } catch (err) {
    const msg = err?.response?.data?.detail || err.message || "push error";
    for (const e of events) {
      await markRetry(e.id, e.attempts + 1, msg);
    }
    throw err;
  }
}

export async function syncAll() {
  const pulled = await pull();
  const pushed = await push();
  const pending = await queueSize();
  return { ...pulled, ...pushed, queue: pending };
}
