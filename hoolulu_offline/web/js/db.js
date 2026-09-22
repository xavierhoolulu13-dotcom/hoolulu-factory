// Local-first store. IndexedDB is the source of truth — the app must open and
// be fully usable with no network at all. Every write also drops a row into the
// `outbox` so the sync engine knows what to push when you reconnect.

import { uid, now } from './util.js';

const DB_NAME = 'hoolulu_offline';
const DB_VERSION = 1;
const STORE_DOCS = 'docs';
const STORE_OUTBOX = 'outbox';
const STORE_META = 'meta';

export const COLLECTIONS = [
  'conversations', 'messages', 'projects', 'files', 'tasks', 'clients',
  'gigs', 'proposals', 'invoices', 'time_entries', 'products', 'sales',
  'expenses', 'queued_prompts', 'notes',
];

let _db = null;
let _deviceId = null;
const _listeners = new Set();

export function onChange(fn) { _listeners.add(fn); return () => _listeners.delete(fn); }
function emit(collection) { for (const fn of _listeners) { try { fn(collection); } catch (e) { console.error(e); } } }

// ------------------------------------------------------------------ open

export function openDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_DOCS)) {
        const s = db.createObjectStore(STORE_DOCS, { keyPath: 'key' });
        s.createIndex('collection', 'collection', { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_OUTBOX)) {
        const s = db.createObjectStore(STORE_OUTBOX, { keyPath: 'seq', autoIncrement: true });
        s.createIndex('key', 'key', { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_META)) {
        db.createObjectStore(STORE_META, { keyPath: 'k' });
      }
    };
    req.onsuccess = () => { _db = req.result; resolve(_db); };
    req.onerror = () => reject(req.error);
  });
}

function tx(store, mode = 'readonly') {
  return openDB().then(db => db.transaction(store, mode).objectStore(store));
}

function done(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function txDone(t) {
  return new Promise((resolve, reject) => {
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error('transaction aborted'));
  });
}

export const keyOf = (collection, id) => `${collection}|${id}`;

// ------------------------------------------------------------------ meta

export async function deviceId() {
  if (_deviceId) return _deviceId;
  let id = await metaGet('device_id');
  if (!id) {
    id = 'dev-' + uid().slice(0, 8);
    await metaSet('device_id', id);
  }
  _deviceId = id;
  return id;
}

export async function metaGet(k, fallback = null) {
  const s = await tx(STORE_META);
  const row = await done(s.get(k));
  return row ? row.v : fallback;
}

export async function metaSet(k, v) {
  const s = await tx(STORE_META, 'readwrite');
  await done(s.put({ k, v }));
  return v;
}

// Settings live in meta under a single key so they are cheap to read.
const SETTINGS_KEY = 'settings';
export const DEFAULT_SETTINGS = {
  serverUrl: '',
  syncToken: '',
  deviceName: '',
  autoSync: true,
  aiMode: 'auto',            // auto | ondevice | ollama | cloud | local | queue
  preferPrivacy: true,       // on-device first vs cloud first when online
  webllmModel: 'Qwen2.5-Coder-1.5B-Instruct-q4f16_1-MLC',
  ollamaHost: '',            // blank = same origin /api/ollama proxy
  ollamaModel: 'qwen2.5-coder:1.5b',
  cloudProvider: 'openai',   // openai | anthropic | custom
  cloudBaseUrl: 'https://api.openai.com/v1',
  cloudModel: 'gpt-4o-mini',
  cloudKey: '',
  cloudViaProxy: true,
  currency: 'USD',
  hourlyRate: 85,
  taxRate: 0,
  businessName: '',
  ownerName: '',
  paymentTerms: 'Net 14',
};

export async function getSettings() {
  const s = await metaGet(SETTINGS_KEY, {});
  return { ...DEFAULT_SETTINGS, ...(s || {}) };
}

export async function setSettings(patch) {
  const cur = await getSettings();
  const next = { ...cur, ...patch };
  await metaSet(SETTINGS_KEY, next);
  return next;
}

