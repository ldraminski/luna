"""Buduje workflow n8n „Oboe: API” (etap 1: logowanie). Wynik: oboe-api.json."""
import json, uuid

PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"

# Wspólny fragment: kto jest zalogowany (sesja ważna, przedłużana przy użyciu).
ME = """me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id)"""
UNAUTH = "json_build_object('status', 401, 'error', 'Zaloguj się ponownie')"

ROUTES = [
  # (metoda, ścieżka, nazwa, SQL, parametry-wyrażenie)
  ("GET", "me", "Kim jestem", f"""
WITH {ME}
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE (SELECT json_build_object('status', 200, 'user', json_build_object('email', u.email, 'name', u.name))
        FROM users u WHERE u.id = (SELECT user_id FROM me)) END AS result""",
   "={{ [ " + TOKEN + " ] }}"),

  ("GET", "items", "Lista rzeczy", f"""
WITH {ME}
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE json_build_object('status', 200, 'items', coalesce((SELECT json_agg(t ORDER BY t.next_at NULLS LAST, t.created_at DESC) FROM (
    SELECT i.id, i.kind, i.title, i.source_text, i.spec, i.data, i.widget_slug, i.status, i.created_at,
      (SELECT min(n.due_at) FROM notifications n WHERE n.item_id = i.id AND n.sent_at IS NULL) AS next_at,
      coalesce((SELECT json_agg(n.due_at ORDER BY n.due_at) FROM notifications n
                WHERE n.item_id = i.id AND n.sent_at IS NULL), '[]'::json) AS notify_at
    FROM items i WHERE i.user_id = (SELECT user_id FROM me) AND i.status = 'active') t), '[]'::json)) END AS result""",
   "={{ [ " + TOKEN + " ] }}"),

  ("GET", "pending", "Do pokazania", f"""
WITH {ME},
p AS (
  UPDATE notifications SET shown_at = now()
  WHERE user_id = (SELECT user_id FROM me) AND sent_at IS NOT NULL AND shown_at IS NULL
    AND sent_at > now() - interval '1 day'
  RETURNING id, item_id, title, body, sent_at)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE json_build_object('status', 200, 'items',
       coalesce((SELECT json_agg(p ORDER BY p.sent_at DESC) FROM p), '[]'::json)) END AS result""",
   "={{ [ " + TOKEN + " ] }}"),

  # Endpoint dostaje od nas POST-a, więc wpuszczamy tylko znane usługi push (inaczej SSRF) — jak w Alertach.
  ("POST", "push/subscribe", "Zapisz urządzenie", f"""
WITH {ME},
ok AS (SELECT $2::text AS ep WHERE $2 ~ '^https://(web\\.push\\.apple\\.com|fcm\\.googleapis\\.com|updates\\.push\\.services\\.mozilla\\.com|[a-z0-9-]+\\.notify\\.windows\\.com)/'),
ins AS (
  INSERT INTO push_subscriptions (endpoint, user_id, p256dh, auth, user_agent)
  SELECT ep, (SELECT user_id FROM me), nullif($3, ''), nullif($4, ''), nullif($5, '') FROM ok WHERE EXISTS (SELECT 1 FROM me)
  ON CONFLICT (endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh, auth = excluded.auth,
    user_agent = excluded.user_agent, failures = 0
  RETURNING 1)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM ins) THEN json_build_object('status', 400, 'error', 'Nieznana usługa push')
  ELSE json_build_object('status', 200, 'ok', true) END AS result""",
   "={{ [ " + TOKEN + ", String($json.body.endpoint || '').slice(0, 1000), String(($json.body.keys || {}).p256dh || '').slice(0, 200), String(($json.body.keys || {}).auth || '').slice(0, 100), String($json.body.ua || '').slice(0, 400) ] }}"),

  ("POST", "push/unsubscribe", "Usuń urządzenie", f"""
WITH {ME},
d AS (DELETE FROM push_subscriptions WHERE endpoint = $2 AND user_id = (SELECT user_id FROM me) RETURNING 1)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE json_build_object('status', 200, 'ok', true) END AS result""",
   "={{ [ " + TOKEN + ", String($json.body.endpoint || '').slice(0, 1000) ] }}"),

  ("POST", "items/done", "Odhacz", f"""
WITH {ME},
upd AS (UPDATE items SET status = 'done', updated_at = now()
        WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) RETURNING id),
cancel AS (DELETE FROM notifications WHERE item_id IN (SELECT id FROM upd) AND sent_at IS NULL RETURNING 1)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM upd) THEN json_build_object('status', 404, 'error', 'Nie ma takiej rzeczy')
  ELSE json_build_object('status', 200, 'ok', true) END AS result""",
   "={{ [ " + TOKEN + ", /^[0-9a-f-]{36}$/i.test($json.body.id || '') ? $json.body.id : '00000000-0000-0000-0000-000000000000' ] }}"),

  ("POST", "items/check", "Odhacz pozycję", f"""
WITH {ME},
upd AS (
  UPDATE items SET updated_at = now(),
    data = jsonb_set(data, ARRAY['checklist', $3::text, 'done'], to_jsonb($4::boolean))
  WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me)
    AND jsonb_typeof(data->'checklist') = 'array' AND $3::int < jsonb_array_length(data->'checklist')
  RETURNING data)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM upd) THEN json_build_object('status', 404, 'error', 'Nie ma takiej pozycji')
  ELSE json_build_object('status', 200, 'data', (SELECT data FROM upd)) END AS result""",
   "={{ [ " + TOKEN + ", /^[0-9a-f-]{36}$/i.test($json.body.id || '') ? $json.body.id : '00000000-0000-0000-0000-000000000000', String(Math.max(0, Math.min(99, parseInt($json.body.index, 10) || 0))), $json.body.done === true ] }}"),

  # Widget zapisuje swój stan (max 20 KB) — tylko do rzeczy z gotowym widgetem.
  ("POST", "items/widget-state", "Stan widgetu", f"""
WITH {ME},
upd AS (
  UPDATE items SET updated_at = now(), data = jsonb_set(data, '{{widget,state}}', $3::jsonb)
  WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) AND data->'widget'->>'status' = 'ready'
    AND length($3) <= 20000 AND jsonb_typeof($3::jsonb) = 'object'
  RETURNING 1)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM upd) THEN json_build_object('status', 400, 'error', 'Nie udało się zapisać danych widgetu')
  ELSE json_build_object('status', 200, 'ok', true) END AS result""",
   "={{ [ " + TOKEN + ", /^[0-9a-f-]{36}$/i.test($json.body.id || '') ? $json.body.id : '00000000-0000-0000-0000-000000000000', JSON.stringify($json.body.state && typeof $json.body.state === 'object' ? $json.body.state : null).slice(0, 20001) ] }}"),

  ("POST", "items/delete", "Usuń", f"""
WITH {ME},
d AS (DELETE FROM items WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) RETURNING id)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM d) THEN json_build_object('status', 404, 'error', 'Nie ma takiej rzeczy')
  ELSE json_build_object('status', 200, 'ok', true) END AS result""",
   "={{ [ " + TOKEN + ", /^[0-9a-f-]{36}$/i.test($json.body.id || '') ? $json.body.id : '00000000-0000-0000-0000-000000000000' ] }}"),
]

