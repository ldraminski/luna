// Oboe — aplikacja. Wygląd i anatomia kart 1:1 z makiety A (Sekkei); tu tylko dane i zachowanie.
import { api, push, getToken, setToken, ApiError } from './api.js';

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const STANDALONE = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;

const state = { user: null, items: [], openId: null };

// ---------- daty ----------
const DAY = 864e5;
const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const dayDiff = (d) => Math.round((startOfDay(d) - startOfDay(new Date())) / DAY);
const fDay = new Intl.DateTimeFormat('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
const fShort = new Intl.DateTimeFormat('pl-PL', { weekday: 'short', day: 'numeric', month: 'short' });
const fTime = new Intl.DateTimeFormat('pl-PL', { hour: '2-digit', minute: '2-digit' });
const fWd = new Intl.DateTimeFormat('pl-PL', { weekday: 'short' });

function rel(d) {
  const n = dayDiff(d);
  if (n === 0) return 'dziś';
  if (n === 1) return 'jutro';
  if (n === 2) return 'pojutrze';
  if (n === -1) return 'wczoraj';
  if (n < 0) return `${-n} dni temu`;
  return `za ${n} dni`;
}
const when = (d) => `${fShort.format(d)}, ${fTime.format(d)}`;
const whenRel = (d) => { const n = dayDiff(d); return (n >= 0 && n <= 1 ? rel(d) : fShort.format(d)) + ' ' + fTime.format(d); };
const dt = (s) => (s ? new Date(s) : null);

// ---------- ikony (z makiety) ----------
const I = {
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  cycle: '<path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"/><path d="m9.5 4.5 2.5 2 2.5-2M9.5 19.5l2.5-2 2.5 2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.8 3 2.8 15 0 18M12 3c-2.8 3-2.8 15 0 18"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/>',
  note: '<path d="M5 4h14v16H5z"/><path d="M9 9h6M9 13h6M9 17h3"/>',
  back: '<path d="m15 5-7 7 7 7"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  ext: '<path d="M7 17 17 7M9 7h8v8"/>',
  bank: '<path d="M8 24 32 10l24 14z" fill="#fff"/><path d="M12 26v22M22 26v22M32 26v22M42 26v22M52 26v22"/><path d="M7 50h50M5 55h54"/><circle cx="32" cy="19" r="2.5" fill="currentColor"/>',
};
const svg = (k, style = '') => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true"${style ? ` style="${style}"` : ''}>${I[k]}</svg>`;

// ---------- ekran powitalny (klucz) ----------
function showHello(msg = '') {
  $('#screen-main').hidden = true; $('#dock').hidden = true;
  $('#screen-hello').hidden = false;
  $('#ios-note').hidden = !(IOS && !STANDALONE);
  $('#tok-err').textContent = msg;
}

async function submitToken(e) {
  e?.preventDefault();
  const raw = $('#tok').value.trim();
  const t = (raw.match(/[a-f0-9]{64}/i) || [raw])[0];   // mail potrafi dokleić spacje albo tekst dookoła
  if (!/^[a-f0-9]{64}$/i.test(t)) { $('#tok-err').textContent = 'To nie wygląda na klucz — skopiuj cały ciąg z maila.'; return; }
  $('#tok-err').textContent = '';
  try {
    const me = await api.me(t);
    await setToken(t);
    state.user = me.user;
    startMain();
  } catch (err) {
    $('#tok-err').textContent = err.status === 401 ? 'Ten klucz nie działa. Poproś Łukasza o nowy.' : err.message;
  }
}

// ---------- ekran główny ----------
function startMain() {
  $('#screen-hello').hidden = true;
  $('#screen-main').hidden = false; $('#dock').hidden = false;
  const h = new Date().getHours();
  const hi = h < 5 ? 'Dobry wieczór' : h < 18 ? 'Dzień dobry' : 'Dobry wieczór';
  $('#hello-name').innerHTML = `${hi},<br>${esc(state.user?.name || '')}`;
  $('#today').textContent = fDay.format(new Date());
  refreshBell();
  load();
}

async function load() {
  try {
    state.items = await api.items();
    render();
  } catch (err) {
    if (err.status === 401) return logout('Klucz przestał działać. Poproś Łukasza o nowy.');
    if (!state.items.length) $('#list').innerHTML = `<div class="empty"><h3>Nie udało się wczytać</h3><p>${esc(err.message)}</p></div>`;
    else toast(err.message);
  }
}

async function logout(msg) { await setToken(null); state.user = null; showHello(msg); }

const eventOf = (it) => dt(it.spec?.event_at) || dt(it.next_at);

function render() {
  const items = state.items;
  renderDays(items);
  if (!items.length) {
    $('#list').innerHTML = `<div class="empty"><h3>Tu jeszcze pusto</h3>
      <p>Napisz na dole zwykłym zdaniem, co mam zapamiętać. Na przykład:</p>
      <ul><li>za 3 dni rano jadę do urzędu złożyć wniosek</li><li>co 2 tygodnie sprawdzaj klimatyzację, przypomnij dzień wcześniej</li>
      <li>kup mleko, chleb i baterie</li></ul></div>`;
    return;
  }
  const once = items.filter((i) => i.kind === 'reminder-once').sort((a, b) => (eventOf(a) || Infinity) - (eventOf(b) || Infinity));
  const hero = once.find((i) => eventOf(i) && eventOf(i) >= startOfDay(new Date()));
  const rest = once.filter((i) => i !== hero);
  const rec = items.filter((i) => i.kind === 'reminder-recurring');
  const lists = items.filter((i) => i.kind === 'checklist');
  const saved = items.filter((i) => ['page-summary', 'note'].includes(i.kind) || !['reminder-once', 'reminder-recurring', 'checklist'].includes(i.kind));

  let html = '';
  if (hero) html += heroCard(hero);
  if (rest.length) html += `<h2 class="sec">${hero ? 'Dalej' : 'Najbliższe'}</h2>` + rest.map(onceCard).join('');
  if (rec.length) html += '<h2 class="sec">Powtarzalne</h2>' + rec.map(recCard).join('');
  if (lists.length) html += '<h2 class="sec">Listy</h2>' + lists.map(listCard).join('');
  if (saved.length) html += '<h2 class="sec">Zapisane</h2>' + saved.map(savedCard).join('');
  $('#list').innerHTML = html;
}

function renderDays(items) {
  const marks = new Set();
  for (const it of items) for (const d of [it.spec?.event_at, ...(it.notify_at || [])]) if (d) marks.add(startOfDay(d).getTime());
  const today = startOfDay(new Date());
  let out = '';
  for (let k = 0; k < 7; k++) {
    const d = new Date(today.getTime() + k * DAY);
    const has = marks.has(d.getTime());
    out += `<li class="${k === 0 ? 'today ' : ''}${has ? 'has' : ''}"><span style="display:flex;flex-direction:column;align-items:center;gap:5px">
      <span class="wd">${esc(fWd.format(d).replace('.', ''))}</span><span class="d">${d.getDate()}</span><span class="mk"></span>
      ${has ? '<span class="sr">są przypomnienia</span>' : ''}</span></li>`;
  }
  $('#days').innerHTML = out;
}

function remindLine(it) {
  const n = (it.notify_at || []).map(dt);
  if (!n.length) return '';
  return 'Przypomnę ' + n.slice(0, 2).map(whenRel).join(' i ');
}

function heroCard(it) {
  const ev = eventOf(it);
  return `<article class="w w--hero" data-id="${it.id}" data-widget="reminder-once" tabindex="0" role="button">
    <p class="kind">${svg('clock', 'width:16px;height:16px')} Jednorazowe · ${esc(when(ev))}</p>
    <p class="big">${esc(rel(ev))}</p>
    <h3>${esc(it.title)}</h3>
    <div class="blob" aria-hidden="true"><svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round">${I.bank}</svg></div>
    <div class="w-f"><span class="meta">${esc(remindLine(it) || it.spec?.understood || '')}</span></div>
  </article>`;
}

function onceCard(it) {
  const ev = eventOf(it);
  return `<article class="w" data-id="${it.id}" data-widget="reminder-once" tabindex="0" role="button">
    <div class="nx">
      <div class="when">${ev ? `<b>${ev.getDate()}</b>${esc(new Intl.DateTimeFormat('pl-PL', { month: 'short' }).format(ev))}` : '—'}</div>
      <div style="min-width:0"><p class="kind">Jednorazowe · ${ev ? esc(rel(ev) + ', ' + fTime.format(ev)) : 'bez terminu'}</p><h3>${esc(it.title)}</h3></div>
    </div>
    ${remindLine(it) ? `<div class="w-f"><span class="meta">${svg('bell')}${esc(remindLine(it))}</span></div>` : ''}
  </article>`;
}

const PERIOD = { day: 1, week: 7, month: 30 };
function recLabel(r) {
  if (!r) return 'Powtarzalne';
  const n = r.every;
  const u = { day: ['dzień', 'dni', 'dni'], week: ['tydzień', 'tygodnie', 'tygodni'], month: ['miesiąc', 'miesiące', 'miesięcy'] }[r.unit];
  if (n === 1) return 'Co ' + u[0];
  return `Co ${n} ` + (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? u[1] : u[2]);
}
function recCard(it) {
  const r = it.spec?.recurrence; const ev = eventOf(it);
  const days = r ? r.every * PERIOD[r.unit] : 14;
  const segs = Math.max(2, Math.min(days, 14));
  const left = ev ? Math.max(0, (ev - Date.now()) / DAY) : days;
  const done = Math.max(0, Math.min(segs - 1, Math.round((1 - left / days) * segs)));
  const bars = Array.from({ length: segs }, (_, k) => `<i class="${k < done ? 'on' : k === done ? 'rem' : ''}"></i>`).join('');
  const nx = (it.notify_at || [])[0];
  return `<article class="w" data-id="${it.id}" data-widget="reminder-recurring" tabindex="0" role="button">
    <div class="w-h"><div class="ico" style="background:var(--tint-mint)" aria-hidden="true">${svg('cycle')}</div>
      <div style="min-width:0"><p class="kind">${esc(recLabel(r))}</p><h3>${esc(it.title)}</h3></div></div>
    <div class="cycle" aria-hidden="true" style="grid-template-columns:repeat(${segs},1fr)">${bars}</div>
    <div class="cyc-l"><span>${ev ? 'następny ' + esc(rel(ev)) : ''}</span><span>${ev ? esc(fShort.format(ev)) : ''}</span></div>
    <div class="w-f" style="flex-direction:column;align-items:flex-start;gap:6px">
      ${ev ? `<span class="meta">${svg('cal')}Następny: ${esc(fDay.format(ev))}</span>` : ''}
      ${nx ? `<span class="meta">${svg('bell')}Przypomnę ${esc(whenRel(dt(nx)))}</span>` : ''}
    </div>
  </article>`;
}

function listCard(it) {
  const list = it.data?.checklist || [];
  const n = list.filter((x) => x.done).length;
  return `<article class="w" data-id="${it.id}" data-widget="checklist">
    <div class="w-h" style="justify-content:space-between"><h3>${esc(it.title)}</h3><p class="kind">${n} z ${list.length}</p></div>
    <ul class="todo">${list.map((x, k) => `<li><label><input type="checkbox" data-check="${k}" ${x.done ? 'checked' : ''}><span>${esc(x.text)}</span></label></li>`).join('')}</ul>
  </article>`;
}

function savedCard(it) {
  const page = it.kind === 'page-summary';
  const url = it.spec?.url || '';
  const host = url.replace(/^https?:\/\//, '').replace(/\/$/, '');
  return `<article class="w" data-id="${it.id}" data-widget="${esc(it.kind)}" tabindex="0" role="button">
    <div class="w-h"><div class="ico" style="background:var(${page ? '--tint-blue' : '--tint-pink'})" aria-hidden="true">${svg(page ? 'globe' : 'note')}</div>
      <div style="min-width:0"><p class="kind">${page ? 'Streszczenie strony' : 'Notatka'}</p><h3>${esc(it.title)}</h3>${page ? `<p class="dom">${esc(host)}</p>` : ''}</div></div>
    ${page ? `<p class="sum">${esc(it.data?.summary || 'Streszczenie pojawi się tutaj — tę część dopiero budujemy.')}</p>` : `<p class="sum">${esc(it.source_text)}</p>`}
  </article>`;
}

// ---------- szczegół ----------
const KIND = { 'reminder-once': 'Jednorazowe', 'reminder-recurring': 'Powtarzalne', checklist: 'Lista', 'page-summary': 'Strona', note: 'Notatka' };
const TOP = { 'reminder-once': '--tint-lavender', 'reminder-recurring': '--tint-mint', checklist: '--tint-pink', 'page-summary': '--tint-blue', note: '--tint-pink' };

function openDetail(id) {
  const it = state.items.find((x) => x.id === id);
  if (!it) return;
  state.openId = id;
  const ev = eventOf(it);
  const rows = [];
  if (ev && it.kind !== 'checklist' && it.kind !== 'note') rows.push(['Kiedy', fDay.format(ev) + ', ' + fTime.format(ev)]);
  if (it.kind === 'reminder-recurring') rows.push(['Powtarzanie', recLabel(it.spec?.recurrence)]);
  if ((it.notify_at || []).length) rows.push(['Przypomnienia', it.notify_at.map((d) => whenRel(dt(d))).join(' · ')]);
  if (it.data?.tip) rows.push(['Podpowiedź', it.data.tip]);
  if (it.spec?.understood) rows.push(['Jak Oboe to rozumie', it.spec.understood]);
  const url = it.spec?.url;
  const [first, ...more] = it.title.split(/\s+[—–-]\s+/);
  $('#detail').innerHTML = `<div class="app">
    <div class="d-top" style="background:var(${TOP[it.kind] || '--tint-lavender'})">
      <span class="ring" aria-hidden="true"></span>
      <div class="d-nav"><button class="round" type="button" data-act="close" aria-label="Wróć">${svg('back')}</button>
        ${url ? `<a class="round" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Otwórz stronę">${svg('ext')}</a>` : ''}</div>
      <h1>${esc(first)}${more.length ? `<b>${esc(more.join(' — '))}</b>` : ''}</h1>
      <span class="pill">${esc(KIND[it.kind] || 'Rzecz')}${ev && it.kind !== 'note' ? ' · ' + esc(rel(ev)) : ''}</span>
    </div>
    <div class="d-body">
      <div class="quote">Wpisane ${esc(rel(dt(it.created_at)))}, ${esc(fTime.format(dt(it.created_at)))}:<q>${esc(it.source_text)}</q></div>
      ${rows.length ? `<ul class="rows">${rows.map(([a, b]) => `<li><span>${esc(a)}</span><b>${esc(b)}</b></li>`).join('')}</ul>` : ''}
      <div class="d-cta">
        <button class="cta" type="button" data-act="done">${svg('check')}Oznacz jako zrobione</button>
        <button class="ghost danger" type="button" data-act="delete" aria-label="Usuń">${svg('trash')}</button>
      </div>
    </div></div>`;
  $('#detail').classList.add('open');
  document.body.style.overflow = 'hidden';
  history.pushState({ detail: id }, '');
}

function closeDetail(fromPop = false) {
  if (!$('#detail').classList.contains('open')) return;
  $('#detail').classList.remove('open');
  document.body.style.overflow = '';
  state.openId = null;
  if (!fromPop && history.state?.detail) history.back();
}

async function detailAction(act) {
  const id = state.openId;
  if (act === 'close') return closeDetail();
  if (act === 'delete' && !confirm('Usunąć na dobre?')) return;
  try {
    await (act === 'done' ? api.done(id) : api.remove(id));
    state.items = state.items.filter((x) => x.id !== id);
    closeDetail(); render();
    toast(act === 'done' ? 'Zrobione ✓' : 'Usunięte');
  } catch (err) { toast(err.message); }
}

// ---------- dodawanie ----------
async function add(e) {
  e.preventDefault();
  const q = $('#q'); const text = q.value.trim();
  if (!text) { q.focus(); return; }
  const form = $('#wpisz'); form.classList.add('busy');
  try {
    const r = await api.add(text);
    q.value = ''; q.blur();
    toast(r.item?.spec?.understood || 'Zapisane');
    await load();
  } catch (err) {
    if (err.status === 401) return logout('Klucz przestał działać. Poproś Łukasza o nowy.');
    toast(err.message);
  } finally { form.classList.remove('busy'); }
}

// ---------- powiadomienia ----------
async function refreshBell() {
  let on = false;
  try { on = push.permission() === 'granted' && !!(await push.current()); } catch {}
  $('#bell-badge').hidden = on || !push.supported();
  $('#bell').setAttribute('aria-label', on ? 'Powiadomienia włączone' : 'Włącz powiadomienia');
  if (on) push.resync();
}

async function bell() {
  if (IOS && !STANDALONE) return toast('Najpierw dodaj Oboe do ekranu początkowego (Udostępnij → „Do ekranu początkowego”) i otwórz stamtąd.');
  if (!push.supported()) return toast('Ta przeglądarka nie obsługuje powiadomień.');
  try {
    if (push.permission() === 'granted' && (await push.current())) { await push.resync(); return toast('Powiadomienia są włączone.'); }
    await push.enable();
    toast('Powiadomienia włączone ✓');
  } catch (err) { toast(err.message); }
  refreshBell();
}

// ---------- drobne ----------
let toastTimer;
function toast(msg) {
  document.querySelector('.toast')?.remove();
  const el = document.createElement('div');
  el.className = 'toast'; el.setAttribute('role', 'status'); el.textContent = msg;
  document.body.appendChild(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), Math.min(9000, 2500 + msg.length * 45));
}

function bind() {
  $('#tok-form').addEventListener('submit', submitToken);
  $('#tok-paste').addEventListener('click', async () => {
    try { $('#tok').value = (await navigator.clipboard.readText()).trim(); submitToken(); }
    catch { $('#tok').focus(); $('#tok-err').textContent = 'Przytrzymaj pole i wybierz „Wklej”.'; }
  });
  $('#wpisz').addEventListener('submit', add);
  $('#plus').addEventListener('click', () => $('#q').focus());
  $('#mic').addEventListener('click', () => { $('#q').focus(); toast('Użyj mikrofonu na klawiaturze telefonu — dyktowanie w aplikacji dojdzie później.'); });
  $('#bell').addEventListener('click', bell);

  $('#list').addEventListener('change', async (e) => {
    const cb = e.target.closest('[data-check]'); if (!cb) return;
    const id = cb.closest('[data-id]').dataset.id;
    try {
      const r = await api.check(id, Number(cb.dataset.check), cb.checked);
      const it = state.items.find((x) => x.id === id); if (it) it.data = r.data;
      render();
    } catch (err) { cb.checked = !cb.checked; toast(err.message); }
  });
  const openFrom = (e) => {
    if (e.target.closest('label, input, a')) return;
    const card = e.target.closest('[data-id]');
    if (card && card.dataset.widget !== 'checklist') openDetail(card.dataset.id);
  };
  $('#list').addEventListener('click', openFrom);
  $('#list').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFrom(e); } });
  $('#detail').addEventListener('click', (e) => { const b = e.target.closest('[data-act]'); if (b) detailAction(b.dataset.act); });
  addEventListener('popstate', () => closeDetail(true));
  addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetail(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && state.user) { load(); refreshBell(); } });
  navigator.serviceWorker?.addEventListener('message', (e) => { if (e.data?.type === 'open') { load().then(() => e.data.id && openDetail(e.data.id)); } });
}

async function boot() {
  bind();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
  const params = new URLSearchParams(location.search);
  const openId = params.get('open');
  if (params.has('open')) history.replaceState(null, '', location.pathname);
  const t = getToken();
  if (!t) return showHello();
  try {
    state.user = (await api.me()).user;
    await setToken(t);          // odśwież kopię dla service workera
    startMain();
    if (openId) { await load(); openDetail(openId); }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return logout('Klucz przestał działać. Poproś Łukasza o nowy.');
    showHello(err.message);
  }
}

boot();
