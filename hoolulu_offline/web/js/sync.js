// Sync engine. Local data is always authoritative for the UI; this module only
// reconciles with the server when one is reachable. When there is no server the
// app keeps working and everything simply accumulates in the outbox.

import * as db from './db.js';
import { now, debounce } from './util.js';

const HEALTH_TIMEOUT = 6000;

const state = {
  online: navigator.onLine,
  syncing: false,
  serverOk: false,
  lastSyncAt: 0,
  lastError: null,
  pending: 0,
  cursor: 0,
  lastPush: 0,
  lastPull: 0,
};

const listeners = new Set();
export function subscribe(fn) { listeners.add(fn); fn(state); return () => listeners.delete(fn); }
function notify() { for (const fn of listeners) { try { fn({ ...state }); } catch (e) { console.error(e); } } }

export const getState = () => ({ ...state });

/** Blank server URL means "the same origin I was served from". */
export function resolveBase(settings) {
  const s = (settings.serverUrl || '').trim().replace(/\/+$/, '');
  return s || '';
}

async function requestJSON(url, body, token, timeoutMs = 20000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'X-Sync-Token': token } : {}),
      },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      cache: 'no-store',
    });
    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch { /* not json */ }
    if (!res.ok) {
      throw new Error((json && json.error) || `HTTP ${res.status}`);
    }
    return json;
  } finally {
    clearTimeout(timer);
  }
}

export async function pingServer(override) {
  const s = override || await db.getSettings();
  const base = resolveBase(s);
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), HEALTH_TIMEOUT);
    const res = await fetch(`${base}/api/health`, {
      cache: 'no-store', signal: ctrl.signal,
    });
    clearTimeout(timer);
    const json = await res.json();
    state.serverOk = !!(json && json.ok);
    state.lastError = state.serverOk ? null : 'server returned an error';
    notify();
    return json;
  } catch (err) {
    state.serverOk = false;
    state.lastError = err.name === 'AbortError' ? 'server timed out' : err.message;
    notify();
    return null;
  }
}

/**
 * Push pending local changes, pull everything new since our cursor.
 * Safe to call any time: without a server it just marks the state and returns.
 */
export async function syncNow({ reason = 'manual', quiet = false } = {}) {
  if (state.syncing) return { ok: false, reason: 'already-syncing' };
  const s = await db.getSettings();
  const base = resolveBase(s);

  state.syncing = true;
  notify();

  try {
    const pending = await db.outboxAll();
    state.pending = pending.length;
    notify();

    // Collapse multiple writes to the same record: only the newest matters.
    const byKey = new Map();
    for (const p of pending) {
      const cur = byKey.get(p.key);
      if (!cur || (p.updated_at || 0) > (cur.updated_at || 0)) byKey.set(p.key, p);
    }
    const changes = [...byKey.values()].map(p => ({
      collection: p.collection, id: p.id, body: p.body,
      updated_at: p.updated_at, deleted: !!p.deleted,
    }));

    const cursor = (await db.metaGet('sync_cursor', 0)) || 0;
    state.cursor = cursor;

    if (!state.online && !changes.length) {
      throw new Error('offline');
    }

    const res = await requestJSON(`${base}/api/sync`, {
      device_id: await db.deviceId(),
      cursor,
      changes,
    }, s.syncToken);

    if (!res || !res.ok) throw new Error((res && res.error) || 'sync failed');

    const appliedRemote = await db.applyRemote(res.changes);
    await db.metaSet('sync_cursor', res.cursor);

    // Only drop the exact outbox rows we sent; anything written while the
    // request was in flight keeps its own row and goes out next time.
    await db.outboxClear(pending.map(p => p.seq));

    state.serverOk = true;
    state.lastSyncAt = now();
    state.lastError = null;
    state.lastPush = changes.length;
    state.lastPull = appliedRemote;
    state.cursor = res.cursor;
    state.pending = await db.outboxCount();
    notify();

    // Server may have capped the batch; loop until fully caught up.
    if (res.more) {
      setTimeout(() => syncNow({ reason: 'continue', quiet: true }), 10);
    }
    return { ok: true, pushed: changes.length, pulled: appliedRemote, reason };
  } catch (err) {
    state.lastError = err.name === 'AbortError' ? 'server timed out' : err.message;
    state.serverOk = false;
    state.pending = await db.outboxCount();
    notify();
    if (!quiet) console.warn('[sync]', state.lastError);
    return { ok: false, error: state.lastError };
  } finally {
    state.syncing = false;
    notify();
  }
}

const autoPush = debounce(() => {
  const st = getState();
  if (st.online && !st.syncing) syncNow({ reason: 'auto', quiet: true });
}, 3500);

let timer = null;

export async function initSync() {
  const s = await db.getSettings();
  state.cursor = (await db.metaGet('sync_cursor', 0)) || 0;
  state.pending = await db.outboxCount();
  state.lastSyncAt = (await db.metaGet('sync_last_at', 0)) || 0;
  notify();

  window.addEventListener('online', () => {
    state.online = true; notify();
    if (s.autoSync) setTimeout(() => syncNow({ reason: 'back-online', quiet: true }), 400);
  });
  window.addEventListener('offline', () => { state.online = false; notify(); });

  db.onChange(() => {
    db.outboxCount().then(n => { state.pending = n; notify(); });
    autoPush();
  });

  // Persist lastSyncAt so it survives a reload.
  subscribe(st => { if (st.lastSyncAt) db.metaSet('sync_last_at', st.lastSyncAt); });

  timer = setInterval(async () => {
    if (!state.online || state.syncing) return;
    const cur = await db.getSettings();
    if (!cur.autoSync) return;
    const pending = await db.outboxCount();
    const stale = Date.now() - state.lastSyncAt > 60000;
    if (pending > 0 || stale) syncNow({ reason: 'interval', quiet: true });
  }, 20000);

  // Fire-and-forget first attempt; a missing server is expected, not an error.
  pingServer(s).then(h => { if (h && s.autoSync) syncNow({ reason: 'startup', quiet: true }); });
  return state;
}

export function stopSync() { if (timer) clearInterval(timer); }
