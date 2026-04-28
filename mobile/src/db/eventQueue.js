/**
 * Local event queue — every offline mutation enqueues an event.
 * Sync engine drains the queue when connectivity is up.
 */
import { getDB } from "./sqlite";

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export async function enqueueEvent(entity, op, data) {
  const db = await getDB();
  const id = uuid();
  await db.runAsync(
    `INSERT INTO event_queue(id, entity, op, data, attempts, created_at, next_attempt_at)
     VALUES(?, ?, ?, ?, 0, ?, ?)`,
    [id, entity, op, JSON.stringify(data), new Date().toISOString(), new Date().toISOString()],
  );
  return id;
}

export async function listPending(limit = 50) {
  const db = await getDB();
  const now = new Date().toISOString();
  return db.getAllAsync(
    `SELECT * FROM event_queue WHERE next_attempt_at <= ? ORDER BY created_at ASC LIMIT ?`,
    [now, limit],
  );
}

export async function markDelivered(id) {
  const db = await getDB();
  await db.runAsync(`DELETE FROM event_queue WHERE id = ?`, [id]);
}

export async function markRetry(id, attempts, error) {
  const db = await getDB();
  // exponential backoff: 5s, 15s, 45s, 2min, 6min
  const delay = 5 * Math.pow(3, Math.min(attempts, 5));
  const next = new Date(Date.now() + delay * 1000).toISOString();
  await db.runAsync(
    `UPDATE event_queue SET attempts = ?, last_error = ?, next_attempt_at = ? WHERE id = ?`,
    [attempts, error, next, id],
  );
}

export async function queueSize() {
  const db = await getDB();
  const r = await db.getFirstAsync(`SELECT COUNT(*) as n FROM event_queue`);
  return r?.n || 0;
}
