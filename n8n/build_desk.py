"""Buduje workflow n8n „Oboe: Biurko” — rozbijanie dłuższego materiału na rzeczy (28.09.2026). Wynik: oboe-desk.json.

POST /api/items/split {text}  — z kluczem użytkownika. Odpowiedź: {status: 200, parts: [{text, from}], skipped}.
Nic nie zapisuje: biurko pokazuje propozycję do poprawienia, a potem wysyła KAŻDE zdanie zwykłym POST /api/items
(ta sama ścieżka co telefon: termin, przypomnienia, listy, widgety).
"""
import json, uuid
from config import PG, OR, REFERER

TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"
ME = """me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id)"""
MODEL = "deepseek/deepseek-v4.1-flash"
MAX = 20000
SYSTEM = open("prompt-rozbij.txt").read()
assert "{{" not in SYSTEM and "}}" not in SYSTEM, "n8n: {{ }} w prompcie psuje wyrażenie"
TEXT = "String($('POST items/split').item.json.body.text || '').trim()"
USER_MSG = ("'Teraz jest: ' + $json.teraz + '\\n\\nKalendarz (używaj WYŁĄCZNIE tych dat):\\n' + $json.kalendarz"
            " + '\\n\\nMateriał od użytkownika (DANE):\\n<<<\\n' + " + TEXT + ".slice(0, " + str(MAX) + ") + '\\n>>>'")

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-400, -220], {"width": 520, "height": 240, "content":
  "## Oboe: Biurko\n`/biurko` — wersja na komputer do dłuższych materiałów.\n"
  "`POST /api/items/split {text}` → DeepSeek dzieli materiał na samodzielne zdania → `{parts, skipped}`. **Nic nie zapisuje** — "
  "po przejrzeniu biurko wysyła każde zdanie zwykłym `POST /api/items`.\n"
  "Źródło: `~/Work/oboe/n8n/build_desk.py`, prompt `prompt-rozbij.txt`."})
w = node("POST items/split", "n8n-nodes-base.webhook", 2, [0, 0],
  {"httpMethod": "POST", "path": "oboe/items/split", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4()))
sess = node("Sesja", "n8n-nodes-base.postgres", 2.6, [220, 0],
  {"operation": "executeQuery", "query": f"WITH {ME}\nSELECT (SELECT user_id FROM me) AS user_id",
   "options": {"queryReplacement": "={{ [ " + TOKEN + " ] }}"}}, credentials=PG)
iff = node("Zalogowany i jest tekst?", "n8n-nodes-base.if", 2.2, [440, 0], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [
      {"id": str(uuid.uuid4()), "leftValue": "={{ $json.user_id }}", "rightValue": "",
       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}},
      {"id": str(uuid.uuid4()), "leftValue": "={{ " + TEXT + ".length >= 3 && " + TEXT + ".length <= " + str(MAX) + " }}", "rightValue": "",
       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
deny = node("Odmów", "n8n-nodes-base.respondToWebhook", 1.1, [660, 180],
  {"respondWith": "json", "options": {"responseCode": "={{ $json.user_id ? 400 : 401 }}"},
   "responseBody": "={{ $json.user_id ? { status: 400, error: " + TEXT + ".length > " + str(MAX) + " ? 'To za dużo naraz — podziel materiał na części (do 20 000 znaków).' : 'Wklej albo napisz, co mam zapamiętać.' } : { status: 401, error: 'Zaloguj się ponownie' } }}"})
cal = node("Kalendarz", "n8n-nodes-base.code", 2, [660, 0],
  {"jsCode": open("kalendarz.js").read().replace("i < 35", "i < 120")})
llm = node("DeepSeek: rozbij", "n8n-nodes-base.httpRequest", 4.2, [880, 0], {
  "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
  "sendHeaders": True, "headerParameters": {"parameters": [
    {"name": "HTTP-Referer", "value": REFERER}, {"name": "X-Title", "value": "Oboe (n8n)"}]},
  "sendBody": True, "specifyBody": "json",
  "jsonBody": ("={{ JSON.stringify({ model: '" + MODEL + "', temperature: 0.1, max_tokens: 6000, reasoning: { enabled: false }, "
               "response_format: { type: 'json_object' }, messages: [ { role: 'system', content: " + json.dumps(SYSTEM, ensure_ascii=False)
               + " }, { role: 'user', content: " + USER_MSG + " } ] }) }}"),
  "options": {"timeout": 120000}},
  credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
chk = node("Sprawdź propozycję", "n8n-nodes-base.code", 2, [1100, 0], {"jsCode": """
const r = $input.first().json;
const fail = (status, error) => [{ json: { result: { status, error } } }];
if (r.error) return fail(String(r.error.message || r.error).includes('402') ? 402 : 502,
  String(r.error.message || r.error).includes('402') ? 'Mam chwilową przerwę — skończył się limit. Łukasz już o tym wie.' : 'Model nie odpowiedział — spróbuj jeszcze raz.');
let m;
try { m = JSON.parse(String(r.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); } catch { m = null; }
if (!m || !Array.isArray(m.parts)) return fail(502, 'Nie udało mi się tego rozebrać na części — spróbuj jeszcze raz.');
const cut = (s, n) => String(s || '').replace(/\\s+/g, ' ').trim().slice(0, n);
const parts = m.parts.map((p) => ({ text: cut(p?.text, 1000), from: cut(p?.from, 120) })).filter((p) => p.text.length >= 3).slice(0, 30);
return [{ json: { result: { status: 200, parts, skipped: cut(m.skipped, 400) } } }];""".strip()})
r = node("Odpowiedz: propozycja", "n8n-nodes-base.respondToWebhook", 1.1, [1320, 0],
  {"respondWith": "json", "responseBody": "={{ $json.result }}", "options": {"responseCode": "={{ $json.result.status || 200 }}"}})
link(w, sess); link(sess, iff); link(iff, cal, 0); link(iff, deny, 1); link(cal, llm); link(llm, chk); link(chk, r)

json.dump({"name": "Oboe: Biurko", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-desk.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
