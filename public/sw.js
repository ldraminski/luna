// Service worker Luny (wewn. oboe) — wzorowany na Alertach.
// Pushe przychodzą BEZ treści (n8n nie ma w sandboksie modułu crypto, więc nie szyfruje payloadu),
// po „szturchańcu” pobieramy treść z /api/pending tokenem z IndexedDB.
// iOS wymaga, żeby KAŻDY push skończył się widocznym powiadomieniem — inaczej Apple cofa subskrypcję.

const SHELL = 'oboe-shell-v10';
const SHELL_FILES = ['/', '/index.html', '/app.css', '/app.js', '/api.js', '/manifest.webmanifest', '/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Sieć najpierw, cache jako zapas (offline). API nigdy z cache.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(event.request, copy)); }
    return res;
  }).catch(() => caches.match(event.request).then((r) => r || caches.match('/'))));
});

function kvGet(k) {
  return new Promise((res) => {
    const req = indexedDB.open('oboe', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('kv');
    req.onerror = () => res(null);
    req.onsuccess = () => {
      try {
        const g = req.result.transaction('kv').objectStore('kv').get(k);
        g.onsuccess = () => res(g.result ?? null); g.onerror = () => res(null);
      } catch { res(null); }
    };
  });
}

async function handlePush() {
  let items = [];
  try {
    const token = await kvGet('token');
    const r = await fetch('/api/pending', { headers: { Authorization: 'Bearer ' + (token || '') }, cache: 'no-store' });
    if (r.ok) items = (await r.json()).items || [];
  } catch {}
  if (!items.length) {
    return self.registration.showNotification('Luna', { body: 'Mam dla ciebie przypomnienie — zajrzyj.', icon: '/icons/icon-192.png', tag: 'oboe-fallback', data: {} });
  }
  const shown = items.slice(0, 3);
  await Promise.all(shown.map((n) => self.registration.showNotification(n.title, {
    body: n.body || '', icon: '/icons/icon-192.png', tag: 'oboe-' + n.id, data: { item: n.item_id },
  })));
  if (items.length > 3) {
    await self.registration.showNotification('Luna', { body: `…i jeszcze ${items.length - 3}`, tag: 'oboe-more', icon: '/icons/icon-192.png', data: {} });
  }
}
self.addEventListener('push', (event) => event.waitUntil(handlePush()));

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const id = event.notification.data?.item || null;
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const own = wins.find((w) => new URL(w.url).origin === location.origin);
    if (own) { await own.focus(); own.postMessage({ type: 'open', id }); return; }
    return self.clients.openWindow(id ? '/?open=' + id : '/');
  })());
});
