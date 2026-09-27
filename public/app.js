// Luna (wewn. oboe) — aplikacja. Wygląd i anatomia kart 1:1 z makiety A (Sekkei); tu tylko dane i zachowanie.
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
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7L20 8.6"/><path d="M20 4v4.6h-4.6"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3.5 6 1.5 1.5L7.5 5M3.5 12l1.5 1.5L7.5 11M3.5 18l1.5 1.5 2.5-2.5"/>',
  building: '<path d="M3 10 12 4l9 6z"/><path d="M5 10v9M9.5 10v9M14.5 10v9M19 10v9M3 21h18"/>',
  tv: '<rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="m8 3 4 3 4-3"/>',
  health: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/><path d="M9 11h6M12 8v6"/>',
  car: '<path d="M5 16V11l2-5h10l2 5v5"/><path d="M3 16h18v3H3zM5 11h14"/><circle cx="7.5" cy="16" r="1.5"/><circle cx="16.5" cy="16" r="1.5"/>',
  home: '<path d="M4 11 12 4l8 7"/><path d="M6 10v10h12V10"/><path d="M10 20v-6h4v6"/>',
  cart: '<path d="M3 4h2l2.4 11h10.2L20 8H6.2"/><circle cx="9" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
  work: '<rect x="3" y="7" width="18" height="13" rx="2.5"/><path d="M9 7V5h6v2M3 12h18"/>',
  money: '<rect x="3" y="6" width="18" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.5"/><path d="M6.5 9.5h.01M17.5 14.5h.01"/>',
  sport: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6c3.5 3.5 3.5 9.3 0 12.8M18.4 5.6c-3.5 3.5-3.5 9.3 0 12.8"/>',
  people: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2c2.8.2 5 2.6 5 5.8"/>',
  doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  food: '<path d="M4 3v8a3 3 0 0 0 6 0V3M7 3v18M17 3c-2 2-3 5-3 8h3v10"/>',
  travel: '<path d="M2 16l20-8-8 12-2-5z"/><path d="m12 15-4 5"/>',
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
  if (!introSeen()) openIntro();
}

// ---------- karta powitalna: kim jest Luna ----------
const EXAMPLES = ['za 3 dni rano jadę do urzędu złożyć wniosek', 'co 2 tygodnie sprawdzaj klimatyzację, przypomnij dzień wcześniej',
  'kup mleko, chleb i baterie', 'zaglądaj co tydzień na draminskiweb.pl i daj znać, co się zmieniło'];
const exChips = () => EXAMPLES.map((t) => `<button type="button" data-ex="${esc(t)}">${esc(t)}</button>`).join('');
const introKey = () => 'luna-intro-' + (state.user?.id || state.user?.email || '');
function introSeen() { try { return localStorage.getItem(introKey()) === '1'; } catch { return true; } }
async function openIntro() {
  $('#intro-ex').innerHTML = exChips();
  let on = false;
  try { on = push.permission() === 'granted' && !!(await push.current()); } catch {}
  $('#intro-push').hidden = on || !push.supported();
  if (!$('#intro').open) $('#intro').showModal();
}
function closeIntro() {
  try { localStorage.setItem(introKey(), '1'); } catch {}
  if ($('#intro').open) $('#intro').close();
}
function useExample(text) {
  closeIntro();
  const q = $('#q'); q.value = text; q.focus();
  toast('Wyślij, a zapiszę — albo zmień po swojemu.');
}

async function load() {
  try {
    state.items = await api.items();
    render();
    watchGenerating();
  } catch (err) {
    if (err.status === 401) return logout('Klucz przestał działać. Poproś Łukasza o nowy.');
    if (!state.items.length) $('#list').innerHTML = `<div class="empty"><h3>Nie udało się wczytać</h3><p>${esc(err.message)}</p></div>`;
    else toast(err.message);
  }
}

