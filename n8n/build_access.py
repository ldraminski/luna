"""Buduje workflow n8n „Oboe: Dostęp” — samodzielne proszenie o klucz (decyzja Łukasza 27.09.2026). Wynik: oboe-access.json.

POST /api/access/request {email, name}   — bez klucza. Istniejące konto: nowy klucz od razu mailem (stare zostają).
                                           Nowa osoba: prośba czeka, admin dostaje powiadomienie (przez „Oboe: Harmonogram”).
GET  /api/access/requests                — admin: prośby czekające.
POST /api/access/decide {id, accept}     — admin: akceptacja = konto + klucz mailem; odrzucenie = mail „przykro mi”.
Klucz NIGDY nie wraca w odpowiedzi HTTP — tylko mailem. Limit: 3 prośby/h na e-mail, 40/h łącznie.
"""
import json, uuid
from config import PG, SMTP
import maile

TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"
ME = """me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id),
adm AS (SELECT id FROM users WHERE id = (SELECT user_id FROM me) AND is_admin)"""
UNAUTH = "json_build_object('status', 401, 'error', 'Zaloguj się ponownie')"
FORBID = "json_build_object('status', 403, 'error', 'To może zrobić tylko Łukasz.')"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def hook(name, method, path, y):
    return node(name, "n8n-nodes-base.webhook", 2, [0, y],
      {"httpMethod": method, "path": f"oboe/{path}", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4()))
def sql(name, pos, query, params):
    return node(name, "n8n-nodes-base.postgres", 2.6, pos,
      {"operation": "executeQuery", "query": query.strip(), "options": {"queryReplacement": params}}, credentials=PG)
def respond(name, pos, body):
    return node(name, "n8n-nodes-base.respondToWebhook", 1.1, pos, {"respondWith": "json", "responseBody": body,
      "options": {"responseCode": "={{ $('" + CUR + "').item.json.result.status || 200 }}"}})
def mail(name, pos, subject, text, html=None):
    return node(name, "n8n-nodes-base.emailSend", 2.1, pos, {"fromEmail": maile.NADAWCA,
      "toEmail": "={{ $json.result.email }}", "subject": subject, **({"emailFormat": "both", "text": text, "html": html} if html else {"emailFormat": "text", "text": text}),
      "options": {"appendAttribution": False}}, credentials=SMTP, onError="continueRegularOutput")
