// Sprawdza odpowiedź modelu; niczego nie zgaduje — przy błędzie zwraca ok:false z komunikatem.
// Rzecz składa się z części (termin, lista, strona, szczegóły); `kind` to tylko część główna — do sortowania i sekcji.
const src = String($('POST items').first().json.body.text || '').trim().slice(0, 1000) || '📷 Zdjęcie';
const fail = (error) => [{ json: { ok: false, error, notify: [], spec: {}, data: {}, source_text: src } }];

const raw = $json.choices?.[0]?.message?.content;
if (!raw) return fail('Model nie odpowiedział. Spróbuj jeszcze raz.');
let m;
try { m = JSON.parse(raw.replace(/^```(json)?|```$/g, '').trim()); } catch (e) { return fail('Nie zrozumiałem. Spróbuj napisać inaczej.'); }

const cut = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
const now = Date.now();
const iso = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t).toISOString() : null; };

const notify = (Array.isArray(m.notify) ? m.notify : [])
  .map((n) => ({ at: iso(n.at), title: cut(n.title, 50) || cut(m.title, 50), body: cut(n.body, 120) }))
  .filter((n) => n.at && Date.parse(n.at) > now - 60000 && Date.parse(n.at) < now + 400 * 864e5)
  .slice(0, 10);

const r = m.recurrence;
const recurrence = r && Number(r.every) > 0 && ['day', 'week', 'month'].includes(r.unit)
  ? { every: Math.min(Math.round(Number(r.every)), 365), unit: r.unit } : null;

// Code node nie ma URL — prosta walidacja wyrażeniem.
const u = String(m.url || '').trim();
const url = /^https?:\/\/[a-z0-9.-]+\.[a-z]{2,}(:\d+)?(\/\S*)?$/i.test(u) ? u.slice(0, 500) : null;

const checklist = (Array.isArray(m.checklist) ? m.checklist : [])
  .map((x) => ({ text: cut(String(x), 80), done: false })).filter((x) => x.text).slice(0, 30);
const fields = (Array.isArray(m.fields) ? m.fields : [])
  .map((f) => ({ label: cut(f?.label, 20), value: cut(String(f?.value ?? ''), 60) })).filter((f) => f.label && f.value).slice(0, 4);

const TINTS = ['lavender', 'mint', 'blue', 'pink', 'sky'];
const ICONS = ['clock', 'cycle', 'list', 'globe', 'note', 'building', 'tv', 'health', 'car', 'home', 'cart', 'work', 'money', 'sport', 'people', 'doc', 'food', 'travel'];
const event_at = iso(m.event_at);

const kind = recurrence ? 'reminder-recurring' : event_at || notify.length ? 'reminder-once'
  : checklist.length ? 'checklist' : url ? 'page-summary' : 'note';
const look = {
  tint: TINTS.includes(m.look?.tint) ? m.look.tint : { 'reminder-recurring': 'mint', checklist: 'pink', 'page-summary': 'blue' }[kind] || 'lavender',
  icon: ICONS.includes(m.look?.icon) ? m.look.icon : { 'reminder-recurring': 'cycle', checklist: 'list', 'page-summary': 'globe', note: 'note' }[kind] || 'clock',
};

return [{ json: {
  ok: true, kind, title: cut(m.title, 40) || src.slice(0, 40), source_text: src, widget_slug: kind,
  spec: { understood: cut(m.understood, 300), event_at, recurrence, url, summarize: m.summarize === true && !!url, model: '__MODEL__',
    widget_brief: cut(m.widget?.brief, 300) || undefined },
  data: {
    tip: cut(m.tip, 80) || null, look, fields,
    widget: m.widget?.brief ? { status: 'generating' } : undefined,
    // listy z nazwami (Popraw może dołożyć kolejne); z jednego zdania powstaje najwyżej jedna, bez nazwy
    photo: (() => { try { return $('Wejście do modelu').first().json.photo || undefined; } catch (e) { return undefined; } })(),   // opis zdjęcia, jeśli było
    lists: checklist.length ? [{ name: null, items: checklist, reset: !!(recurrence && m.checklist_reset !== false) }] : undefined,
  },
  notify,
  research: cut(m.research?.query, 200) || null,   // tylko sterowanie przepływem — nie trafia do bazy
} }];
