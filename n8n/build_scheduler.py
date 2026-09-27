"""Buduje workflow n8n „Oboe: Harmonogram” — co minutę wysyła zaległe powiadomienia. Wynik: oboe-scheduler.json.

Push jak w Alertach: BEZ treści (Code node nie ma crypto), telefon pobiera ją z /api/pending.
Klucz VAPID wspólny z Alertami (credential „Alerty VAPID”) — front Oboe subskrybuje tym samym kluczem publicznym.
Mail: gdy powiadomienie ma kanał 'email' ALBO osoba nie ma żadnego działającego urządzenia z pushem.
"""
import json, uuid

PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
SMTP = {"smtp": {"id": "DY5t4HkHVBfxB2gY", "name": "SMTP n8n renlab"}}
VAPID_CRED = {"crypto": {"id": "INg6KASgJTytqlBu", "name": "Alerty VAPID (klucz podpisu Web Push)"}}
VAPID_PUB = "BCsLF3E2-p-L9Cpw_smlVGOtpdBEXgDJKEyexxG28crg4SiZkqoFbAuJAlEKOS5YyMVpdw_ISLaWMtbBTqwpYA4"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-420, -320], {"width": 600, "height": 280, "content":
  "## Oboe: Harmonogram\nCo minutę: bierze zaległe powiadomienia (`sent_at IS NULL AND due_at <= now()`), od razu oznacza je jako wysłane "
  "(najwyżej raz — lepiej zgubić niż wysłać dwa razy), a dla cyklicznych planuje następne (+ `oboe_period(spec)`).\n\n"
  "**Push** bez treści, jak w Alertach — telefon pobiera ją z `/api/pending`. Jeden push na urządzenie na przebieg.\n"
  "**Mail** gdy kanał `email` albo osoba nie ma działającego urządzenia z pushem.\n"
  "Źródło: `~/Work/oboe/n8n/build_scheduler.py`."})
t = node("Co minutę", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0],
  {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}})
claim = node("Weź zaległe", "n8n-nodes-base.postgres", 2.6, [220, 0], {"operation": "executeQuery", "query": """
WITH due AS (
  SELECT id FROM notifications WHERE sent_at IS NULL AND due_at <= now()
  ORDER BY due_at LIMIT 100 FOR UPDATE SKIP LOCKED),
claimed AS (
  UPDATE notifications n SET sent_at = now() FROM due WHERE n.id = due.id RETURNING n.*),
rec AS (
  SELECT DISTINCT ON (c.item_id) c.*, i.spec FROM claimed c JOIN items i ON i.id = c.item_id
  WHERE i.status = 'active' AND oboe_period(i.spec) IS NOT NULL
    -- CTE widzą stan sprzed UPDATE w claimed, więc właśnie wzięte trzeba wykluczyć jawnie
    AND NOT EXISTS (SELECT 1 FROM notifications x WHERE x.item_id = c.item_id AND x.sent_at IS NULL
                    AND x.id NOT IN (SELECT id FROM claimed))
  ORDER BY c.item_id, c.due_at DESC),
nxt AS (
  INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)
  SELECT item_id, user_id, due_at + oboe_period(spec), channels, title, body FROM rec RETURNING item_id),
ev AS (
  -- następne wystąpienie: przesuń termin, a listę odnawianą (checklist_reset) wyczyść na nowy cykl
  UPDATE items i SET updated_at = now(),
    spec = CASE WHEN i.spec->>'event_at' IS NULL THEN i.spec ELSE
      jsonb_set(i.spec, '{event_at}', to_jsonb(to_char(((i.spec->>'event_at')::timestamptz + oboe_period(i.spec)) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))) END,
    data = CASE WHEN (i.data->>'checklist_reset')::boolean IS TRUE AND jsonb_typeof(i.data->'checklist') = 'array' THEN
      jsonb_set(i.data, '{checklist}', (SELECT coalesce(jsonb_agg(x || '{"done": false}'::jsonb), '[]'::jsonb) FROM jsonb_array_elements(i.data->'checklist') x))
      ELSE i.data END
  WHERE i.id IN (SELECT item_id FROM nxt)
  RETURNING 1)
SELECT c.id, c.user_id, c.item_id, c.title, coalesce(c.body, '') AS body, u.email, coalesce(u.name, '') AS name,
  ('email' = ANY(c.channels) OR NOT EXISTS (
     SELECT 1 FROM push_subscriptions s WHERE s.user_id = c.user_id AND s.failures < 3))
    AND NOT coalesce((i.spec->>'summarize')::boolean, false) AS send_email,
  ('push' = ANY(c.channels)) AND NOT coalesce((i.spec->>'summarize')::boolean, false) AS send_push,
  coalesce((i.spec->>'summarize')::boolean, false) AS summarize,
  (SELECT count(*) FROM ev) AS next_planned
FROM claimed c JOIN users u ON u.id = c.user_id LEFT JOIN items i ON i.id = c.item_id
ORDER BY c.due_at""".strip(), "options": {}}, credentials=PG)

