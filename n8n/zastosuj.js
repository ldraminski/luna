// „Zrób to” w czacie Popraw: wprowadza plan z rozmowy do rzeczy. Niczego nie zgaduje — każda zmiana jest walidowana,
// a to, czego nie da się bezpiecznie zastosować, jest pomijane. Widget na zamówienie idzie osobno (w tle).
const r = $json.result; const p = r.proposal || {}; const ch = p.changes || {}; const it = r.item;
const cut = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
const iso = (v) => { const t = Date.parse(v); return Number.isFinite(t) ? new Date(t).toISOString() : null; };
const now = Date.now();
const spec = { ...(it.spec || {}) }; const data = { ...(it.data || {}) };
const title = cut(ch.title, 40) || it.title;

// termin, powtarzanie, przypomnienia — tylko gdy plan je zmienia (wtedy cały nowy zestaw przypomnień)
let notify = []; let replace = false;
if (ch.when && typeof ch.when === 'object') {
  replace = true;
  spec.event_at = iso(ch.when.event_at);
  const rc = ch.when.recurrence;
  spec.recurrence = rc && Number(rc.every) > 0 && ['day', 'week', 'month'].includes(rc.unit)
    ? { every: Math.min(Math.round(Number(rc.every)), 365), unit: rc.unit } : null;
  notify = (Array.isArray(ch.when.notify) ? ch.when.notify : [])
    .map((n) => ({ at: iso(n.at), title: cut(n.title, 50) || title.slice(0, 50), body: cut(n.body, 120) }))
    .filter((n) => n.at && Date.parse(n.at) > now - 60000 && Date.parse(n.at) < now + 400 * 864e5).slice(0, 10);
}

// listy z nazwami
const norm = (s) => String(s || '').trim().toLowerCase();
const item = (t) => ({ text: cut(String(t ?? ''), 80), done: false });
let lists = (Array.isArray(data.lists) ? data.lists : []).map((l) => ({ name: l.name ?? null, reset: !!l.reset, items: [...(l.items || [])] }));
for (const op of Array.isArray(ch.lists) ? ch.lists : []) {
  if (!op || typeof op !== 'object') continue;
  if (op.op === 'add') {
    const items = (Array.isArray(op.items) ? op.items : []).map(item).filter((x) => x.text).slice(0, 40);
    if (items.length && lists.length < 10) lists.push({ name: cut(op.name, 40) || null, reset: op.reset === true, items });
  } else if (op.op === 'edit' || op.op === 'delete') {
    const L = lists[Number(op.list)]; if (!L) continue;
    if (op.op === 'delete') { L.deleted = true; continue; }
    if (typeof op.name === 'string' && op.name.trim()) L.name = cut(op.name, 40);
    if (typeof op.reset === 'boolean') L.reset = op.reset;
    const rm = new Set((Array.isArray(op.remove) ? op.remove : []).map(norm));
    L.items = L.items.filter((x) => !rm.has(norm(x.text)));
    for (const rn of Array.isArray(op.rename) ? op.rename : []) {
      const x = L.items.find((y) => norm(y.text) === norm(rn?.from)); if (x && cut(rn?.to, 80)) x.text = cut(rn.to, 80);
    }
    for (const t of Array.isArray(op.add) ? op.add : []) { const x = item(t); if (x.text && L.items.length < 40) L.items.push(x); }
  }
}
lists = lists.filter((l) => !l.deleted && l.items.length);
if (lists.length) data.lists = lists; else delete data.lists;
if (!spec.recurrence) data.lists?.forEach((l) => { l.reset = false; });

// szczegóły i wygląd
if (Array.isArray(ch.fields)) data.fields = ch.fields.map((f) => ({ label: cut(f?.label, 20), value: cut(String(f?.value ?? ''), 60) })).filter((f) => f.label && f.value).slice(0, 4);
const TINTS = ['lavender', 'mint', 'blue', 'pink', 'sky'];
const ICONS = ['clock', 'cycle', 'list', 'globe', 'note', 'building', 'tv', 'health', 'car', 'home', 'cart', 'work', 'money', 'sport', 'people', 'doc', 'food', 'travel'];
if (ch.look && typeof ch.look === 'object') data.look = { tint: TINTS.includes(ch.look.tint) ? ch.look.tint : data.look?.tint, icon: ICONS.includes(ch.look.icon) ? ch.look.icon : data.look?.icon };

// widget na zamówienie: usunięcie albo przebudowa (w tle, stary działa do czasu podmiany)
if (ch.widget_remove === true && !p.widget) { delete data.widget; delete spec.widget_brief; }
if (p.widget) {
  const w = data.widget || {};
  data.widget = w.slug ? { ...w, pending: true } : { status: 'generating' };
  delete data.widget.revision_error;
}

const timed = spec.event_at || (replace ? notify.length > 0 : it.kind === 'reminder-once');
const kind = spec.recurrence ? 'reminder-recurring' : timed ? 'reminder-once' : lists.length ? 'checklist' : spec.url ? 'page-summary' : 'note';
const done = 'Zrobione ✓' + (p.widget ? ' Widget przebudowuję w tle — stary działa do czasu podmiany.' : '');
return [{ json: { item_id: it.id, chat_id: r.chat_id, title, kind, spec, data, notify, replace_notify: replace, done, widget: !!p.widget } }];
