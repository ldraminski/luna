"""Sesja + dzienny limit akcji z modelem (migracja db/014). Jedno zapytanie: kto to jest, czy mieści się w limicie, i zapis zużycia.

Wynik: user_id (pusty = niezalogowany), within_limit (bool), daily_limit (NULL = bez limitu).
Zużycie zapisuje się TYLKO, gdy akcja mieści się w limicie. Doba liczona w strefie Europe/Warsaw.
"""

def session_with_limit(kind):
    return f"""WITH me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id),
u AS (SELECT id, daily_limit FROM users WHERE id = (SELECT user_id FROM me)),
used AS (SELECT count(*) AS n FROM usage_log
         WHERE user_id = (SELECT id FROM u) AND at >= (date_trunc('day', now() AT TIME ZONE 'Europe/Warsaw') AT TIME ZONE 'Europe/Warsaw')),
ok AS (SELECT (SELECT daily_limit FROM u) IS NULL OR (SELECT n FROM used) < (SELECT daily_limit FROM u) AS v),
log AS (INSERT INTO usage_log (user_id, kind) SELECT id, '{kind}' FROM u WHERE (SELECT v FROM ok) RETURNING 1)
SELECT (SELECT user_id FROM me) AS user_id, coalesce((SELECT v FROM ok), false) AND EXISTS (SELECT 1 FROM u) AS within_limit,
       (SELECT daily_limit FROM u) AS daily_limit, (SELECT count(*) FROM log) AS logged"""

# Odpowiedź, gdy limit się skończył (HTTP 429). Wyrażenie n8n; $json = wynik session_with_limit.
LIMIT_MSG = ("'Na dziś wystarczy — to konto testowe ma limit ' + $json.daily_limit + ' wpisów dziennie (Luna działa na jednym, "
             "prywatnym kluczu). Wróć jutro albo napisz do Łukasza.'")