# --- mail
fm = node("Tylko mail", "n8n-nodes-base.filter", 2.2, [460, -140], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.send_email }}", "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}})
mail = node("Wyślij mail", "n8n-nodes-base.emailSend", 2.1, [680, -140], {
  "fromEmail": "Oboe <n8n@renlab.ovh>", "toEmail": "={{ $json.email }}", "subject": "={{ '⏰ ' + $json.title }}",
  "emailFormat": "text", "text": "={{ ($json.body ? $json.body + '\\n\\n' : '') + '— Oboe' }}",
  "options": {"appendAttribution": False}}, credentials=SMTP, onError="continueRegularOutput")
mark = node("Oznacz wysłane mailem", "n8n-nodes-base.postgres", 2.6, [900, -140], {"operation": "executeQuery",
  "query": "UPDATE notifications SET emailed = true, error = CASE WHEN $2 = '' THEN error ELSE left($2, 300) END WHERE id = $1",
  "options": {"queryReplacement": "={{ [ $('Tylko mail').item.json.id, $json.error ? String($json.error.message || $json.error) : '' ] }}"}},
  credentials=PG)

# --- push: jeden na urządzenie na przebieg
subs = node("Urządzenia", "n8n-nodes-base.postgres", 2.6, [460, 140], {"operation": "executeQuery",
  "query": "SELECT endpoint FROM push_subscriptions WHERE user_id = ANY($1::uuid[]) AND failures < 10",
  "options": {"queryReplacement": "={{ [ '{' + [...new Set($('Weź zaległe').all().filter(i => i.json.send_push).map(i => i.json.user_id))].join(',') + '}' ] }}"}},
  credentials=PG, executeOnce=True)
jwt = node("Podpisz JWT", "n8n-nodes-base.code", 2, [680, 140], {"jsCode":
  "// Nagłówek VAPID (RFC 8292): JWT ES256 z aud = origin usługi push. Podpis robi węzeł Crypto.\n"
  "const b64u = (s) => Buffer.from(s).toString('base64').replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');\n"
  "return $input.all().filter((it) => it.json.endpoint).map((it) => {\n"
  "  const aud = (it.json.endpoint.match(/^https:\\/\\/[^/]+/) || [''])[0];\n"
  "  const header = b64u(JSON.stringify({ typ: 'JWT', alg: 'ES256' }));\n"
  "  const payload = b64u(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 3600, sub: 'https://push.draminski.dev' }));\n"
  "  return { json: { endpoint: it.json.endpoint, unsigned: header + '.' + payload } };\n"
  "});"})
sign = node("Podpis ES256", "n8n-nodes-base.crypto", 2, [900, 140],
  {"action": "sign", "value": "={{ $json.unsigned }}", "dataPropertyName": "sig", "algorithm": "RSA-SHA256", "encoding": "base64"},
  credentials=VAPID_CRED)