nodes, conns = [], {}
nodes.append({"id": str(uuid.uuid4()), "name": "Opis", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
  "position": [-400, -200], "parameters": {"width": 520, "height": 220, "content":
  "## Oboe: API\nFront `oboe` (nginx) proxuje `/api/*` → `/webhook/oboe/*`.\n"
  "Autoryzacja: `Authorization: Bearer <token>`; w bazie tylko sha256 tokenu.\n"
  "Bez haseł: token wydaje admin (`POST /webhook/oboe/admin/token`, X-Admin-Token), mailem albo ręcznie.\n"
  "Każdy SQL zwraca `result` z polem `status` → kod HTTP odpowiedzi.\n"
  "Źródło: `~/Work/oboe/n8n/build_api.py`."}})
for i, (method, path, name, sql, params) in enumerate(ROUTES):
    y = i * 200
    wh, q, r = f"{method} {path}", name, f"Odpowiedz: {name}"
    nodes += [
      {"id": str(uuid.uuid4()), "name": wh, "type": "n8n-nodes-base.webhook", "typeVersion": 2,
       "position": [0, y], "webhookId": str(uuid.uuid4()),
       "parameters": {"httpMethod": method, "path": f"oboe/{path}", "responseMode": "responseNode", "options": {}}},
      {"id": str(uuid.uuid4()), "name": q, "type": "n8n-nodes-base.postgres", "typeVersion": 2.6,
       "position": [240, y], "credentials": PG, "alwaysOutputData": False,
       "parameters": {"operation": "executeQuery", "query": sql.strip(), "options": {"queryReplacement": params}}},
      {"id": str(uuid.uuid4()), "name": r, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
       "position": [480, y],
       "parameters": {"respondWith": "json", "responseBody": "={{ $json.result }}",
                      "options": {"responseCode": "={{ $json.result.status || 200 }}"}}},
    ]
    conns[wh] = {"main": [[{"node": q, "type": "main", "index": 0}]]}
    conns[q] = {"main": [[{"node": r, "type": "main", "index": 0}]]}


