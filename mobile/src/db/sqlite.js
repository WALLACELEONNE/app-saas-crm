/**
 * SQLite schema mirroring server entities + local-only tables (event_queue, sync_state).
 */
import * as SQLite from "expo-sqlite";

export const DB_NAME = "agrocrm.db";

let _db = null;
export async function getDB() {
  if (_db) return _db;
  _db = await SQLite.openDatabaseAsync(DB_NAME);
  await migrate(_db);
  return _db;
}

const TABLES = {
  clients: `
    CREATE TABLE IF NOT EXISTS clients (
      id TEXT PRIMARY KEY,
      seq_id INTEGER,
      tenant_id TEXT,
      type TEXT,
      name TEXT,
      doc TEXT,
      region TEXT,
      culture TEXT,
      classification TEXT,
      potential TEXT,
      area_ha REAL,
      contacts TEXT,
      notes TEXT,
      created_at TEXT,
      updated_at TEXT,
      deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  products: `
    CREATE TABLE IF NOT EXISTS products (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      category TEXT, name TEXT, sku TEXT, unit TEXT,
      current_price REAL, currency TEXT, notes TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  contracts: `
    CREATE TABLE IF NOT EXISTS contracts (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      type TEXT, client_id TEXT, client_name TEXT,
      product_id TEXT, product_name TEXT,
      volume REAL, unit TEXT, price REAL, currency TEXT,
      signed_at TEXT, delivery_window TEXT,
      status TEXT, notes TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  orders: `
    CREATE TABLE IF NOT EXISTS orders (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      type TEXT, contract_id TEXT, client_id TEXT, client_name TEXT,
      items TEXT, total REAL, currency TEXT,
      status TEXT, logistic_status TEXT, notes TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  opportunities: `
    CREATE TABLE IF NOT EXISTS opportunities (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      client_id TEXT, client_name TEXT,
      stage_id TEXT, stage_name TEXT,
      title TEXT, product_id TEXT, product_name TEXT,
      volume REAL, unit TEXT, value REAL, currency TEXT,
      probability INTEGER, expected_close TEXT, notes TEXT,
      history TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  pipeline_stages: `
    CREATE TABLE IF NOT EXISTS pipeline_stages (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      name TEXT, "order" INTEGER, color TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  tickets: `
    CREATE TABLE IF NOT EXISTS tickets (
      id TEXT PRIMARY KEY, seq_id INTEGER, tenant_id TEXT,
      client_id TEXT, client_name TEXT, subject TEXT, description TEXT,
      priority TEXT, sla_hours INTEGER, status TEXT, assigned_to TEXT,
      comments TEXT,
      created_at TEXT, updated_at TEXT, deleted_at TEXT,
      _dirty INTEGER DEFAULT 0
    );`,
  // Local-only operational tables
  event_queue: `
    CREATE TABLE IF NOT EXISTS event_queue (
      id TEXT PRIMARY KEY,
      entity TEXT NOT NULL,
      op TEXT NOT NULL,
      data TEXT NOT NULL,
      attempts INTEGER DEFAULT 0,
      last_error TEXT,
      created_at TEXT NOT NULL,
      next_attempt_at TEXT NOT NULL
    );`,
  sync_state: `
    CREATE TABLE IF NOT EXISTS sync_state (
      key TEXT PRIMARY KEY,
      value TEXT
    );`,
};

export const SYNCABLE_ENTITIES = [
  "clients", "products", "contracts", "orders",
  "opportunities", "pipeline_stages", "tickets",
];

async function migrate(db) {
  for (const ddl of Object.values(TABLES)) {
    await db.execAsync(ddl);
  }
  await db.execAsync(`CREATE INDEX IF NOT EXISTS idx_clients_dirty ON clients(_dirty);`);
  await db.execAsync(`CREATE INDEX IF NOT EXISTS idx_orders_dirty ON orders(_dirty);`);
  await db.execAsync(`CREATE INDEX IF NOT EXISTS idx_contracts_dirty ON contracts(_dirty);`);
}

/**
 * Generic upsert helper. Encodes JSON columns automatically based on schema.
 */
const JSON_COLS = {
  clients: ["culture", "contacts"],
  orders: ["items"],
  opportunities: ["history"],
  tickets: ["comments"],
};

export async function upsertEntity(entity, row) {
  const db = await getDB();
  const data = { ...row };
  // serialize JSON
  for (const col of JSON_COLS[entity] || []) {
    if (data[col] !== undefined && typeof data[col] !== "string") {
      data[col] = JSON.stringify(data[col]);
    }
  }
  const cols = Object.keys(data).filter((k) => !k.startsWith("_") && k !== "tenant_id" || k === "tenant_id");
  const placeholders = cols.map(() => "?").join(",");
  const values = cols.map((k) => (data[k] === undefined ? null : data[k]));
  const setClause = cols.map((k) => `"${k}"=excluded."${k}"`).join(",");
  const sql = `INSERT INTO ${entity} (${cols.map((c) => `"${c}"`).join(",")}) VALUES (${placeholders})
               ON CONFLICT(id) DO UPDATE SET ${setClause}`;
  await db.runAsync(sql, values);
}

export async function listEntity(entity, where = "deleted_at IS NULL", params = []) {
  const db = await getDB();
  const rows = await db.getAllAsync(`SELECT * FROM ${entity} WHERE ${where} ORDER BY seq_id DESC LIMIT 200`, params);
  for (const r of rows) {
    for (const col of JSON_COLS[entity] || []) {
      if (typeof r[col] === "string") {
        try { r[col] = JSON.parse(r[col]); } catch (e) { /* keep as string */ }
      }
    }
  }
  return rows;
}

export async function getEntity(entity, id) {
  const db = await getDB();
  const r = await db.getFirstAsync(`SELECT * FROM ${entity} WHERE id = ?`, [id]);
  if (r) {
    for (const col of JSON_COLS[entity] || []) {
      if (typeof r[col] === "string") {
        try { r[col] = JSON.parse(r[col]); } catch (e) {}
      }
    }
  }
  return r;
}

export async function markDirty(entity, id) {
  const db = await getDB();
  await db.runAsync(`UPDATE ${entity} SET _dirty = 1, updated_at = ? WHERE id = ?`, [new Date().toISOString(), id]);
}

export async function getSyncState(key, fallback = null) {
  const db = await getDB();
  const r = await db.getFirstAsync(`SELECT value FROM sync_state WHERE key = ?`, [key]);
  return r ? r.value : fallback;
}

export async function setSyncState(key, value) {
  const db = await getDB();
  await db.runAsync(`INSERT INTO sync_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value`, [key, value]);
}
