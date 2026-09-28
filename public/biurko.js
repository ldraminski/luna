// Biurko Luny (wewn. oboe) — wklej dłuższy materiał → Luna rozbija go na rzeczy (/api/items/split, nic nie zapisuje) →
// przegląd i poprawki → każda rzecz idzie zwykłym POST /api/items, tak jak wpis z telefonu. 28.09.2026.
import { api, getToken } from './api.js?v=__V__';

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MAX = 20000;
const DRAFT = 'luna-biurko-szkic';   // szkic materiału zostaje w przeglądarce, gdyby karta się zamknęła
const fWd = new Intl.DateTimeFormat('pl-PL', { weekday: 'short' });
const fDay = (d) => `${fWd.format(d).replace('.', '')} ${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
const fTime = new Intl.DateTimeFormat('pl-PL', { hour: 'numeric', minute: '2-digit' });
const fresh = new Set();   // rzeczy zapisane w tej sesji biurka — wyróżnione w „Najbliższych”

let toastTimer;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, Math.min(9000, 2500 + msg.length * 45));
}
const fail = (err) => {
  if (err.status === 401) { $('#desk').hidden = true; $('#gate').hidden = false; return; }
  toast(err.status === 0 ? 'Nie mogę połączyć się z Luną — sprawdź internet i spróbuj jeszcze raz.' : err.message);
};
const grow = (ta) => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; };
const busy = (btn, on) => { btn.classList.toggle('busy', on); btn.disabled = on; };

// ---------- start ----------
async function start() {
  if (!getToken()) { $('#gate').hidden = false; return; }
  try {
    const { user } = await api.me();
    $('#who').textContent = user?.name ? `Cześć, ${user.name}` : '';
  } catch (err) {
    if (err.status === 401) { $('#gate').hidden = false; return; }
  }
  $('#desk').hidden = false;
  const src = $('#src');
  try { src.value = localStorage.getItem(DRAFT) || ''; } catch {}
  count(); src.focus();
  loadSoon();
}

// ---------- 1. materiał ----------
function count() {
  const n = $('#src').value.length;
  $('#count').textContent = `${n.toLocaleString('pl-PL')} / ${MAX.toLocaleString('pl-PL')}`;
  $('#count').classList.toggle('over', n > MAX);
  try { localStorage.setItem(DRAFT, $('#src').value); } catch {}
}
async function split() {
  const text = $('#src').value.trim();
  if (text.length < 3) { $('#src').focus(); return toast('Wklej albo napisz, co mam zapamiętać.'); }
  if (text.length > MAX) return toast('To za dużo naraz — podziel materiał na części (do 20 000 znaków).');
  const b = $('#split'); busy(b, true);
  const slow = setTimeout(() => toast('Czytam i rozdzielam — przy dłuższym materiale to kilkanaście sekund…'), 4000);
  try {
    const r = await api.split(text);
    if (!r.parts?.length) return toast(r.skipped ? 'Nie znalazłam tu nic do zapamiętania: ' + r.skipped : 'Nie znalazłam tu nic do zapamiętania.');
    showParts(r.parts, r.skipped);
  } catch (err) { fail(err); } finally { clearTimeout(slow); busy(b, false); }
}
async function saveOne() {
  const text = $('#src').value.trim();
  if (text.length < 3) { $('#src').focus(); return toast('Wklej albo napisz, co mam zapamiętać.'); }
  if (text.length > 1000) return toast('Jedna rzecz może mieć do 1000 znaków — dłuższy materiał rozbij na rzeczy.');
  showParts([{ text, from: '' }], '');
  saveAll();
}

// ---------- 2. przegląd ----------
function partRow(p) {
  const li = document.createElement('li'); li.className = 'part';
  li.innerHTML = `<textarea rows="1" aria-label="Rzecz do zapisania">${esc(p.text)}</textarea>
    <button type="button" class="x" aria-label="Usuń tę rzecz" title="Usuń">✕</button>
    ${p.from ? `<span class="from">z materiału: „${esc(p.from)}”</span>` : ''}`;
  return li;
}
function showParts(parts, skipped) {
  const ol = $('#parts'); ol.innerHTML = ''; ol.classList.remove('saving');
  parts.forEach((p) => ol.appendChild(partRow(p)));
  $('#skipped').hidden = !skipped; $('#skipped').textContent = !skipped ? '' : /^pomin/i.test(skipped) ? skipped : 'Pominęłam: ' + skipped;
  $('#rv-lead').textContent = 'Każda linijka to osobna rzecz. Popraw, co trzeba, usuń zbędne — zapiszę dopiero po „Zapisz wszystkie”.';
  $('#step-in').hidden = true; $('#step-review').hidden = false;
  $('#save-all').hidden = false; $('#add-part').hidden = false;
  ol.querySelectorAll('textarea').forEach(grow);
  retitle();
  $('#step-review').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function retitle() {
  const n = $('#parts').querySelectorAll('.part:not(.ok):not(.undone)').length;
  $('#rv-title').textContent = `Sprawdź, co zapiszę (${n})`;
  $('#save-all').textContent = n === 1 ? 'Zapisz' : `Zapisz wszystkie (${n})`;
  $('#save-all').disabled = !n;
}
function restart() {
  $('#step-review').hidden = true; $('#step-in').hidden = false; $('#src').focus();
}

// ---------- 3. zapis: każda rzecz zwykłym POST /api/items (po 2 naraz) ----------
async function saveAll() {
  const rows = [...$('#parts').querySelectorAll('.part:not(.ok):not(.undone)')];
  const todo = rows.map((li) => ({ li, text: li.querySelector('textarea')?.value.trim() || '' })).filter((x) => x.text.length >= 1);
  rows.filter((li) => !todo.some((x) => x.li === li)).forEach((li) => li.remove());
  if (!todo.length) return retitle();
  const b = $('#save-all'); busy(b, true); $('#parts').classList.add('saving');
  $('#rv-title').textContent = 'Zapisuję…';
  let ok = 0, bad = 0, i = 0;
  const worker = async () => {
    while (i < todo.length) {
      const { li, text } = todo[i++];
      li.className = 'part wait';
      li.innerHTML = `<div class="res"><p>${esc(text)}</p></div>`;
      try {
        const r = await api.add(text);
        ok++; fresh.add(r.item?.id);
        li.className = 'part ok';
        li.innerHTML = `<div class="res"><p>${esc(r.item?.spec?.understood || 'Zapisałam.')}<small>${esc(text)}</small></p>
          <button type="button" class="btn alt" data-undo="${esc(r.item?.id || '')}">Cofnij</button></div>`;
      } catch (err) {
        if (err.status === 401) return fail(err);
        bad++;
        li.className = 'part err';
        li.innerHTML = `<textarea rows="1" aria-label="Rzecz do zapisania">${esc(text)}</textarea>
          <button type="button" class="x" aria-label="Usuń tę rzecz" title="Usuń">✕</button>
          <span class="from">${esc(err.status === 0 ? 'Brak połączenia z Luną.' : err.message)} Popraw albo spróbuj jeszcze raz.</span>`;
        grow(li.querySelector('textarea'));
      }
    }
  };
  await Promise.all([worker(), worker()]);
  busy(b, false); $('#parts').classList.remove('saving');
  if (!bad) {
    $('#rv-title').textContent = ok === 1 ? 'Zapisałam' : `Zapisałam ${ok} rzeczy`;
    $('#rv-lead').textContent = 'Gotowe. Jeśli coś zrozumiałam źle, stuknij „Cofnij” — albo popraw to potem w Lunie.';
    b.hidden = true; $('#add-part').hidden = true;
    $('#src').value = ''; count();
    $('#restart').textContent = 'Wklej kolejny materiał';
  } else {
    retitle();
    $('#rv-lead').textContent = `Zapisałam ${ok}, ${bad} się nie udało — popraw je i kliknij „Zapisz” jeszcze raz.`;
  }
  loadSoon();
}
async function undo(btn) {
  const id = btn.dataset.undo; if (!id) return;
  busy(btn, true);
  try {
    await api.remove(id); fresh.delete(id);
    const li = btn.closest('.part'); li.className = 'part undone';
    li.querySelector('.res').innerHTML = `<p>Cofnięte — tego nie zapisałam.<small>${esc(li.querySelector('small')?.textContent || '')}</small></p>`;
    loadSoon();
  } catch (err) { busy(btn, false); fail(err); }
}

// ---------- boczna kolumna: najbliższe 30 dni ----------
const eventOf = (it) => { const s = it.spec?.event_at || it.next_at; return s ? new Date(s) : null; };
async function loadSoon() {
  const ul = $('#soon');
  let items = [];
  try { items = await api.items(); } catch (err) { ul.innerHTML = '<li class="muted">Nie udało się wczytać.</li>'; return; }
  const from = new Date(); from.setHours(0, 0, 0, 0); const to = from.getTime() + 30 * 864e5;
  const soon = items.map((it) => ({ it, ev: eventOf(it) })).filter((x) => x.ev && x.ev >= from && x.ev < to).sort((a, b) => a.ev - b.ev);
  const rest = items.length - soon.length;
  ul.innerHTML = (soon.length ? soon.slice(0, 40).map(({ it, ev }) => `<li class="${fresh.has(it.id) ? 'fresh' : ''}">
      <span class="d"><b>${esc(fDay(ev))}</b>${esc(fTime.format(ev))}</span><span class="t">${esc(it.title)}</span></li>`).join('')
    : '<li class="muted">Nic zaplanowanego w najbliższych 30 dniach.</li>')
    + (rest > 0 ? `<li class="muted">…i ${rest} bez terminu albo później — w Lunie.</li>` : '');
}

// ---------- zdarzenia ----------
$('#src').addEventListener('input', count);
$('#src').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); split(); } });
$('#split').addEventListener('click', split);
$('#one').addEventListener('click', saveOne);
$('#restart').addEventListener('click', () => { $('#restart').textContent = 'Zacznij od nowa'; restart(); });
$('#save-all').addEventListener('click', saveAll);
$('#add-part').addEventListener('click', () => {
  const li = partRow({ text: '', from: '' }); $('#parts').appendChild(li); li.querySelector('textarea').focus(); retitle();
});
$('#parts').addEventListener('input', (e) => { if (e.target.matches('textarea')) grow(e.target); });
$('#parts').addEventListener('click', (e) => {
  const x = e.target.closest('.x'); if (x) { x.closest('.part').remove(); return retitle(); }
  const u = e.target.closest('[data-undo]'); if (u) undo(u);
});
addEventListener('resize', () => $('#parts').querySelectorAll('textarea').forEach(grow));

start();