def when(name, pos, expr):
    return node(name, "n8n-nodes-base.if", 2.2, pos, {"conditions": {"options": {"caseSensitive": True, "leftValue": "",
      "typeValidation": "loose", "version": 2}, "conditions": [{"id": str(uuid.uuid4()), "leftValue": expr, "rightValue": "",
      "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}})
# bez klucza w odpowiedzi — tylko te pola wychodzą do przeglądarki
SAFE = "{ status: R.status, action: R.action, name: R.name, error: R.error }"

node("Opis", "n8n-nodes-base.stickyNote", 1, [-420, -300], {"width": 600, "height": 260, "content":
  "## Oboe: Dostęp (Luna)\nKtoś podaje imię i e-mail → istniejące konto dostaje nowy klucz mailem od razu; "
  "nowa osoba czeka na akceptację Łukasza (powiadomienie push + mail przez „Oboe: Harmonogram”).\n"
  "Akceptacja → konto + klucz mailem; odrzucenie → mail „przykro mi”.\n"
  "**Klucz nigdy nie wraca w odpowiedzi HTTP.** Limit 3/h na e-mail, 40/h łącznie (`access_log`).\n"
  "Teksty maili: `n8n/maile.py`. Źródło: `~/Work/oboe/n8n/build_access.py`."})

# ---- 1. prośba ----
CUR = "Prośba"
w1 = hook("POST access/request", "POST", "access/request", 0)
q1 = sql("Prośba", [220, 0], """
WITH v AS (SELECT lower(trim($1)) AS email, nullif(left(trim($2), 80), '') AS name
           WHERE lower(trim($1)) ~ '^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$'),
lim AS (SELECT (SELECT count(*) FROM access_log WHERE email = (SELECT email FROM v) AND at > now() - interval '1 hour') AS per_email,
               (SELECT count(*) FROM access_log WHERE at > now() - interval '1 hour') AS total),
ok AS (SELECT v.* FROM v, lim WHERE lim.per_email < 3 AND lim.total < 40),
log AS (INSERT INTO access_log (email) SELECT email FROM ok RETURNING 1),
u AS (SELECT id, email, name FROM users WHERE email = (SELECT email FROM ok)),
tok AS (SELECT encode(gen_random_bytes(32), 'hex') AS t),
s AS (INSERT INTO sessions (token_hash, user_id)
      SELECT encode(digest((SELECT t FROM tok), 'sha256'), 'hex'), id FROM u RETURNING 1),
rej AS (SELECT 1 FROM access_requests WHERE email = (SELECT email FROM ok) AND status = 'rejected'
        AND decided_at > now() - interval '30 days' AND NOT EXISTS (SELECT 1 FROM u)),
prev AS (SELECT 1 FROM access_requests WHERE email = (SELECT email FROM ok) AND status = 'pending'),
req AS (INSERT INTO access_requests (email, name) SELECT email, name FROM ok
        WHERE NOT EXISTS (SELECT 1 FROM u) AND NOT EXISTS (SELECT 1 FROM rej) AND NOT EXISTS (SELECT 1 FROM prev)
        RETURNING id, email, name),
nt AS (INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)
       SELECT NULL, a.id, now(), '{push,email}', 'Prośba o dostęp do Luny',
              coalesce(r.name, r.email) || ' (' || r.email || ') chce korzystać z Luny. Otwórz, żeby zaakceptować albo odrzucić.'
       FROM req r CROSS JOIN users a WHERE a.is_admin RETURNING 1)
SELECT CASE
  WHEN NOT EXISTS (SELECT 1 FROM v) THEN json_build_object('status', 400, 'error', 'To nie wygląda na adres e-mail.')
  WHEN NOT EXISTS (SELECT 1 FROM ok) THEN json_build_object('status', 429, 'error', 'Za dużo próśb naraz — spróbuj za godzinę.')
  WHEN EXISTS (SELECT 1 FROM u) THEN json_build_object('status', 200, 'action', 'token', 'email', (SELECT email FROM u),
       'name', coalesce((SELECT name FROM u), ''), 'token', (SELECT t FROM tok), 'issued', (SELECT count(*) FROM s))
  WHEN EXISTS (SELECT 1 FROM rej) THEN json_build_object('status', 200, 'action', 'rejected', 'name', (SELECT name FROM ok))
  ELSE json_build_object('status', 200, 'action', 'pending', 'name', (SELECT name FROM ok), 'notified', (SELECT count(*) FROM nt))
END AS result""", "={{ [ String($json.body.email || '').slice(0, 200), String($json.body.name || '').slice(0, 80) ] }}")
i1 = when("Istniejące konto?", [440, 0], "={{ $json.result.action === 'token' }}")
m1 = mail("Mail: nowy klucz", [660, -120], "Twój nowy klucz do Luny", maile.klucz_nowy("$json.result"), maile.html_nowy("$json.result"))
r1 = respond("Odpowiedz: prośba", [880, 0], "={{ (R => (" + SAFE + "))($('Prośba').item.json.result) }}")
link(w1, q1); link(q1, i1); link(i1, m1, 0); link(i1, r1, 1); link(m1, r1)

# ---- 2. lista próśb (admin) ----
CUR = "Prośby czekające"
w2 = hook("GET access/requests", "GET", "access/requests", 400)
q2 = sql("Prośby czekające", [220, 400], f"""
WITH {ME}
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM adm) THEN {FORBID}
  ELSE json_build_object('status', 200, 'requests', coalesce((SELECT json_agg(r ORDER BY r.created_at) FROM
       (SELECT id, email, name, created_at FROM access_requests WHERE status = 'pending') r), '[]'::json)) END AS result""",
  "={{ [ " + TOKEN + " ] }}")
r2 = respond("Odpowiedz: prośby", [440, 400], "={{ $json.result }}")
link(w2, q2); link(q2, r2)

# ---- 3. decyzja (admin) ----
CUR = "Decyzja"
w3 = hook("POST access/decide", "POST", "access/decide", 700)
q3 = sql("Decyzja", [220, 700], f"""
WITH {ME},
d AS (UPDATE access_requests SET status = CASE WHEN $3::boolean THEN 'accepted' ELSE 'rejected' END,
        decided_at = now(), decided_by = (SELECT id FROM adm)
      WHERE id = $2::bigint AND status = 'pending' AND EXISTS (SELECT 1 FROM adm) RETURNING email, name, status),
u AS (INSERT INTO users (email, name) SELECT email, name FROM d WHERE status = 'accepted'
      ON CONFLICT (email) DO UPDATE SET name = coalesce(users.name, excluded.name) RETURNING id, email, name),
tok AS (SELECT encode(gen_random_bytes(32), 'hex') AS t),
s AS (INSERT INTO sessions (token_hash, user_id)
      SELECT encode(digest((SELECT t FROM tok), 'sha256'), 'hex'), id FROM u RETURNING 1)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN NOT EXISTS (SELECT 1 FROM adm) THEN {FORBID}
  WHEN NOT EXISTS (SELECT 1 FROM d) THEN json_build_object('status', 404, 'error', 'Tej prośby już nie ma — jest rozpatrzona.')
  WHEN (SELECT status FROM d) = 'accepted' THEN json_build_object('status', 200, 'action', 'accepted',
       'email', (SELECT email FROM u), 'name', coalesce((SELECT name FROM u), ''), 'token', (SELECT t FROM tok), 'issued', (SELECT count(*) FROM s))
  ELSE json_build_object('status', 200, 'action', 'rejected', 'email', (SELECT email FROM d), 'name', coalesce((SELECT name FROM d), ''))
END AS result""",
  "={{ [ " + TOKEN + ", /^[0-9]{1,18}$/.test(String($json.body.id)) ? String($json.body.id) : '0', $json.body.accept === true ? 'true' : 'false' ] }}")
i3 = when("Zaakceptowana?", [440, 640], "={{ $json.result.action === 'accepted' }}")
i3b = when("Odrzucona?", [660, 800], "={{ $json.result.action === 'rejected' }}")
m3a = mail("Mail: witaj", [660, 560], "Łukasz zaakceptował Twoją prośbę — tu Luna",
           maile.klucz_powitalny("$json.result", "Łukasz zaakceptował Twoją prośbę o dostęp — witaj!\\n\\n" + maile.O_LUNIE),
           maile.html_powitalny("$json.result", "<p><b>Łukasz zaakceptował Twoją prośbę o dostęp — witaj!</b></p>" + maile.O_LUNIE_HTML))
m3b = mail("Mail: przykro mi", [880, 760], "Twoja prośba o dostęp do Luny", maile.odrzucenie("$json.result"))
r3 = respond("Odpowiedz: decyzja", [1100, 700],
  "={{ (R => Object.assign(" + SAFE.replace("}", ", email: R.email }") + ", { emailed: !$json.error }))($('Decyzja').item.json.result) }}")
link(w3, q3); link(q3, i3); link(i3, m3a, 0); link(i3, i3b, 1); link(i3b, m3b, 0); link(i3b, r3, 1)
link(m3a, r3); link(m3b, r3)

json.dump({"name": "Oboe: Dostęp", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-access.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