async function logout(msg) { await setToken(null); state.user = null; showHello(msg); }

const eventOf = (it) => dt(it.spec?.event_at) || dt(it.next_at);
// Po terminie: jednorazowa rzecz z terminem, który już minął (cykliczne przesuwa harmonogram, więc nigdy nie są „po”).
const isLate = (it) => { const ev = !it.spec?.recurrence && eventOf(it); return !!ev && ev < Date.now(); };
const lateLabel = (ev) => 'Po terminie · ' + rel(ev) + ', ' + fTime.format(ev);

function render() {
  const items = state.items;
  renderDays(items);
  if (!items.length) {
    $('#list').innerHTML = `<div class="empty"><h3>Jeszcze nic mi nie powierzono</h3>
      <p>Napisz na dole zwykłym zdaniem, co mam zapamiętać — resztą zajmę się sama. Na przykład:</p>
      <div class="ex">${exChips()}</div></div>`;
    return;
  }
  const byTime = (a, b) => (eventOf(a) || Infinity) - (eventOf(b) || Infinity);
  const dated = items.filter((i) => !i.spec?.recurrence && eventOf(i)).sort(byTime);
  const late = dated.filter(isLate);
  const hero = dated.find((i) => !isLate(i));
  const rest = dated.filter((i) => i !== hero && !isLate(i));
  const rec = items.filter((i) => i.spec?.recurrence).sort(byTime);
  const lists = items.filter((i) => !i.spec?.recurrence && !eventOf(i) && listOf(i).length);
  const tracked = items.filter((i) => !i.spec?.recurrence && !eventOf(i) && i.data?.widget && i.data.widget.status !== 'rejected');
  const saved = items.filter((i) => !i.spec?.recurrence && !eventOf(i) && !listOf(i).length && !tracked.includes(i));

  let html = '';
  if (late.length) html += `<h2 class="sec sec--late">Po terminie <span>${late.length}</span></h2>` + late.map((i) => card(i)).join('');
  if (hero) html += card(hero, true);
  if (rest.length) html += `<h2 class="sec">${hero ? 'Dalej' : 'Najbliższe'}</h2>` + rest.map((i) => card(i)).join('');
  if (rec.length) html += '<h2 class="sec">Powtarzalne</h2>' + rec.map((i) => card(i)).join('');
  if (tracked.length) html += '<h2 class="sec">Śledzone</h2>' + tracked.map((i) => card(i)).join('');
  if (lists.length) html += '<h2 class="sec">Listy</h2>' + lists.map((i) => card(i)).join('');
  if (saved.length) html += '<h2 class="sec">Zapisane</h2>' + saved.map((i) => card(i)).join('');
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
  const n = (it.notify_at || []).map(dt).filter((d) => d > Date.now());
  if (!n.length) return '';
  if (it.spec?.summarize) return 'Sprawdzę stronę ' + whenRel(n[0]) + ' — dam znać, jeśli coś się zmieni';
  return 'Przypomnę ' + n.slice(0, 2).map(whenRel).join(' i ');
}

const PERIOD = { day: 1, week: 7, month: 30 };
function recLabel(r) {
  if (!r) return 'Powtarzalne';
  const n = r.every;
  const u = { day: ['dzień', 'dni', 'dni'], week: ['tydzień', 'tygodnie', 'tygodni'], month: ['miesiąc', 'miesiące', 'miesięcy'] }[r.unit];
  if (n === 1) return 'Co ' + u[0];
  return `Co ${n} ` + (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? u[1] : u[2]);
}