# ---- POST items: zdanie użytkownika → DeepSeek → rzecz + zaplanowane powiadomienia ----
SYSTEM = open("prompt-rozumienie.txt").read()
MODEL = "deepseek/deepseek-v4.1-flash"
WIDGETS_WF = open(".widgets-wf-id").read().strip()  # id „Oboe: Generuj widget” w n8n
USER_MSG = ("'Teraz jest: ' + $json.teraz + '\\n\\nKalendarz (używaj WYŁĄCZNIE tych dat):\\n' + $json.kalendarz"
            " + '\\n\\nZdanie użytkownika:\\n' + String($('POST items').item.json.body.text).trim().slice(0, 1000)")
JSON_BODY = ("={{ JSON.stringify({ model: '" + MODEL + "', temperature: 0.2, max_tokens: 1200, reasoning: { enabled: false }, "
             "response_format: { type: 'json_object' }, messages: [ { role: 'system', content: " + json.dumps(SYSTEM, ensure_ascii=False)
             + " }, { role: 'user', content: " + USER_MSG + " } ] }) }}")
assert "{{" not in SYSTEM and "}}" not in SYSTEM, "n8n: {{ }} w prompcie psuje wyrażenie"
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

y = len(ROUTES) * 200 + 100
w = node("POST items", "n8n-nodes-base.webhook", 2, [0, y],
  {"httpMethod": "POST", "path": "oboe/items", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4()))
sess = node("Sesja", "n8n-nodes-base.postgres", 2.6, [220, y],
  {"operation": "executeQuery", "query": f"WITH {ME}\nSELECT (SELECT user_id FROM me) AS user_id",
   "options": {"queryReplacement": "={{ [ " + TOKEN + " ] }}"}}, credentials=PG)