// ------------------------------------------------------------------ reads

function unwrap(row) {
  if (!row) return null;
  return { ...(row.body || {}), id: row.id, updated_at: row.updated_at, deleted: !!row.deleted };
}

export async function get(collection, id) {
  const s = await tx(STORE_DOCS);
  const row = await done(s.get(keyOf(collection, id)));
  const rec = unwrap(row);
  return rec && rec.deleted ? null : rec;
}

export async function all(collection, { includeDeleted = false } = {}) {
  const s = await tx(STORE_DOCS);
  const rows = await done(s.index('collection').getAll(collection));
  return rows
    .map(unwrap)
    .filter(r => r && (includeDeleted || !r.deleted))
    .sort((a, b) => (a.created_at || a.updated_at || 0) - (b.created_at || b.updated_at || 0));
}

export async function where(collection, predicate) {
  const rows = await all(collection);
  return rows.filter(predicate);
}

/** Ordered by most recently updated first. */
export async function recent(collection, limit = 50) {
  const rows = await all(collection);
  return rows.sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0)).slice(0, limit);
}

// ------------------------------------------------------------------ writes

async function writeRaw(collection, obj, { enqueue = true } = {}) {
  const db = await openDB();
  const id = obj.id || uid();
  const ts = obj.updated_at || now();
  const deleted = !!obj.deleted;
  const body = { ...obj };
  delete body.id; delete body.updated_at; delete body.deleted; delete body.key;
  delete body.collection;

  const doc = {
    key: keyOf(collection, id),
    collection, id, body,
    updated_at: ts,
    deleted,
    device_id: await deviceId(),
  };

  const t = db.transaction([STORE_DOCS, STORE_OUTBOX], 'readwrite');
  const docs = t.objectStore(STORE_DOCS);
  docs.put(doc);

  if (enqueue) {
    const out = t.objectStore(STORE_OUTBOX);
    out.put({
      key: doc.key, collection, id,
      body, updated_at: ts, deleted,
      ts: now(),
    });
  }
  await txDone(t);
  emit(collection);
  return { ...body, id, updated_at: ts, deleted };
}

export function put(collection, obj, opts) { return writeRaw(collection, obj, opts); }

export async function putMany(collection, objs, opts) {
  const out = [];
  for (const o of objs) out.push(await writeRaw(collection, o, opts));
  return out;
}

/** Soft delete — replicates as a tombstone so other devices remove it too. */
export async function remove(collection, id) {
  const existing = await get(collection, id);
  return writeRaw(collection, { ...(existing || {}), id, deleted: true });
}

/** Hard delete, local only (used when importing / resetting). */
export async function purge(collection, id) {
  const db = await openDB();
  const t = db.transaction([STORE_DOCS, STORE_OUTBOX], 'readwrite');
  t.objectStore(STORE_DOCS).delete(keyOf(collection, id));
  await txDone(t);
  emit(collection);
}

// ------------------------------------------------------------------ outbox

export async function outboxAll() {
  const s = await tx(STORE_OUTBOX);
  return done(s.getAll());
}

export async function outboxCount() {
  const s = await tx(STORE_OUTBOX);
  return done(s.count());
}

export async function outboxClear(seqs) {
  if (!seqs || !seqs.length) return;
  const db = await openDB();
  const t = db.transaction(STORE_OUTBOX, 'readwrite');
  const s = t.objectStore(STORE_OUTBOX);
  for (const seq of seqs) s.delete(seq);
  await txDone(t);
}

// ------------------------------------------------------------------ remote

/**
 * Apply records that came down from the server. These must NOT re-enter the
 * outbox, and any local pending change that is older gets dropped.
 */
