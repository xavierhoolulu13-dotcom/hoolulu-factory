/* Service worker: caches the app shell so the whole thing opens with no network.
   Bump CACHE_VERSION to force every client to pick up a new build. */

const CACHE_VERSION = 'hoolulu-v1';
const CORE_CACHE = CACHE_VERSION + '-core';
const RUNTIME_CACHE = CACHE_VERSION + '-runtime';

// Everything needed to boot. The vendored WebLLM runtime is included so you can
// load an on-device model for the first time while offline (the model weights
// themselves are cached by WebLLM's own storage on first download).
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './css/app.css',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/favicon-64.png',
  './js/app.js',
  './js/db.js',
  './js/sync.js',
  './js/util.js',
  './js/ai/local_brain.js',
  './js/ai/skills.js',
  './js/ai/scaffold.js',
  './js/ai/provider.js',
  './js/ai/webllm.js',
  './js/ai/ollama.js',
  './js/ai/cloud.js',
  './js/ai/queue.js',
  './js/ui/chat.js',
  './js/ui/projects.js',
  './js/ui/money.js',
  './js/ui/settings.js',
  './js/ui/sync_view.js',
  './js/ui/modal.js',
];

const OPTIONAL_ASSETS = [
  './vendor/webllm/index.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CORE_CACHE);
    await cache.addAll(CORE_ASSETS);
    // Large and non-essential: never fail the install because of it.
    try {
      const c = await caches.open(RUNTIME_CACHE);
      await Promise.all(OPTIONAL_ASSETS.map(u => c.add(u).catch(() => null)));
    } catch { /* ignore */ }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter(k => k.startsWith('hoolulu-') && k !== CORE_CACHE && k !== RUNTIME_CACHE)
      .map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Never cache API traffic — sync must always hit the real server.
  if (url.pathname.includes('/api/')) {
    event.respondWith(fetch(req));
    return;
  }

  // Cross-origin (model weights, fonts): let WebLLM manage its own cache.
  if (url.origin !== self.location.origin) return;

  // Navigations: try the network so updates appear, fall back to the shell.
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(CORE_CACHE);
        cache.put('./index.html', fresh.clone());
        return fresh;
      } catch {
        const cache = await caches.open(CORE_CACHE);
        return (await cache.match('./index.html')) ||
          (await cache.match('./')) ||
          new Response('Offline and no cached shell. Reload once while online.',
            { status: 503, headers: { 'Content-Type': 'text/plain' } });
      }
    })());
    return;
  }

  // Everything else: cache-first, refresh in the background.
  event.respondWith((async () => {
    const cache = await caches.open(RUNTIME_CACHE);
    const hit = await cache.match(req);
    const network = fetch(req).then((res) => {
      if (res && res.status === 200 && res.type === 'basic') {
        cache.put(req, res.clone()).catch(() => {});
      }
      return res;
    }).catch(() => null);

    if (hit) {
      // Refresh quietly so the next load is current.
      network.then((res) => { if (res) cache.put(req, res.clone()).catch(() => {}); });
      return hit;
    }
    const res = await network;
    if (res) return res;

    const coreCache = await caches.open(CORE_CACHE);
    return (await coreCache.match(req)) || new Response('', { status: 504 });
  })());
});
