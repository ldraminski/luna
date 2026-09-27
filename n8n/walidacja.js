// Sprawdza odpowiedź modelu; niczego nie zgaduje — przy błędzie zwraca ok:false z komunikatem.
const src = String($('POST items').first().json.body.text || '').trim().slice(0, 1000);
const fail = (error) => [{ json: { ok: false, error, notify: [], spec: {}, data: {}, source_text: src } }];

const raw = $json.choices?.[0]?.message?.content;
if (!raw) return fail('Model nie odpowiedział. Spróbuj jeszcze raz.');
let m;
try { m = JSON.parse(raw.replace(/^```(json)?|```$/g, '').trim()); } catch (e) { return fail('Nie zrozumiałem. Spróbuj napisać inaczej.'); }

const KINDS = ['reminder-once', 'reminder-recurring', 'page-summary', 'checklist', 'note'];
const kind = KINDS.includes(m.kind) ? m.kind : 'note';
const cut = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
const now = Date.now();
const iso = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t).toISOString() : null; };

let notify = (Array.isArray(m.notify) ? m.notify : [])
  .map((n) => ({ at: iso(n.at), title: cut(n.title, 50) || cut(m.title, 50), body: cut(n.body, 120) }))
  .filter((n) => n.at && Date.parse(n.at) > now - 60000 && Date.parse(n.at) < now + 400 * 864e5)
  .slice(0, 10);

let url = null;
if (kind === 'page-summary') {
  // Code node nie ma URL — prosta walidacja wyrażeniem.
  const u = String(m.url || '').trim();
  if (/^https?:\/\/[a-z0-9.-]+\.[a-z]{2,}(:\d+)?(\/\S*)?$/i.test(u)) url = u.slice(0, 500);
  if (!url) return fail('Nie widzę adresu strony. Podaj pełny link.');
}

const title = cut(m.title, 40) || src.slice(0, 40);
const rec = kind === 'reminder-recurring' && m.recurrence && Number(m.recurrence.every) > 0 &&
  ['day', 'week', 'month'].includes(m.recurrence.unit) ? {
    every: Math.min(Number(m.recurrence.every), 365), unit: m.recurrence.unit,
    lead: m.recurrence.lead && ['hour', 'day'].includes(m.recurrence.lead.unit)
      ? { value: Math.min(Number(m.recurrence.lead.value) || 0, 30), unit: m.recurrence.lead.unit } : null,
  } : null;
if (kind === 'reminder-recurring' && !rec) return fail('Nie rozumiem, co ile to powtarzać.');

return [{ json: {
  ok: true, kind, title, source_text: src, widget_slug: kind,
  spec: { understood: cut(m.understood, 300), event_at: iso(m.event_at), recurrence: rec, url, model: '__MODEL__' },
  data: {
    tip: cut(m.tip, 80) || null,
    checklist: kind === 'checklist' ? (Array.isArray(m.checklist) ? m.checklist : []).map((x) => ({ text: cut(String(x), 80), done: false })).filter((x) => x.text).slice(0, 30) : undefined,
  },
  notify,
} }];