hdr = node("Złóż nagłówek VAPID", "n8n-nodes-base.code", 2, [1120, 140], {"jsCode":
  "// Crypto node zwraca podpis ECDSA w DER, JWT wymaga surowego r||s (64 bajty).\n"
  f"const VAPID_PUB = '{VAPID_PUB}';\n"
  "const b64u = (buf) => buf.toString('base64').replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');\n"
  "function derToRaw(der) {\n  let o = 2;\n  if (der[1] & 0x80) o += der[1] & 0x7f;\n  const int = () => {\n"
  "    if (der[o] !== 0x02) throw new Error('Zły DER');\n    const len = der[o + 1];\n    let v = der.slice(o + 2, o + 2 + len);\n"
  "    o += 2 + len;\n    while (v.length > 32 && v[0] === 0) v = v.slice(1);\n    return Buffer.concat([Buffer.alloc(32 - v.length), v]);\n  };\n"
  "  return Buffer.concat([int(), int()]);\n}\n"
  "return $input.all().map((it) => ({ json: { endpoint: it.json.endpoint,\n"
  "  authorization: `vapid t=${it.json.unsigned + '.' + b64u(derToRaw(Buffer.from(it.json.sig, 'base64')))}, k=${VAPID_PUB}` } }));"})
push = node("Wyślij push", "n8n-nodes-base.httpRequest", 4.2, [1340, 140], {
  "method": "POST", "url": "={{ $json.endpoint }}", "sendHeaders": True, "headerParameters": {"parameters": [
    {"name": "Authorization", "value": "={{ $json.authorization }}"}, {"name": "TTL", "value": "86400"},
    {"name": "Urgency", "value": "high"}, {"name": "Content-Length", "value": "0"}]},
  "options": {"timeout": 10000, "response": {"response": {"fullResponse": True, "neverError": True, "responseFormat": "text"}}}})
res = node("Wynik wysyłki", "n8n-nodes-base.code", 2, [1560, 140], {"jsCode":
  "// 201 = OK, 404/410 = subskrypcja martwa (kasujemy), reszta = błąd.\n"
  "const subs = $('Złóż nagłówek VAPID').all();\n"
  "return $input.all().map((it, i) => ({ json: { endpoint: subs[i].json.endpoint,\n"
  "  status: Number(it.json.statusCode ?? it.json.error?.status ?? it.json.error?.httpCode ?? 0) || 0 } }));"})
upd = node("Aktualizuj urządzenia", "n8n-nodes-base.postgres", 2.6, [1780, 140], {"operation": "executeQuery", "query":
  "WITH d AS (DELETE FROM push_subscriptions WHERE endpoint = $1 AND $2 IN (404, 410) RETURNING 1)\n"
  "UPDATE push_subscriptions SET last_status = $2,\n"
  "  last_ok_at = CASE WHEN $2 BETWEEN 200 AND 299 THEN now() ELSE last_ok_at END,\n"
  "  failures = CASE WHEN $2 BETWEEN 200 AND 299 THEN 0 ELSE failures + 1 END\n"
  "WHERE endpoint = $1 AND $2 NOT IN (404, 410)",
  "options": {"queryReplacement": "={{ [ $json.endpoint, $json.status ] }}"}}, credentials=PG)

SUMMARY_WF = open(".summary-wf-id").read().strip()
fs = node("Tylko strony do streszczenia", "n8n-nodes-base.filter", 2.2, [460, -320], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.summarize }}", "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}})
fset = node("Id strony", "n8n-nodes-base.set", 3.4, [680, -320], {"mode": "manual", "includeOtherFields": False,
  "assignments": {"assignments": [{"id": str(uuid.uuid4()), "name": "item_id", "type": "string", "value": "={{ $json.item_id }}"},
                                  {"id": str(uuid.uuid4()), "name": "reason", "type": "string", "value": "scheduled"}]}, "options": {}})
fx = node("Streść stronę (w tle)", "n8n-nodes-base.executeWorkflow", 1.2, [900, -320], {
  "source": "database", "workflowId": {"__rl": True, "value": SUMMARY_WF, "mode": "id"},
  "options": {"waitForSubWorkflow": False}})
link(t, claim); link(claim, fm); link(claim, subs); link(claim, fs); link(fs, fset); link(fset, fx)
link(fm, mail); link(mail, mark)
link(subs, jwt); link(jwt, sign); link(sign, hdr); link(hdr, push); link(push, res); link(res, upd)

json.dump({"name": "Oboe: Harmonogram", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw", "saveDataSuccessExecution": "none"}},
          open("oboe-scheduler.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