export async function applyRemote(changes) {
  if (!changes || !changes.length) return 0;
  const db = await openDB();
  const t = db.transaction([STORE_DOCS, STORE_OUTBOX], 'readwrite');
  const docs = t.objectStore(STORE_DOCS);
  const out = t.objectStore(STORE_OUTBOX);
  let applied = 0;

  for (const ch of changes) {
    if (!COLLECTIONS.includes(ch.collection)) continue;
    const key = keyOf(ch.collection, ch.id);
    const req = docs.get(key);
    req.onsuccess = () => {
      const local = req.result;
      if (local && !local.deleted && (local.updated_at || 0) > (ch.updated_at || 0)) {
        return; // local is newer (shouldn't normally happen after a push)
      }
      docs.put({
        key,
        collection: ch.collection,
        id: ch.id,
        body: ch.body || {},
        updated_at: ch.updated_at || now(),
        deleted: !!ch.deleted,
        device_id: ch.device_id || 'remote',
      });
      applied++;
      // Drop any pending local push for this same key that is now stale.
      const idx = out.index('key').getAll(key);
      idx.onsuccess = () => {
        for (const row of idx.result || []) {
          if ((row.updated_at || 0) <= (ch.updated_at || 0)) out.delete(row.seq);
        }
      };
    };
  }
  await txDone(t);
  if (applied) emit('*');
  return applied;
}

// ------------------------------------------------------------------ backup

export async function exportAll() {
  const s = await tx(STORE_DOCS);
  const rows = await done(s.getAll());
  const settings = await getSettings();
  const device = await deviceId();
  return {
    format: 'hoolulu-offline-backup',
    version: 1,
    exported_at: new Date().toISOString(),
    device_id: device,
    settings,
    records: rows.map(r => ({
      collection: r.collection, id: r.id, body: r.body,
      updated_at: r.updated_at, deleted: !!r.deleted,
    })),
  };
}

/**
 * mode: 'merge' (newest wins, default) | 'replace' (wipe local first)
 */
export async function importAll(payload, mode = 'merge') {
  if (!payload || !Array.isArray(payload.records)) throw new Error('Not a Hoolulu backup file');
  const db = await openDB();
  const t = db.transaction([STORE_DOCS, STORE_OUTBOX], 'readwrite');
  const docs = t.objectStore(STORE_DOCS);

  if (mode === 'replace') {
    docs.clear();
    t.objectStore(STORE_OUTBOX).clear();
  }

  let count = 0;
  for (const r of payload.records) {
    if (!COLLECTIONS.includes(r.collection)) continue;
    docs.put({
      key: keyOf(r.collection, r.id),
      collection: r.collection, id: r.id,
      body: r.body || {}, updated_at: r.updated_at || now(),
      deleted: !!r.deleted, device_id: 'import',
    });
    count++;
  }
  await txDone(t);

  // A full replace may not contain records the server still has, so rewind
  // the cursor and let the next sync fill the gaps.
  if (mode === 'replace') await metaSet('sync_cursor', 0);

  if (payload.settings) {
    await setSettings({ ...DEFAULT_SETTINGS, ...payload.settings });
  }
  emit('*');
  return count;
}

/** Forget the sync cursor and re-download everything from the server. */
export async function resetCursor() {
  await metaSet('sync_cursor', 0);
  emit('*');
  return 0;
}

/**
 * Clear local data. The sync cursor is reset too, so the next sync can rebuild
 * this device from the server instead of leaving it stranded with nothing.
 */
export async function wipeLocal() {
  const db = await openDB();
  const t = db.transaction([STORE_DOCS, STORE_OUTBOX], 'readwrite');
  t.objectStore(STORE_DOCS).clear();
  t.objectStore(STORE_OUTBOX).clear();
  await txDone(t);
  await metaSet('sync_cursor', 0);
  await metaSet('last_conversation', '');
  emit('*');
}

/** Approximate bytes used, when the browser supports it. */
export async function estimateSize() {
  if (!navigator.storage || !navigator.storage.estimate) return null;
  try {
    const { usage, quota } = await navigator.storage.estimate();
    return { usage, quota };
  } catch { return null; }
}
