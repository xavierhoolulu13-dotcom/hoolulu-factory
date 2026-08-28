// App shell: boots the local database, wires navigation, tracks which brain is
// answering, and registers the service worker that makes it all work offline.

import * as db from './db.js';
import * as sync from './sync.js';
import * as provider from './ai/provider.js';
import * as queue from './ai/queue.js';
import { $, $$, el, toast } from './util.js';

import * as chatView from './ui/chat.js';
import * as projectsView from './ui/projects.js';
import * as moneyView from './ui/money.js';
import * as syncView from './ui/sync_view.js';
import * as settingsView from './ui/settings.js';

export const state = {
  ready: false,
  settings: null,
  providers: null,
  view: 'chat',
};

const VIEWS = {
  chat: { title: 'Chat', render: chatView.render },
  projects: { title: 'Projects', render: projectsView.render },
  money: { title: 'Money', render: moneyView.render },
  sync: { title: 'Sync', render: syncView.render },
  settings: { title: 'Settings', render: settingsView.render },
};

const listeners = new Set();
export function onAppEvent(fn) { listeners.add(fn); return () => listeners.delete(fn); }
function emit(type, detail) { for (const fn of listeners) { try { fn(type, detail); } catch (e) { console.error(e); } } }

export function serverBase() {
  return sync.resolveBase(state.settings || {});
}

export async function refreshProviders() {
  state.providers = await provider.detect({
    settings: state.settings,
    online: navigator.onLine,
    serverBase: serverBase(),
  });
  updateEnginePill();
  emit('providers', state.providers);
  return state.providers;
}

function updateEnginePill() {
  const p = state.providers;
  const pill = $('#engine-pill');
  const text = $('#engine-text');
  if (!pill || !p || !state.settings) return;

  const decision = provider.choose(state.settings, p);
  pill.className = 'engine-pill ' + decision.engine;
  text.textContent = provider.engineLabel(decision.engine).toLowerCase();
  pill.title = `Answering with: ${decision.reason}`;
}

// ------------------------------------------------------------------ routing

export function navigate(view) {
  if (!VIEWS[view]) view = 'chat';
  state.view = view;
  location.hash = '#/' + view;
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $('#view-title').textContent = VIEWS[view].title;
  const root = $('#view');
  root.innerHTML = '';
  const inner = el('div', { class: 'view-inner' });
  root.appendChild(inner);
  Promise.resolve(VIEWS[view].render(inner)).catch(err => {
    console.error(err);
    inner.appendChild(el('div', { class: 'empty' }, [
      el('h3', { text: 'Something broke in this view' }),
      el('p', { class: 'mono small', text: String(err.message || err) }),
    ]));
  });
}

export function rerender() {
  if (state.view) navigate(state.view);
}

// ------------------------------------------------------------------- chrome

function wireShell() {
  $$('#nav .nav-btn').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.view));
  });

  window.addEventListener('hashchange', () => {
    const v = (location.hash || '').replace('#/', '');
    if (VIEWS[v] && v !== state.view) navigate(v);
  });

  $('#pill-syncnow').addEventListener('click', async () => {
    const btn = $('#pill-syncnow');
    btn.disabled = true; btn.textContent = 'Syncing…';
    const res = await sync.syncNow();
    btn.disabled = false; btn.textContent = 'Sync';
    if (res.ok) toast(`Synced — sent ${res.pushed}, received ${res.pulled}`, 'ok');
    else toast('Sync failed: ' + (res.error || 'unknown'), 'err');
    rerender();
  });

  window.addEventListener('online', () => {
    refreshProviders();
    runQueue();
  });
  window.addEventListener('offline', () => refreshProviders());

  setInterval(() => refreshProviders(), 60000);
}

async function runQueue() {
  if (!state.settings || !state.providers) return;
  const n = await queue.runDue({
    settings: state.settings,
    status: state.providers,
    serverBase: serverBase(),
    onResult: () => {
      if (state.view === 'chat') rerender();
    },
  });
  if (n > 0) toast(`${n} queued prompt${n === 1 ? '' : 's'} answered`, 'ok');
}

function updateNetPill(st) {
  const pill = $('#pill-net');
  const label = pill.querySelector('span:last-child');
  pill.classList.toggle('online', !!st.online);
  label.textContent = st.online ? 'online' : 'offline';
  $('#offline-banner').hidden = !!st.online;
}

// ------------------------------------------------------------ install + SW

let deferredPrompt = null;
function wireInstall() {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const btn = $('#install-btn');
    btn.hidden = false;
    btn.onclick = async () => {
      btn.hidden = true;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') toast('Installed — it now works with no network', 'ok');
      deferredPrompt = null;
    };
  });
  window.addEventListener('appinstalled', () => { $('#install-btn').hidden = true; });
}

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.register('sw.js', { scope: './' });
    reg.addEventListener('updatefound', () => {
      const sw = reg.installing;
      if (!sw) return;
      sw.addEventListener('statechange', () => {
        if (sw.state === 'installed' && navigator.serviceWorker.controller) {
          toast('New version ready — reload to update', 'info', 6000);
        }
      });
    });
  } catch (err) {
    console.warn('[sw] registration failed', err);
  }
}

// --------------------------------------------------------------------- boot

async function boot() {
  await db.openDB();
  state.settings = await db.getSettings();

  wireShell();
  wireInstall();
  registerServiceWorker();

  await sync.initSync();
  sync.subscribe(st => {
    updateNetPill(st);
    const c = $('#sync-count');
    if (c) c.textContent = st.pending;
    const sp = $('#pill-sync');
    if (sp) {
      sp.classList.toggle('online', st.serverOk);
      sp.title = st.serverOk ? 'Connected to sync server' : (st.lastError || 'no server');
    }
  });

  await refreshProviders();
  await queue.prune();

  state.ready = true;
  const initial = (location.hash || '').replace('#/', '');
  navigate(VIEWS[initial] ? initial : 'chat');

  // If a real engine is available right now, clear anything queued earlier.
  runQueue();

  // Keep the engine pill honest when settings change.
  onAppEvent((type) => { if (type === 'settings') { refreshProviders(); } });
}

export async function saveSettings(patch) {
  state.settings = await db.setSettings(patch);
  await refreshProviders();
  emit('settings', state.settings);
  return state.settings;
}

boot().catch(err => {
  console.error(err);
  document.body.appendChild(el('div', { class: 'empty', style: { margin: '40px' } }, [
    el('h3', { text: 'Could not start' }),
    el('p', { class: 'mono small', text: String(err.message || err) }),
  ]));
});

window.hoolulu = { state, db, sync, provider, queue, navigate, rerender, refreshProviders };
