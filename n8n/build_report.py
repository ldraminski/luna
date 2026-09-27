"""Buduje workflow n8n „Oboe: Raport” — raport dzienny (dziś + jutro) i w poniedziałek tygodniowy. Wynik: oboe-report.json.

Co 5 min: użytkownicy, którym wypadła godzina raportu (users.report_time, domyślnie 9:00; okno 4 h), a nie mają raportu na dziś.
Lista rzeczy liczona KODEM z bazy (nic nie zmyśla), DeepSeek pisze tylko wstęp, rady „przygotuj się” i treść powiadomienia.
Ręcznie (test / ponowienie): POST /webhook/oboe/admin/report {email, weekly?} z X-Admin-Token — tylko z serwera.
"""
import json, uuid
PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
ADMIN = {"httpHeaderAuth": {"id": "9Rd7Zl7NxIcEvPtL", "name": "Oboe - admin (X-Admin-Token)"}}
OR = {"openRouterApi": {"id": "ZGSl0yv59gDWZKJG", "name": "OpenRouter - Luna"}}
MODEL = "deepseek/deepseek-v4.1-flash"
SYSTEM = open("prompt-raport.txt").read(); assert "{{" not in SYSTEM and "}}" not in SYSTEM
nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-420, -300], {"width": 620, "height": 250, "content":
  "## Oboe: Raport (Luna)\nCo 5 min: komu wypadła godzina raportu (`users.report_time`, domyślnie 9:00, okno 4 h) i nie ma raportu na dziś.\n"
  "Pon = raport tygodnia, inne dni = dziś + jutro. Plan liczy KOD (występowania cyklicznych jak w aplikacji), "
  "DeepSeek pisze tylko wstęp, rady i powiadomienie. Zapis: `reports` + powiadomienie push (item_id NULL) przez Harmonogram.\n"
  "Ręcznie: `POST /webhook/oboe/admin/report {email, weekly}` (X-Admin-Token, tylko z serwera).\nŹródło: `~/Work/oboe/n8n/build_report.py`."})
