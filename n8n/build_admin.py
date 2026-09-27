"""Buduje workflow n8n „Oboe: Wydaj token”. Wynik: oboe-admin.json.

Wołany tylko z serwera (nginx blokuje /api/admin/):
  ssh vps.draminski.dev 'curl -s -X POST http://127.0.0.1:5678/webhook/oboe/admin/token \\
     -H "X-Admin-Token: $(cat /opt/oboe/.admin-token)" -H "Content-Type: application/json" \\
     -d "{\\"email\\":\\"...\\",\\"name\\":\\"...\\",\\"send_email\\":true}"'
"""
import json, uuid

APP_URL = "https://oboe.draminski.dev"
PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
SMTP = {"smtp": {"id": "DY5t4HkHVBfxB2gY", "name": "SMTP n8n renlab"}}
ADMIN = {"httpHeaderAuth": {"id": "9Rd7Zl7NxIcEvPtL", "name": "Oboe - admin (X-Admin-Token)"}}

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-380, -260], {"width": 560, "height": 240, "content":
  "## Oboe: Wydaj token\nAdmin (Łukasz) dodaje osobę albo wydaje nowy token zgubionemu.\n"
  "Body: `email`, `name` (opcjonalnie), `send_email` (domyślnie true).\n"
  "Stare tokeny tej osoby są **unieważniane** — w bazie jest tylko sha256, więc tokenu nie da się odczytać, tylko wydać nowy.\n"
  "Odpowiedź zawiera token (tryb ręczny). Wołać tylko z serwera — nginx blokuje `/api/admin/`.\n"
  "Źródło: `~/Work/oboe/n8n/build_admin.py`."})
w = node("POST admin/token", "n8n-nodes-base.webhook", 2, [0, 0],
  {"httpMethod": "POST", "path": "oboe/admin/token", "authentication": "headerAuth", "responseMode": "responseNode", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
q = node("Wydaj token", "n8n-nodes-base.postgres", 2.6, [220, 0], {"operation": "executeQuery", "query": """
WITH valid AS (SELECT lower(trim($1)) AS email WHERE lower(trim($1)) ~ '^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$'),
u AS (
  INSERT INTO users (email, name) SELECT email, nullif(trim($2), '') FROM valid
  ON CONFLICT (email) DO UPDATE SET name = coalesce(nullif(trim($2), ''), users.name)
  RETURNING id, email, name),
old AS (DELETE FROM sessions WHERE user_id IN (SELECT id FROM u) RETURNING 1),
tok AS (SELECT encode(gen_random_bytes(32), 'hex') AS t),
s AS (INSERT INTO sessions (token_hash, user_id)
      SELECT encode(digest((SELECT t FROM tok), 'sha256'), 'hex'), id FROM u RETURNING user_id)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM s) THEN json_build_object('status', 400, 'error', 'Zły e-mail')
  ELSE json_build_object('status', 200, 'email', (SELECT email FROM u), 'name', (SELECT name FROM u),
       'token', (SELECT t FROM tok), 'revoked', (SELECT count(*) FROM old)) END AS result""".strip(),
  "options": {"queryReplacement": "={{ [ String($json.body.email || '').slice(0, 200), String($json.body.name || '').slice(0, 80) ] }}"}},
  credentials=PG)
iff = node("Wysłać mail?", "n8n-nodes-base.if", 2.2, [440, 0], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [
      {"id": str(uuid.uuid4()), "leftValue": "={{ $json.result.status === 200 && $('POST admin/token').item.json.body.send_email !== false }}",
       "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})

TEXT = ("={{ 'Cześć' + ($json.result.name ? ' ' + $json.result.name : '') + '!\\n\\n"
  "Oto Twój klucz do Oboe — aplikacji, która pamięta za Ciebie:\\n\\n' + $json.result.token + '\\n\\n"
  "Jak zacząć:\\n"
  "1. Otwórz na telefonie: " + APP_URL + "\\n"
  "2. iPhone: Udostępnij → „Do ekranu początkowego”. Android: menu → „Zainstaluj aplikację”.\\n"
  "3. Uruchom Oboe Z EKRANU POCZĄTKOWEGO i dopiero tam wklej klucz. "
  "(Na iPhonie aplikacja z ekranu początkowego nie widzi tego, co wpiszesz w Safari.)\\n\\n"
  "Klucz działa bez końca. Nie przesyłaj go nikomu — kto go ma, widzi Twoje przypomnienia.\\n"
  "Zgubisz go? Napisz do Łukasza, dostaniesz nowy, a ten przestanie działać.\\n\\n— Oboe' }}")
mail = node("Wyślij token mailem", "n8n-nodes-base.emailSend", 2.1, [660, -100], {
  "fromEmail": "Oboe <n8n@renlab.ovh>", "toEmail": "={{ $json.result.email }}",
  "subject": "Twój klucz do Oboe", "emailFormat": "text", "text": TEXT, "options": {"appendAttribution": False}},
  credentials=SMTP, onError="continueRegularOutput")
r_mail = node("Odpowiedz: wysłano", "n8n-nodes-base.respondToWebhook", 1.1, [880, -100], {
  "respondWith": "json", "options": {},
  "responseBody": "={{ Object.assign({}, $('Wydaj token').item.json.result, { emailed: !$json.error, email_error: $json.error ? String($json.error.message || $json.error) : undefined }) }}"})
r = node("Odpowiedz", "n8n-nodes-base.respondToWebhook", 1.1, [660, 120], {
  "respondWith": "json", "responseBody": "={{ Object.assign({}, $json.result, { emailed: false }) }}",
  "options": {"responseCode": "={{ $json.result.status || 200 }}"}})
link(w, q); link(q, iff); link(iff, mail, 0); link(iff, r, 1); link(mail, r_mail)

json.dump({"name": "Oboe: Wydaj token", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-admin.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
