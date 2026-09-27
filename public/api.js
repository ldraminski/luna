// Oboe — warstwa danych: token, wywołania /api/*, Web Push.
// Token trzymamy w localStorage (aplikacja) ORAZ w IndexedDB (service worker nie ma localStorage,
// a po pushu musi pobrać treść z /api/pending).

// Ten sam klucz VAPID co w Alertach — n8n podpisuje nim oba systemy (credential „Alerty VAPID”).
export const VAPID_PUBLIC_KEY = 'BCsLF3E2-p-L9Cpw_smlVGOtpdBEXgDJKEyexxG28crg4SiZkqoFbAuJAlEKOS5YyMVpdw_ISLaWMtbBTqwpYA4';

function kv() {
  return new Promise((res, rej) => {
    const req = indexedDB.open('oboe', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('kv');
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}
async function kvSet(k, v) {
  try {
    const db = await kv();
    await new Promise((res, rej) => {
      const tx = db.transaction('kv', 'readwrite');
      v == null ? tx.objectStore('kv').delete(k) : tx.objectStore('kv').put(v, k);
      tx.oncomplete = res; tx.onerror = () => rej(tx.error);
    });
  } catch { /* bez IndexedDB push nie pobierze treści, ale aplikacja działa */ }
}

export function getToken() {
  try { return localStorage.getItem('oboe-token') || ''; } catch { return ''; }
}
export async function setToken(t) {
  try { t ? localStorage.setItem('oboe-token', t) : localStorage.removeItem('oboe-token'); } catch {}
  await kvSet('token', t || null);
}

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function call(path, { method = 'GET', body, token = getToken() } = {}) {
  let res;
  try {
    res = await fetch('/api/' + path, {
      method,
      headers: { Authorization: 'Bearer ' + token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      cache: 'no-store',
    });
  } catch {
    throw new ApiError(0, 'Brak połączenia. Sprawdź internet.');
  }
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new ApiError(res.status, data.error || 'Coś poszło nie tak (' + res.status + ').');
  return data;
}

export const api = {
  me: (token) => call('me', { token }),
  items: () => call('items').then((d) => d.items || []),
  add: (text) => call('items', { method: 'POST', body: { text } }),
  done: (id) => call('items/done', { method: 'POST', body: { id } }),
  remove: (id) => call('items/delete', { method: 'POST', body: { id } }),
  check: (id, index, done) => call('items/check', { method: 'POST', body: { id, index, done } }),
  summarize: (id) => call('items/summarize', { method: 'POST', body: { id } }),
  widgetChat: (id, message = '') => call('items/widget-chat', { method: 'POST', body: { id, message } }),
  widgetChatClose: (id) => call('items/widget-chat/close', { method: 'POST', body: { id } }),
  widgetRegenerate: (id) => call('items/widget-regenerate', { method: 'POST', body: { id } }),
  widgetState: (id, state) => call('items/widget-state', { method: 'POST', body: { id, state } }),
};

// ---------- Web Push ----------
export const push = {
  supported: () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
  permission: () => ('Notification' in window ? Notification.permission : 'unsupported'),
  async current() {
    if (!this.supported()) return null;
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  },
  // Musi być wołane bezpośrednio z kliknięcia (iOS inaczej odmawia).
  async enable() {
    if (!this.supported()) throw new Error('Ta przeglądarka nie obsługuje powiadomień.');
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') throw new Error('Powiadomienia zablokowane. Włącz je w ustawieniach telefonu.');
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64urlToBytes(VAPID_PUBLIC_KEY) });
    const j = sub.toJSON();
    await call('push/subscribe', { method: 'POST', body: { endpoint: j.endpoint, keys: j.keys, ua: navigator.userAgent } });
    return sub;
  },
  // Odświeża zapis na serwerze (endpoint potrafi się zmienić), bez pytania o zgodę.
  async resync() {
    const sub = await this.current();
    if (!sub) return false;
    const j = sub.toJSON();
    await call('push/subscribe', { method: 'POST', body: { endpoint: j.endpoint, keys: j.keys, ua: navigator.userAgent } }).catch(() => {});
    return true;
  },
};

function b64urlToBytes(s) {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const bin = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