iff = node("Zalogowany i jest tekst?", "n8n-nodes-base.if", 2.2, [440, y], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [
      {"id": str(uuid.uuid4()), "leftValue": "={{ $json.user_id }}", "rightValue": "",
       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}},
      {"id": str(uuid.uuid4()), "leftValue": "={{ String($('POST items').item.json.body.text || '').trim() }}", "rightValue": "",
       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
deny = node("Odmów", "n8n-nodes-base.respondToWebhook", 1.1, [660, y + 180],
  {"respondWith": "json", "options": {"responseCode": "={{ $json.user_id ? 400 : 401 }}"},
   "responseBody": "={{ $json.user_id ? { status: 400, error: 'Napisz, co zapamiętać' } : { status: 401, error: 'Zaloguj się ponownie' } }}"})
cal = node("Kalendarz", "n8n-nodes-base.code", 2, [660, y], {"jsCode": open("kalendarz.js").read()})
llm = node("DeepSeek: zrozum", "n8n-nodes-base.httpRequest", 4.2, [880, y], {
  "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
  "sendHeaders": True, "headerParameters": {"parameters": [
    {"name": "HTTP-Referer", "value": "https://draminski.dev"}, {"name": "X-Title", "value": "Oboe (n8n)"}]},
  "sendBody": True, "specifyBody": "json",
  "jsonBody": JSON_BODY,
  "options": {"timeout": 60000}},
  credentials={"openRouterApi": {"id": "kv8oGsmY1JN14X0m", "name": "OpenRouter account"}},
  retryOnFail=True, maxTries=2, onError="continueRegularOutput")
code = node("Sprawdź odpowiedź", "n8n-nodes-base.code", 2, [1100, y], {"jsCode": open("walidacja.js").read().replace("__MODEL__", MODEL)})
save = node("Zapisz", "n8n-nodes-base.postgres", 2.6, [1320, y], {"operation": "executeQuery", "query": """
WITH it AS (
  INSERT INTO items (user_id, kind, source_text, title, spec, widget_slug, data)
  SELECT $1::uuid, $2, $3, $4, $5::jsonb, $6, $7::jsonb WHERE $8::boolean
  RETURNING *),
nt AS (
  INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)
  SELECT it.id, it.user_id, x.at, coalesce(x.channels, '{push}'), x.title, x.body
  FROM it, jsonb_to_recordset($9::jsonb) AS x(at timestamptz, title text, body text, channels text[])
  RETURNING due_at)
SELECT CASE WHEN NOT $8::boolean THEN json_build_object('status', 422, 'error', $10::text)
  ELSE json_build_object('status', 200, 'item', (SELECT row_to_json(it) FROM it),
       'notifications', coalesce((SELECT json_agg(due_at ORDER BY due_at) FROM nt), '[]'::json)) END AS result""".strip(),
  "options": {"queryReplacement": "={{ [ $('Sesja').item.json.user_id, $json.kind, $json.source_text, $json.title, JSON.stringify($json.spec), $json.widget_slug, JSON.stringify($json.data), $json.ok, JSON.stringify($json.notify), $json.error || '' ] }}"}},
  credentials=PG)
resp = node("Odpowiedz: dodano", "n8n-nodes-base.respondToWebhook", 1.1, [1540, y],
  {"respondWith": "json", "responseBody": "={{ $json.result }}", "options": {"responseCode": "={{ $json.result.status || 200 }}"}})
wneed = node("Potrzebny widget?", "n8n-nodes-base.if", 2.2, [1760, y], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.result.status === 200 && !!(($json.result.item || {}).data || {}).widget }}",
      "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}})
wgen = node("Generuj widget (w tle)", "n8n-nodes-base.executeWorkflow", 1.2, [1980, y], {
  "source": "database", "workflowId": {"__rl": True, "value": WIDGETS_WF, "mode": "id"},
  "options": {"waitForSubWorkflow": False}})
wset = node("Id rzeczy", "n8n-nodes-base.set", 3.4, [1870, y], {"mode": "manual", "includeOtherFields": False,
  "assignments": {"assignments": [{"id": str(uuid.uuid4()), "name": "item_id", "type": "string", "value": "={{ $json.result.item.id }}"}]}, "options": {}})
link(resp, wneed); link(wneed, wset, 0); link(wset, wgen)
link(w, sess); link(sess, iff); link(iff, cal, 0); link(cal, llm); link(iff, deny, 1); link(llm, code); link(code, save); link(save, resp)

wf = {"name": "Oboe: API", "nodes": nodes, "connections": conns,
      "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}}
json.dump(wf, open("oboe-api.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
