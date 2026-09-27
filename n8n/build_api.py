"""Buduje workflow n8n „Oboe: API” (etap 1: logowanie). Wynik: oboe-api.json."""
import json, uuid

PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"

# Wspólny fragment: kto jest zalogowany (sesja ważna, przedłużana przy użyciu).
ME = """me AS (
  UPDATE sessions SET expires_at = greatest(expires_at, now() + interval '30 days')
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id)"""
UNAUTH = "json_build_object('status', 401, 'error', 'Zaloguj się ponownie')"

ROUTES = [
  # (metoda, ścieżka, nazwa, SQL, parametry-wyrażenie)
  ("POST", "login", "Logowanie", """
WITH recent AS (
  SELECT count(*) AS n FROM login_attempts
  WHERE email = lower($1) AND NOT ok AND created_at > now() - interval '15 minutes'),
u AS (
  SELECT id, email, name FROM users
  WHERE email = lower($1) AND password_hash IS NOT NULL
    AND password_hash = crypt($2, password_hash)
    AND (SELECT n FROM recent) < 10),
log AS (
  INSERT INTO login_attempts (email, ok) VALUES (lower($1), EXISTS (SELECT 1 FROM u))),
tok AS (SELECT encode(gen_random_bytes(32), 'hex') AS t),
s AS (
  INSERT INTO sessions (token_hash, user_id, expires_at)
  SELECT encode(digest((SELECT t FROM tok), 'sha256'), 'hex'), id, now() + interval '30 days' FROM u
  RETURNING user_id)
SELECT CASE
  WHEN (SELECT n FROM recent) >= 10 THEN json_build_object('status', 429, 'error', 'Za dużo prób. Spróbuj za 15 minut.')
  WHEN EXISTS (SELECT 1 FROM s) THEN json_build_object('status', 200, 'token', (SELECT t FROM tok),
       'user', (SELECT json_build_object('email', email, 'name', name) FROM u))
  ELSE json_build_object('status', 401, 'error', 'Zły e-mail albo hasło')
END AS result""",
   "={{ [ String($json.body.email || '').trim().slice(0, 200), String($json.body.password || '').slice(0, 200) ] }}"),

  ("POST", "logout", "Wylogowanie", """
WITH d AS (DELETE FROM sessions WHERE token_hash = encode(digest($1, 'sha256'), 'hex') RETURNING 1)
SELECT json_build_object('status', 200, 'ok', true) AS result""",
   "={{ [ " + TOKEN + " ] }}"),

  ("GET", "me", "Kim jestem", f"""
WITH {ME}
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE (SELECT json_build_object('status', 200, 'user', json_build_object('email', u.email, 'name', u.name))
        FROM users u WHERE u.id = (SELECT user_id FROM me)) END AS result""",
   "={{ [ " + TOKEN + " ] }}"),
]

nodes, conns = [], {}
nodes.append({"id": str(uuid.uuid4()), "name": "Opis", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
  "position": [-400, -200], "parameters": {"width": 520, "height": 220, "content":
  "## Oboe: API\nFront `oboe` (nginx) proxuje `/api/*` → `/webhook/oboe/*`.\n"
  "Autoryzacja: `Authorization: Bearer <token>`; w bazie tylko sha256 tokenu.\n"
  "Hasła: bcrypt w Postgresie (pgcrypto `crypt`), bo Code node nie ma `crypto`.\n"
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

wf = {"name": "Oboe: API", "nodes": nodes, "connections": conns,
      "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}}
json.dump(wf, open("oboe-api.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