// ---------- karta = części (termin, lista, strona, szczegóły) ----------
// Wygląd każdej części 1:1 z makiety A; karta składa tylko te, które rzecz ma.
const TINT = { lavender: '--tint-lavender', mint: '--tint-mint', blue: '--tint-blue', pink: '--tint-pink', sky: '--tint-sky' };
const DEF_LOOK = { 'reminder-once': ['lavender', 'clock'], 'reminder-recurring': ['mint', 'cycle'], checklist: ['pink', 'list'], 'page-summary': ['blue', 'globe'], note: ['pink', 'note'] };
function lookOf(it) {
  const d = DEF_LOOK[it.kind] || DEF_LOOK.note; const l = it.data?.look || {};
  return { tint: TINT[l.tint] ? l.tint : d[0], icon: I[l.icon] ? l.icon : d[1] };
}
const listOf = (it) => it.data?.checklist || [];
const hostOf = (url) => (url || '').replace(/^https?:\/\//, '').replace(/\/$/, '');

function kindLabel(it) {
  const r = it.spec?.recurrence; const ev = eventOf(it);
  if (r) return recLabel(r);
  if (ev && isLate(it)) return lateLabel(ev);
  if (ev) return (it.kind === 'reminder-once' ? 'Jednorazowe · ' : '') + rel(ev) + ', ' + fTime.format(ev);
  if (it.data?.widget && it.data.widget.status !== 'rejected') return 'Śledzenie';
  if (listOf(it).length) return 'Lista';
  if (it.spec?.url) return it.spec?.summarize ? 'Streszczenie strony' : 'Strona';
  return 'Notatka';
}

function partCycle(it) {
  const r = it.spec?.recurrence; if (!r) return '';
  const ev = eventOf(it);
  const days = r.every * PERIOD[r.unit];
  const segs = Math.max(2, Math.min(days, 14));
  const left = ev ? Math.max(0, (ev - Date.now()) / DAY) : days;
  const done = Math.max(0, Math.min(segs - 1, Math.round((1 - left / days) * segs)));
  const bars = Array.from({ length: segs }, (_, k) => `<i class="${k < done ? 'on' : k === done ? 'rem' : ''}"></i>`).join('');
  return `<div class="cycle" aria-hidden="true" style="grid-template-columns:repeat(${segs},1fr)">${bars}</div>
    <div class="cyc-l"><span>${ev ? 'następny ' + esc(rel(ev)) : ''}</span><span>${ev ? esc(fShort.format(ev)) : ''}</span></div>`;
}
function partList(it) {
  const list = listOf(it); if (!list.length) return '';
  return `<ul class="todo">${list.map((x, k) => `<li><label><input type="checkbox" data-check="${k}" ${x.done ? 'checked' : ''}><span>${esc(x.text)}</span></label></li>`).join('')}</ul>`;
}
function partFields(it) {
  const f = it.data?.fields || []; if (!f.length) return '';
  return `<p class="chips">${f.map((x) => `<span><small>${esc(x.label)}</small> ${esc(x.value)}</span>`).join('')}</p>`;
}
function partPage(it, full = false) {
  const url = it.spec?.url; if (!url) return '';
  const d = it.data || {}; const sm = d.summary;
  let body = '';
  if (it.spec?.summarize || sm) {
    if (d.summary_status === 'working') body = `<p class="gen-state">${svg('spark', 'width:15px;height:15px')} Czytam stronę…</p>`;
    else if (d.summary_status === 'error' && !sm) body = `<p class="gen-state bad">${esc(d.summary_error || 'Nie udało się streścić strony.')}</p>`;
    if (sm) {
      const bl = full ? sm.bullets : sm.bullets.slice(0, 3);
      body += `${sm.changed && sm.changes ? `<p class="chg">${svg('spark', 'width:14px;height:14px')} ${esc(sm.changes)}</p>` : ''}
        <p class="sum-h">${esc(sm.headline)}</p>
        ${bl.length ? `<ul class="sum">${bl.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}`;
    }
  }
  const checked = sm?.checked_at ? `Sprawdzono ${rel(dt(sm.checked_at))}, ${fTime.format(dt(sm.checked_at))}` : '';
  return `${body}<div class="w-f"><span class="meta">${svg('globe', 'width:15px;height:15px')}<span class="dom">${esc(hostOf(url))}</span></span>
      <span style="display:flex;gap:8px;align-items:center">
        ${it.spec?.summarize || sm ? `<button type="button" class="chev" data-sum="${it.id}" aria-label="Sprawdź teraz"${d.summary_status === 'working' ? ' disabled' : ''}>${svg('refresh')}</button>` : ''}
        <a class="chev" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Otwórz stronę">${svg('ext')}</a></span></div>
    ${checked ? `<p class="dom" style="margin-top:6px">${esc(checked)}${d.summary_status === 'error' && sm ? ' · ostatnia próba: ' + esc(d.summary_error || 'błąd') : ''}</p>` : ''}`;
}
// Widget wygenerowany przez AI: iframe sandbox (bez allow-same-origin) + CSP sandbox z nginx = osobny, pusty origin,
// bez sieci i bez dostępu do aplikacji. Rozmowa tylko przez postMessage (oboe:data / ready / resize / save).
function partWidget(it) {
  const w = it.data?.widget; if (!w) return '';
  if (w.status === 'generating') return `<p class="gen-state">${svg('spark', 'width:15px;height:15px')} Robię widget do tej rzeczy…</p>`;
  if (w.status === 'rejected') return `<p class="gen-state bad">Widget nie przeszedł kontroli bezpieczeństwa, więc zostawiam zwykłą kartę.</p>`;
  if (w.status !== 'ready' || !/^[a-z0-9-]+$/.test(w.slug || '') || !Number.isInteger(w.version)) return '';
  const note = w.pending ? `<p class="gen-state">${svg('spark', 'width:15px;height:15px')} Przebudowuję widget — ten działa do czasu podmiany…</p>`
    : w.revision_error ? `<p class="gen-state bad">Nowa wersja nie przeszła kontroli, więc zostawiam tę. ${esc(String(w.revision_error).replace(/^ODRZUCONY( po poprawce)?: /, '').slice(0, 160))}</p>` : '';
  return note + `<iframe class="wframe" data-wid="${it.id}" src="/widgets/${w.slug}.v${w.version}.html" sandbox="allow-scripts"
    title="Widget: ${esc(it.title)}" loading="lazy" referrerpolicy="no-referrer" style="height:120px"></iframe>`;
}

function partFoot(it) {
  const rem = remindLine(it);
  const list = listOf(it); const n = list.filter((x) => x.done).length;
  const bits = [];
  if (rem) bits.push(`<span class="meta">${svg('bell')}${esc(rem)}</span>`);
  if (list.length) bits.push(`<span class="meta">${n} z ${list.length} zrobione${it.data?.checklist_reset ? ' · odnawia się' : ''}</span>`);
  if (isLate(it)) bits.push(`<button type="button" class="late-done" data-done="${it.id}">${svg('check', 'width:16px;height:16px')}Zrobione</button>`);
  return bits.length ? `<div class="w-f" style="flex-wrap:wrap">${bits.join('')}</div>` : '';
}

function card(it, hero = false) {
  const { tint, icon } = lookOf(it);
  const ev = eventOf(it);
  const noteText = !listOf(it).length && !it.spec?.url && !ev && !it.spec?.recurrence ? `<p class="sum">${esc(it.source_text)}</p>` : '';
  if (hero) {
    return `<article class="w w--hero" data-id="${it.id}" data-widget="${esc(it.kind)}" tabindex="0" role="button">
      <p class="kind">${svg('clock', 'width:16px;height:16px')} ${esc(kindLabel(it).replace(/^Jednorazowe · /, 'Jednorazowe · ') )}</p>
      <p class="big">${esc(rel(ev))}</p>
      <h3>${esc(it.title)}</h3>
      <div class="blob" aria-hidden="true"><svg class="i" viewBox="0 0 24 24" style="width:64px;height:64px;stroke-width:1.4;margin:-10px 18px 0 0">${I[icon]}</svg></div>
      ${partFields(it)}${partWidget(it)}${partList(it)}${partFoot(it)}
    </article>`;
  }
  const late = isLate(it);
  return `<article class="w${late ? ' w--late' : ''}" data-id="${it.id}" data-widget="${esc(it.kind)}" tabindex="0" role="button">
    <div class="w-h"><div class="ico" style="background:var(${late ? '--late-bg' : TINT[tint]})" aria-hidden="true">${svg(icon)}</div>
      <div style="min-width:0"><p class="kind">${esc(kindLabel(it))}</p><h3>${esc(it.title)}</h3></div></div>
    ${partCycle(it)}${partFields(it)}${partPage(it)}${partWidget(it)}${partList(it)}${it.data?.widget ? '' : noteText}${partFoot(it)}
  </article>`;
}

// ---------- szczegół ----------
const KIND = { 'reminder-once': 'Jednorazowe', 'reminder-recurring': 'Powtarzalne', checklist: 'Lista', 'page-summary': 'Strona', note: 'Notatka' };
const TOP = { 'reminder-once': '--tint-lavender', 'reminder-recurring': '--tint-mint', checklist: '--tint-pink', 'page-summary': '--tint-blue', note: '--tint-pink' };

function openDetail(id) {
  const it = state.items.find((x) => x.id === id);
  if (!it) return;
  state.openId = id;
  const { tint } = lookOf(it);
  const ev = eventOf(it);
  const rows = [];
  const late = isLate(it);
  if (ev) rows.push([it.spec?.recurrence ? 'Następny raz' : late ? 'Termin był' : 'Kiedy', fDay.format(ev) + ', ' + fTime.format(ev)]);
  if (it.spec?.recurrence) rows.push(['Powtarzanie', recLabel(it.spec.recurrence)]);
  if ((it.notify_at || []).length) rows.push(['Przypomnienia', it.notify_at.map((d) => whenRel(dt(d))).join(' · ')]);
  for (const f of it.data?.fields || []) rows.push([f.label, f.value]);
  if (it.data?.tip) rows.push(['Podpowiedź', it.data.tip]);
  if (it.spec?.understood) rows.push(['Jak to zrozumiałam', it.spec.understood]);
  const url = it.spec?.url;
  const list = listOf(it);
  const [first, ...more] = it.title.split(/\s+[—–-]\s+/);
  $('#detail').innerHTML = `<div class="app">
    <div class="d-top${late ? ' d-top--late' : ''}" style="background:var(${late ? '--late-bg' : TINT[tint]})">
      <span class="ring" aria-hidden="true"></span>
      <div class="d-nav"><button class="round" type="button" data-act="close" aria-label="Wróć">${svg('back')}</button>
        ${url ? `<a class="round" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Otwórz stronę">${svg('ext')}</a>` : ''}</div>
      <h1>${esc(first)}${more.length ? `<b>${esc(more.join(' — '))}</b>` : ''}</h1>
      <span class="pill">${late ? svg('clock', 'width:14px;height:14px') : ''}${esc(kindLabel(it))}</span>
    </div>
    <div class="d-body">
      <div class="quote">Wpisane ${esc(rel(dt(it.created_at)))}, ${esc(fTime.format(dt(it.created_at)))}:<q>${esc(it.source_text)}</q></div>
      ${it.data?.widget ? `<div class="w" style="margin-top:12px;cursor:default">${partWidget(it)}</div>` : ''}
      ${list.length ? `<div class="w" data-id="${it.id}" style="margin-top:12px;cursor:default">
          <div class="w-h" style="justify-content:space-between"><h3>Do odhaczenia</h3>
          <p class="kind">${list.filter((x) => x.done).length} z ${list.length}${it.data?.checklist_reset ? ' · odnawia się' : ''}</p></div>${partList(it)}</div>` : ''}
      ${url ? `<div class="w" style="margin-top:12px;cursor:default"><p class="kind">${it.spec?.summarize ? 'Streszczenie strony' : 'Strona'}</p>${partPage(it, true)}</div>` : ''}
      ${rows.length ? `<ul class="rows">${rows.map(([a, b]) => `<li><span>${esc(a)}</span><b>${esc(b)}</b></li>`).join('')}</ul>` : ''}
      <button class="cta alt wide" type="button" data-act="chat">${svg('spark')}${it.data?.widget?.slug ? 'Popraw widget' : 'Zrób widget'}</button>
      <div class="d-cta">
        <button class="cta" type="button" data-act="done">${svg('check')}${it.spec?.recurrence ? 'Zakończ powtarzanie' : 'Oznacz jako zrobione'}</button>
        <button class="ghost danger" type="button" data-act="delete" aria-label="Usuń">${svg('trash')}</button>
      </div>
    </div></div>`;
  $('#detail').classList.add('open');
  document.body.style.overflow = 'hidden';
  if (!history.state?.detail) history.pushState({ detail: id }, '');
}

function closeDetail(fromPop = false) {
  if (!$('#detail').classList.contains('open')) return;
  $('#detail').classList.remove('open');
  document.body.style.overflow = '';
  state.openId = null;
  if (!fromPop && history.state?.detail) history.back();
}

async function markDone(id) {
  await api.done(id);
  state.items = state.items.filter((x) => x.id !== id);
  render(); toast('Zrobione ✓');
}

// Gdy termin minie przy otwartej aplikacji, karta ma sama przejść do „Po terminie”. Render tylko przy zmianie zbioru,
// bo przerysowanie listy przeładowuje iframe'y widgetów.
let lateSig = '';
const lateNow = () => state.items.filter(isLate).map((i) => i.id).join(',');
setInterval(() => {
  if (!state.user || document.hidden) return;
  const sig = lateNow(); if (sig === lateSig) return;
  lateSig = sig; render();
  if (state.openId) openDetail(state.openId);
}, 30e3);

async function detailAction(act) {
  const id = state.openId;
  if (act === 'close') return closeDetail();
  if (act === 'chat') return openChat(id);
  if (act === 'delete' && !confirm('Usunąć na dobre?')) return;
  try {
    await (act === 'done' ? api.done(id) : api.remove(id));
    state.items = state.items.filter((x) => x.id !== id);
    closeDetail(); render();
    toast(act === 'done' ? 'Zrobione ✓' : 'Usunęłam.');
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
    toast(r.item?.spec?.understood || 'Zapisałam.');
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
  if (IOS && !STANDALONE) return toast('Najpierw dodaj mnie do ekranu początkowego (Udostępnij → „Do ekranu początkowego”) i otwórz stamtąd.');
  if (!push.supported()) return toast('W tej przeglądarce nie mogę wysyłać ci powiadomień.');
  try {
    if (push.permission() === 'granted' && (await push.current())) { await push.resync(); return toast('Powiadomienia są włączone — odezwę się, kiedy trzeba.'); }
    await push.enable();
    toast('Gotowe — odezwę się, kiedy trzeba ✓');
  } catch (err) { toast(err.message); }
  refreshBell();
}

// ---------- czat: popraw / zrób widget ----------
const chat = { id: null, busy: false };
function chatGreeting(it) {
  return it.data?.widget?.slug
    ? 'Co nie pasuje w tym widgecie? Opisz, co zmienić — dopytam o szczegóły, a zanim przebuduję, pokażę plan.'
    : 'Jaki widget ma tu być? Napisz, co ma pokazywać i co chcesz w nim wpisywać.';
}
function renderChat(messages, proposal) {
  const it = state.items.find((x) => x.id === chat.id);
  const all = [{ role: 'assistant', text: chatGreeting(it || {}) }, ...(messages || [])];
  $('#msgs').innerHTML = all.map((m) => `<p class="msg ${m.role === 'user' ? 'me' : 'ai'}">${esc(m.text)}</p>`).join('')
    + (chat.busy ? '<p class="msg ai typing" aria-label="AI pisze"><i></i><i></i><i></i></p>' : '');
  $('#prop').hidden = !proposal;
  if (proposal) $('#prop-text').textContent = proposal.summary;
  const box = $('#msgs'); box.scrollTop = box.scrollHeight;
}
async function openChat(id) {
  const it = state.items.find((x) => x.id === id); if (!it) return;
  chat.id = id; chat.busy = false;
  $('#chat-title').textContent = it.data?.widget?.slug ? 'Popraw widget' : 'Zrób widget';
  $('#chat-kind').textContent = it.title;
  renderChat([], null);
  $('#chat').showModal();
  try { const r = await api.widgetChat(id, ''); renderChat(r.messages, r.proposal); } catch (err) { toast(err.message); }
  $('#chat-q').focus();
}
async function sendChat(e) {
  e.preventDefault();
  const q = $('#chat-q'); const text = q.value.trim();
  if (!text || chat.busy) return;
  const shown = [...$('#msgs').querySelectorAll('.msg')].slice(1).map((el) => ({ role: el.classList.contains('me') ? 'user' : 'assistant', text: el.textContent }));
  q.value = ''; chat.busy = true;
  renderChat([...shown, { role: 'user', text }], null);
  try { const r = await api.widgetChat(chat.id, text); chat.busy = false; renderChat(r.messages, r.proposal); }
  catch (err) { chat.busy = false; renderChat(shown, null); q.value = text; toast(err.message); }
  q.focus();
}
async function chatAction(act) {
  if (act === 'close') return $('#chat').close();
  if (act === 'more') { $('#prop').hidden = true; $('#chat-q').placeholder = 'Co jeszcze zmienić?'; return $('#chat-q').focus(); }
  if (act === 'reset') {
    try { await api.widgetChatClose(chat.id); renderChat([], null); $('#chat-q').focus(); } catch (err) { toast(err.message); }
    return;
  }
  if (act === 'go') {
    try {
      await api.widgetRegenerate(chat.id);
      $('#chat').close();
      toast('Przebudowuję widget — obecny działa do czasu podmiany.');
      await load(); if (state.openId) openDetail(state.openId);
    } catch (err) { toast(err.message); }
  }
}

// ---------- most do widgetów ----------
function frameFor(win) { return [...document.querySelectorAll('iframe.wframe')].find((f) => f.contentWindow === win); }
function sendData(f) {
  const it = state.items.find((x) => x.id === f.dataset.wid);
  if (it) f.contentWindow.postMessage({ type: 'oboe:data', state: it.data?.widget?.state || {}, now: new Date().toISOString() }, '*');
}
const saveTimers = new Map();
addEventListener('message', (e) => {
  const f = frameFor(e.source); if (!f || !e.data || typeof e.data !== 'object') return;
  const it = state.items.find((x) => x.id === f.dataset.wid); if (!it) return;
  if (e.data.type === 'oboe:ready') sendData(f);
  else if (e.data.type === 'oboe:resize') f.style.height = Math.max(40, Math.min(900, Number(e.data.height) || 120)) + 'px';
  else if (e.data.type === 'oboe:save' && e.data.state && typeof e.data.state === 'object') {
    const json = JSON.stringify(e.data.state); if (json.length > 20000) return toast('Za dużo danych w widgecie.');
    it.data.widget.state = JSON.parse(json);
    // inne kopie tego widgetu (karta i szczegół) dostają nowy stan
    document.querySelectorAll(`iframe.wframe[data-wid="${it.id}"]`).forEach((g) => { if (g !== f) sendData(g); });
    clearTimeout(saveTimers.get(it.id));
    saveTimers.set(it.id, setTimeout(() => api.widgetState(it.id, it.data.widget.state).catch((err) => toast(err.message)), 600));
  }
});
// Widget, który nie przyśle oboe:ready (np. wolno się ładuje), i tak dostaje dane po załadowaniu ramki.
document.addEventListener('load', (e) => { if (e.target.matches?.('iframe.wframe')) sendData(e.target); }, true);
// Dopóki jakiś widget się generuje, odświeżaj listę co 8 s.
let genTimer;
function watchGenerating() {
  clearTimeout(genTimer);
  if (state.items.some((i) => i.data?.widget?.status === 'generating' || i.data?.widget?.pending || i.data?.summary_status === 'working'))
    genTimer = setTimeout(() => load().then(() => { if (state.openId) openDetail(state.openId); }), 5000);
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
  $('#mic').addEventListener('click', () => { $('#q').focus(); toast('Na razie podyktuj mi to mikrofonem z klawiatury telefonu — własne słuchanie dostanę później.'); });
  $('#bell').addEventListener('click', bell);
  $('#luna').addEventListener('click', openIntro);
  $('#intro').addEventListener('click', async (e) => {
    const ex = e.target.closest('[data-ex]'); if (ex) return useExample(ex.dataset.ex);
    const b = e.target.closest('[data-intro]'); if (!b) return;
    if (b.dataset.intro === 'close') return closeIntro();
    if (b.dataset.intro === 'push') { await bell(); openIntro(); }
  });
  $('#intro').addEventListener('cancel', () => { try { localStorage.setItem(introKey(), '1'); } catch {} });
  $('#list').addEventListener('click', (e) => { const ex = e.target.closest('.empty [data-ex]'); if (ex) { const q = $('#q'); q.value = ex.dataset.ex; q.focus(); } });

  const onCheck = async (e) => {
    const cb = e.target.closest('[data-check]'); if (!cb) return;
    const id = cb.closest('[data-id]').dataset.id;
    try {
      const r = await api.check(id, Number(cb.dataset.check), cb.checked);
      const it = state.items.find((x) => x.id === id); if (it) it.data = r.data;
      render();
      if (state.openId === id) openDetail(id);
    } catch (err) { cb.checked = !cb.checked; toast(err.message); }
  };
  $('#list').addEventListener('change', onCheck);
  $('#detail').addEventListener('change', onCheck);
  const openFrom = (e) => {
    if (e.target.closest('label, input, a, button[data-sum], button[data-done]')) return;
    const card = e.target.closest('[data-id]');
    if (card) openDetail(card.dataset.id);
  };
  $('#list').addEventListener('click', openFrom);
  $('#list').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFrom(e); } });
  $('#detail').addEventListener('click', (e) => { const b = e.target.closest('[data-act]'); if (b) detailAction(b.dataset.act); });
  const onSum = async (e) => {
    const b = e.target.closest('[data-sum]'); if (!b) return;
    e.stopPropagation(); b.disabled = true;
    const it = state.items.find((x) => x.id === b.dataset.sum);
    try {
      await api.summarize(b.dataset.sum);
      if (it) it.data = { ...(it.data || {}), summary_status: 'working' };
      render(); if (state.openId === it?.id) openDetail(it.id);
      toast('Sprawdzam stronę…'); watchGenerating();
    } catch (err) { b.disabled = false; toast(err.message); }
  };
  $('#list').addEventListener('click', onSum, true);
  $('#list').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-done]'); if (!b) return;
    b.disabled = true;
    try { await markDone(b.dataset.done); } catch (err) { b.disabled = false; toast(err.message); }
  });
  $('#chat-form').addEventListener('submit', sendChat);
  $('#chat').addEventListener('click', (e) => { const b = e.target.closest('[data-chat]'); if (b) chatAction(b.dataset.chat); });
  $('#detail').addEventListener('click', onSum, true);
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
