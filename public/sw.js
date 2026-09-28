// Service worker Luny (wewn. oboe) — wzorowany na Alertach.
// Pushe przychodzą BEZ treści (n8n nie ma w sandboksie modułu crypto, więc nie szyfruje payloadu),
// po „szturchańcu” pobieramy treść z /api/pending tokenem z IndexedDB.
// iOS wymaga, żeby KAŻDY push skończył się widocznym powiadomieniem — inaczej Apple cofa subskrypcję.

const SHELL = 'oboe-shell-__V__';   // __V__ = skrót treści plików, podmieniany przy budowie obrazu (Dockerfile)
const SHELL_FILES = ['/', '/index.html', '/app.css?v=__V__', '/app.js?v=__V__', '/api.js?v=__V__', '/manifest.webmanifest', '/icons/icon-192.png',
  '/fonts/lexend.css', '/fonts/lexend-latin.woff2', '/fonts/lexend-latin-ext.woff2'];

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
  // Cloudflare dokleja max-age=14400 do CSS/JS — cache: 'no-cache' wymusza sprawdzenie u serwera (ETag), żeby telefon nie wziął starej wersji.
  const net = event.request.mode === 'navigate' ? fetch(event.request) : fetch(event.request, { cache: 'no-cache' });
  const fromCache = () => caches.match(event.request).then((r) => r || (event.request.mode === 'navigate' ? caches.match('/') : undefined));
  const saved = net.then((res) => {
    if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(event.request, copy)); }
    return res;
  });
  // Serwer nie odpowiada (nie „brak sieci”, tylko wiszące połączenie) → po 4 s bierzemy wersję z pamięci, zamiast białego ekranu.
  const timeout = new Promise((res) => setTimeout(res, 4000)).then(fromCache);
  event.respondWith(Promise.race([saved.catch(fromCache), timeout.then((r) => r || saved)]).then((r) => r || saved).catch(fromCache));
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
  await Promise.all(shown.map((n) => self.registration.showNotification(n.title, n.kind === 'alarm'
    // alarm: jedno powiadomienie na rzecz, podmieniane co 20 s i dzwoniące od nowa; przyciski działają tam, gdzie system je pokazuje (Android)
    ? { body: n.body || '', icon: '/icons/icon-192.png', tag: 'oboe-alarm-' + n.item_id, renotify: true, requireInteraction: true,
        actions: [{ action: 'snooze', title: 'Przełóż o 5 min' }, { action: 'off', title: 'Wyłącz' }], data: { item: n.item_id, alarm: true } }
    : { body: n.body || '', icon: '/icons/icon-192.png', tag: 'oboe-' + n.id, data: { item: n.item_id } })));
  if (items.length > 3) {
    await self.registration.showNotification('Luna', { body: `…i jeszcze ${items.length - 3} ${items.length - 3 === 1 ? 'przypomnienie' : (items.length - 3) % 10 >= 2 && (items.length - 3) % 10 <= 4 && ((items.length - 3) % 100 < 10 || (items.length - 3) % 100 >= 20) ? 'przypomnienia' : 'przypomnień'}`, tag: 'oboe-more', icon: '/icons/icon-192.png', data: {} });
  }
}
self.addEventListener('push', (event) => event.waitUntil(handlePush()));

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const id = event.notification.data?.item || null;
  if (id && (event.action === 'snooze' || event.action === 'off')) {
    event.waitUntil(kvGet('token').then((token) => fetch('/api/items/alarm', { method: 'POST',
      headers: { Authorization: 'Bearer ' + (token || ''), 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action: event.action }) })).catch(() => {}));
    return;
  }
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const own = wins.find((w) => new URL(w.url).origin === location.origin);
    if (own) { await own.focus(); own.postMessage({ type: 'open', id }); return; }
    return self.clients.openWindow(id ? '/?open=' + id : '/');
  })());
});