cron = node("Co 5 minut", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0], {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}})
hook = node("POST admin/report", "n8n-nodes-base.webhook", 2, [0, 200],
  {"httpMethod": "POST", "path": "oboe/admin/report", "authentication": "headerAuth", "responseMode": "lastNode", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
par = node("Parametry", "n8n-nodes-base.code", 2, [220, 100], {"jsCode":
  "const b = $json.body || {};\nreturn [{ json: { email: String(b.email || '').trim().toLowerCase().slice(0, 200), weekly: b.weekly === true } }];"})
who = node("Komu raport", "n8n-nodes-base.postgres", 2.6, [440, 100], {"operation": "executeQuery", "query": """
WITH n AS (SELECT (now() AT TIME ZONE 'Europe/Warsaw') AS t),
u AS (SELECT u.* FROM users u, n WHERE
   ($1 <> '' AND u.email = $1)
   OR ($1 = '' AND u.report_enabled AND n.t::time >= u.report_time AND n.t::time < u.report_time + interval '4 hours'
       AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.user_id = u.id AND r.for_date = n.t::date)
       AND EXISTS (SELECT 1 FROM sessions s WHERE s.user_id = u.id))
   LIMIT 20)
SELECT u.id AS user_id, coalesce(u.name, '') AS name, $2::boolean AS force_weekly,
  coalesce((SELECT json_agg(json_build_object('id', i.id, 'title', i.title, 'kind', i.kind, 'spec', i.spec, 'lists', i.data->'lists',
      'next_at', (SELECT min(x.due_at) FROM notifications x WHERE x.item_id = i.id AND x.sent_at IS NULL)))
    FROM items i WHERE i.user_id = u.id AND i.status = 'active'), '[]'::json) AS items
FROM u""".strip(), "options": {"queryReplacement": "={{ [ $json.email, $json.weekly ] }}"}}, credentials=PG)
plan = node("Ułóż plan", "n8n-nodes-base.code", 2, [660, 100], {"jsCode": open("raport-plan.js").read()})
llm = node("DeepSeek: wstęp", "n8n-nodes-base.httpRequest", 4.2, [880, 100], {
  "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
  "sendHeaders": True, "headerParameters": {"parameters": [{"name": "HTTP-Referer", "value": "https://draminski.dev"}, {"name": "X-Title", "value": "Oboe raport (n8n)"}]},
  "sendBody": True, "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({ model: '" + MODEL + "', temperature: 0.3, max_tokens: 700, reasoning: { enabled: false }, response_format: { type: 'json_object' }, "
    "messages: [ { role: 'system', content: " + json.dumps(SYSTEM, ensure_ascii=False) + " }, { role: 'user', content: 'PLAN (dane):\\n' + $json.facts } ] }) }}",
  "options": {"timeout": 60000}}, credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
merge = node("Dołącz wstęp", "n8n-nodes-base.code", 2, [1100, 100], {"jsCode": r"""// Łączy plan (kod) z wstępem (model) — po indeksie; bez odpowiedzi modelu raport i tak powstaje.
const plans = $('Ułóż plan').all();
return $input.all().map((it, i) => {
  const p = plans[i].json; let m = {};
  try { m = JSON.parse(String(it.json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); } catch (e) {}
  const cut = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
  const content = { ...p.content, intro: cut(m.intro, 400) || p.fallback, prep: (Array.isArray(m.prep) ? m.prep : []).map((x) => cut(x, 200)).filter(Boolean).slice(0, 3),
    overdue_ask: p.content.overdue.length ? (cut(m.overdue_ask, 400) || 'Te rzeczy są po terminie i nie są odhaczone. Jeśli to już nieaktualne, mogę je zamknąć.') : '' };
  return { json: { user_id: p.user_id, kind: p.kind, for_date: p.for_date, content, push_title: p.push_title, push_body: cut(m.push, 110) || cut(content.intro, 110) } };
});"""})
save = node("Zapisz raport", "n8n-nodes-base.postgres", 2.6, [1320, 100], {"operation": "executeQuery", "query": """
WITH r AS (
  INSERT INTO reports (user_id, kind, for_date, content) VALUES ($1::uuid, $2, $3::date, $4::jsonb)
  ON CONFLICT (user_id, for_date) DO UPDATE SET kind = EXCLUDED.kind, content = EXCLUDED.content, created_at = now(), seen_at = NULL
  RETURNING id),
nt AS (INSERT INTO notifications (item_id, user_id, due_at, channels, title, body) VALUES (NULL, $1::uuid, now(), '{push}', $5, $6) RETURNING 1),
-- przypomnienie o zaległych: osobne powiadomienie, dopóki są nierozwiązane (w aplikacji — karta od dołu)
ov AS (INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)
       SELECT NULL, $1::uuid, now() + interval '1 minute', '{push}', $7, 'Wykonaj je albo oznacz jako zakończone — inaczej będę ci ciągle przypominać.'
       WHERE $7 <> '' RETURNING 1)
SELECT (SELECT id FROM r) AS report_id, $2 AS kind, $3 AS for_date, (SELECT count(*) FROM nt) + (SELECT count(*) FROM ov) AS notified""".strip(),
  "options": {"queryReplacement": "={{ [ $json.user_id, $json.kind, $json.for_date, JSON.stringify($json.content), $json.push_title, $json.push_body, (n => !n ? '' : 'Masz ' + n + ' ' + (n === 1 ? 'przeterminowaną rzecz' : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) ? 'przeterminowane rzeczy' : 'przeterminowanych rzeczy'))(($json.content.overdue || []).length) ] }}"}}, credentials=PG)
link(cron, par); link(hook, par); link(par, who); link(who, plan); link(plan, llm); link(llm, merge); link(merge, save)
json.dump({"name": "Oboe: Raport", "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-report.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
