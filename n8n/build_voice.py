"""Buduje workflow n8n „Oboe: Notatki głosowe” — długie nagrania (spotkania, 5–20 min) przepisywane W TLE. Wynik: oboe-voice.json.

Łukasz, 29.09.2026: notatka ze spotkania ma 10–15 min — to zatkałoby Whispera na czas zwykłego dyktowania i trzymało użytkownika
przed ekranem „Odsłuchuję…”. Dlatego kolejka:
  POST /api/voice-notes {audio: dataURL, duration, name}  → wpis w `voice_notes` (status queued), odpowiedź od razu.
  GET  /api/voice-notes                                   → notatki w obróbce + niedawno gotowe (pasek i lista w aplikacji).
  POST /api/voice-notes/dismiss {id}                      → w kolejce: anuluj (usuń); gotowe/błąd: schowaj z listy.
  POST /api/voice-notes/retry {id}                        → błąd → z powrotem do kolejki (póki nagranie jest).
  Co 30 s: JEDNA notatka naraz (blokada doradcza + „nikt nie przepisuje”) → Whisper (u nas, CPU; ~1/3 długości nagrania)
  → model porządkuje (streszczenie, ustalenia, do zrobienia) → zwykła rzecz w Lunie + push „Notatka gotowa”.
Nagranie leży w bazie tylko do przepisania — po sukcesie `audio = NULL`. Zawieszone (> 45 min) wraca do kolejki, 3. raz = błąd.
"""
import json, uuid
from config import PG, OR, REFERER, TEXT_MODEL, or_headers, WHISPER_URL
from limit import session_with_limit, LIMIT_MSG
from komunikaty import KEY_LIMIT, is_key_limit_js

WHISPER_MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"
MAX_MB = 11            # po zdekodowaniu; nagranie z aplikacji (opus 24 kb/s) to ~3 MB na 15 min, dyktafon telefonu (AAC) ~7 MB
MAX_QUEUE = 3          # ile naraz może czekać jedna osoba
TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"
ME = """me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id)"""
UNAUTH = "json_build_object('status', 401, 'error', 'Zaloguj się ponownie')"
UUID = "(/^[0-9a-f-]{36}$/i.test(String($json.body.id || '')) ? $json.body.id : '00000000-0000-0000-0000-000000000000')"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def chain(*ns):
    for a, b in zip(ns, ns[1:]): link(a, b)
def pg(name, pos, sql, params=None, **kw):
    p = {"operation": "executeQuery", "query": sql.strip(), "options": {}}
    if params: p["options"]["queryReplacement"] = params
    return node(name, "n8n-nodes-base.postgres", 2.6, pos, p, credentials=PG, **kw)
def code(name, pos, js): return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js.strip()})
def iff(name, pos, expr):
    return node(name, "n8n-nodes-base.if", 2.2, pos, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
      "conditions": [{"id": str(uuid.uuid4()), "leftValue": expr, "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
      "combinator": "and"}, "options": {}})
def hook(method, path, pos):
    return node(f"{method} {path}", "n8n-nodes-base.webhook", 2, pos,
      {"httpMethod": method, "path": f"oboe/{path}", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4()))
def respond(name, pos, body="={{ $json.result }}", code_="={{ $json.result.status || 200 }}"):
    return node(name, "n8n-nodes-base.respondToWebhook", 1.1, pos, {"respondWith": "json", "responseBody": body, "options": {"responseCode": code_}})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-460, -420], {"width": 700, "height": 330, "content":
  "## Oboe: Notatki głosowe\nDługie nagrania (spotkania) przepisywane w tle, po jednym naraz.\n"
  "- `POST /api/voice-notes` → kolejka (`voice_notes`), odpowiedź od razu. `GET` → pasek „w obróbce” w aplikacji.\n"
  "- Co 30 s: jedna notatka → Whisper u nas (timeout 40 min) → DeepSeek porządkuje (streszczenie, ustalenia, do zrobienia) "
  "→ rzecz w Lunie (`data.voice`) + push. Nagranie kasowane po przepisaniu.\n"
  "- Zawieszone > 45 min wraca do kolejki; 3. próba = błąd („Spróbuj ponownie” w aplikacji).\n"
  "Źródło: `~/Work/oboe/n8n/build_voice.py`, prompt `prompt-notatka-glosowa.txt`."})

# ---------- 1. wgranie nagrania ----------
w = hook("POST", "voice-notes", [0, 0])
sess = pg("Sesja, limit, kolejka", [220, 0], session_with_limit("voice").replace(
  "SELECT (SELECT user_id FROM me) AS user_id,",
  "SELECT (SELECT user_id FROM me) AS user_id,\n  (SELECT count(*) FROM voice_notes WHERE user_id = (SELECT user_id FROM me) AND status IN ('queued', 'transcribing', 'summarizing')) AS waiting,"),
  "={{ [ " + TOKEN + " ] }}")
chk = code("Sprawdź nagranie", [440, 0], f"""
// Odpowiedź od razu z błędem albo dane do zapisu. Nagranie: data URL z przeglądarki (nagrane w Lunie albo plik z dyktafonu).
const s = $json; const b = $('POST voice-notes').first().json.body || {{}};
const out = (status, error) => [{{ json: {{ ok: false, result: {{ status, error }} }} }}];
if (!s.user_id) return out(401, 'Zaloguj się ponownie');
if (Number(s.waiting) >= {MAX_QUEUE}) return out(429, 'Masz już {MAX_QUEUE} notatki w kolejce — poczekaj, aż skończę którąś z nich.');
if (!s.within_limit) return out(429, {LIMIT_MSG});
const url = String(b.audio || '');
const m = url.match(/^data:(audio\\/[a-z0-9.+-]+|video\\/(?:webm|mp4|quicktime))(?:;[a-z0-9=._-]+)*;base64,/i);
if (!m) return out(400, 'Nie dostałam nagrania — spróbuj jeszcze raz.');
const b64 = url.slice(m[0].length);
const bytes = Math.floor(b64.length * 3 / 4);
if (bytes < 2000) return out(400, 'To nagranie jest za krótkie.');
if (bytes > {MAX_MB} * 1024 * 1024) return out(413, 'To nagranie jest za duże (limit {MAX_MB} MB, ok. 20 minut). Podziel je albo nagraj w Lunie.');
const duration = Math.max(0, Math.min(4 * 3600, Math.round(Number(b.duration) || 0)));
const name = String(b.name || '').replace(/[\\u0000-\\u001f]/g, '').trim().slice(0, 120);
return [{{ json: {{ ok: true, user_id: s.user_id, mime: m[1].toLowerCase().replace('video/', 'audio/'), b64, bytes, duration, name }} }}];""")
ok = iff("Nagranie OK?", [660, 0], "={{ $json.ok === true }}")
bad = respond("Odpowiedz: odmowa", [880, 180])
ins = pg("Do kolejki", [880, 0], """
WITH v AS (
  INSERT INTO voice_notes (user_id, audio, mime, bytes, duration_s, name)
  VALUES ($1::uuid, decode($2, 'base64'), $3, $4::int, $5::int, $6)
  RETURNING id, status, duration_s, name, created_at)
SELECT json_build_object('status', 200, 'note', (SELECT row_to_json(v) FROM v)) AS result""",
  "={{ [ $json.user_id, $json.b64, $json.mime, $json.bytes, $json.duration, $json.name ] }}")
r1 = respond("Odpowiedz: w kolejce", [1100, 0])
chain(w, sess, chk, ok); link(ok, ins, 0); link(ok, bad, 1); link(ins, r1)

# ---------- 2. lista: w obróbce + niedawno gotowe ----------
# Kolejka jest wspólna (jeden Whisper), więc miejsce i czas liczymy po wszystkich; szacunek: ~0,35 długości nagrania + 30 s porządkowania.
y = 360
w2 = hook("GET", "voice-notes", [0, y])
q2 = pg("Lista notatek", [220, y], f"""
WITH {ME},
q AS (SELECT id, duration_s, created_at, status, started_at,
        sum(CASE WHEN status = 'queued' THEN greatest(duration_s, 60) * 0.35 + 30 ELSE 0 END) OVER (ORDER BY created_at ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS ahead_s,
        count(*) FILTER (WHERE status = 'queued') OVER (ORDER BY created_at) AS place
      FROM voice_notes WHERE status IN ('queued', 'transcribing', 'summarizing')),
cur AS (SELECT coalesce(sum(greatest(0, greatest(duration_s, 60) * 0.35 + 30 - extract(epoch FROM now() - started_at))), 0) AS left_s
        FROM voice_notes WHERE status IN ('transcribing', 'summarizing')),
l AS (SELECT v.id, v.status, v.duration_s, v.name, v.created_at, v.started_at, v.finished_at, v.item_id, v.error,
        v.audio IS NOT NULL AS can_retry, i.title AS item_title,
        CASE WHEN v.status = 'queued' THEN q.place END AS place,
        CASE WHEN v.status = 'queued' THEN round((SELECT left_s FROM cur) + coalesce(q.ahead_s, 0) + greatest(v.duration_s, 60) * 0.35 + 30)
             WHEN v.status IN ('transcribing', 'summarizing') THEN round(greatest(15, greatest(v.duration_s, 60) * 0.35 + 30 - extract(epoch FROM now() - v.started_at))) END AS eta_s
      FROM voice_notes v LEFT JOIN q ON q.id = v.id LEFT JOIN items i ON i.id = v.item_id
      WHERE v.user_id = (SELECT user_id FROM me) AND v.seen_at IS NULL AND v.created_at > now() - interval '3 days'
      ORDER BY v.created_at DESC LIMIT 20)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  ELSE json_build_object('status', 200, 'notes', coalesce((SELECT json_agg(l) FROM l), '[]'::json)) END AS result""", "={{ [ " + TOKEN + " ] }}")
r2 = respond("Odpowiedz: lista", [440, y])
chain(w2, q2, r2)

# ---------- 3. anuluj / schowaj ----------
y = 600
w3 = hook("POST", "voice-notes/dismiss", [0, y])
q3 = pg("Anuluj albo schowaj", [220, y], f"""
WITH {ME},
del AS (DELETE FROM voice_notes WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) AND status = 'queued' RETURNING id),
hid AS (UPDATE voice_notes SET seen_at = now(), audio = CASE WHEN status = 'error' THEN NULL ELSE audio END
        WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) AND status IN ('done', 'error') RETURNING id)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN EXISTS (SELECT 1 FROM del) OR EXISTS (SELECT 1 FROM hid) THEN json_build_object('status', 200, 'ok', true, 'cancelled', EXISTS (SELECT 1 FROM del))
  ELSE json_build_object('status', 409, 'error', 'Tę notatkę właśnie przepisuję — za chwilę będzie gotowa.') END AS result""",
  "={{ [ " + TOKEN + ", " + UUID + " ] }}")
r3 = respond("Odpowiedz: schowane", [440, y])
chain(w3, q3, r3)

y = 840
w4 = hook("POST", "voice-notes/retry", [0, y])
q4 = pg("Spróbuj ponownie", [220, y], f"""
WITH {ME},
upd AS (UPDATE voice_notes SET status = 'queued', attempts = 0, error = NULL, started_at = NULL, finished_at = NULL, created_at = now()
        WHERE id = $2::uuid AND user_id = (SELECT user_id FROM me) AND status = 'error' AND audio IS NOT NULL RETURNING id)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM me) THEN {UNAUTH}
  WHEN EXISTS (SELECT 1 FROM upd) THEN json_build_object('status', 200, 'ok', true)
  ELSE json_build_object('status', 404, 'error', 'Tego nagrania już nie mam — nagraj je jeszcze raz.') END AS result""",
  "={{ [ " + TOKEN + ", " + UUID + " ] }}")
r4 = respond("Odpowiedz: ponownie", [440, y])
chain(w4, q4, r4)

# ---------- 4. przepisywanie w tle: jedna notatka naraz ----------
y = 1200
t = node("Co 30 sekund", "n8n-nodes-base.scheduleTrigger", 1.2, [0, y], {"rule": {"interval": [{"field": "seconds", "secondsInterval": 30}]}})
claim = pg("Weź następną", [220, y], """
WITH lock AS (SELECT pg_try_advisory_xact_lock(815015) AS got),
stale AS (
  UPDATE voice_notes SET status = CASE WHEN attempts >= 3 THEN 'error' ELSE 'queued' END,
    error = CASE WHEN attempts >= 3 THEN 'Nie udało mi się przepisać tego nagrania.' END,
    finished_at = CASE WHEN attempts >= 3 THEN now() END
  WHERE (SELECT got FROM lock) AND status IN ('transcribing', 'summarizing') AND started_at < now() - interval '45 minutes' RETURNING 1),
busy AS (SELECT 1 FROM voice_notes WHERE status IN ('transcribing', 'summarizing') AND started_at >= now() - interval '45 minutes'),
nxt AS (SELECT id FROM voice_notes WHERE (SELECT got FROM lock) AND NOT EXISTS (SELECT 1 FROM busy) AND status = 'queued' AND audio IS NOT NULL
        ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED),
cl AS (UPDATE voice_notes v SET status = 'transcribing', started_at = now(), attempts = attempts + 1, error = NULL FROM nxt WHERE v.id = nxt.id
       RETURNING v.id, v.user_id, v.mime, v.duration_s, v.name, v.attempts, v.created_at, v.audio)
SELECT id, user_id, mime, duration_s, name, attempts, created_at, encode(audio, 'base64') AS b64 FROM cl""")
plik = code("Nagranie → plik", [440, y], """
const j = $json;
const m = j.mime || 'audio/webm';
const ext = /mp4|m4a|aac|quicktime/.test(m) ? 'm4a' : /ogg/.test(m) ? 'ogg' : /wav/.test(m) ? 'wav' : /mpeg|mp3/.test(m) ? 'mp3' : 'webm';
const buf = Buffer.from(String(j.b64 || '').replace(/\\s+/g, ''), 'base64');
const bin = await this.helpers.prepareBinaryData(buf, 'notatka.' + ext, m);
return [{ json: { id: j.id, user_id: j.user_id, duration_s: j.duration_s, name: j.name, attempts: j.attempts, created_at: j.created_at }, binary: { audio: bin } }];""")
wh = node("Whisper", "n8n-nodes-base.httpRequest", 4.2, [660, y], {
  "method": "POST", "url": WHISPER_URL, "sendBody": True, "contentType": "multipart-form-data",
  "bodyParameters": {"parameters": [
    {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "audio"},
    {"name": "model", "value": WHISPER_MODEL}, {"name": "language", "value": "pl"}, {"name": "vad_filter", "value": "true"}]},
  "options": {"timeout": 2400000}}, onError="continueRegularOutput")
txt = code("Tekst", [880, y], """
const n = $('Nagranie → plik').first().json; const j = $input.first().json;
if (j.error || typeof j.text !== 'string') return [{ json: { ...n, ok: false, retry: true, error: 'Nie udało mi się przepisać nagrania — spróbuję jeszcze raz.' } }];
const FAKE = /^(dzi[eę]kuj[eę] za (uwag[eę]|obejrzenie|ogl[aą]danie)|dzi[eę]ki za (ogl[aą]danie|uwag[eę])|napisy stworzone przez spo[lł]eczno[sś][cć] amara\\.org|do zobaczenia)[.!]*$/i;
const text = j.text.replace(/[ \\t]+/g, ' ').trim();
if (text.length < 5 || FAKE.test(text)) return [{ json: { ...n, ok: false, retry: false, error: 'Nic nie usłyszałam w tym nagraniu.' } }];
return [{ json: { ...n, ok: true, text: text.slice(0, 60000) } }];""")
tok = iff("Przepisane?", [1100, y], "={{ $json.ok === true }}")
fail = pg("Błąd przepisywania", [1320, y + 200], """
UPDATE voice_notes SET
  status = CASE WHEN $2::boolean AND attempts < 3 THEN 'queued' ELSE 'error' END,
  error = CASE WHEN $2::boolean AND attempts < 3 THEN NULL ELSE $3 END,
  finished_at = CASE WHEN $2::boolean AND attempts < 3 THEN NULL ELSE now() END,
  audio = CASE WHEN $2::boolean THEN audio ELSE NULL END
WHERE id = $1::uuid RETURNING id, status""", "={{ [ $json.id, $json.retry === true, $json.error ] }}")
summ = pg("Porządkuję", [1320, y], "UPDATE voice_notes SET status = 'summarizing' WHERE id = $1::uuid RETURNING id", "={{ [ $json.id ] }}")
SYSTEM = open("prompt-notatka-glosowa.txt").read()
assert "{{" not in SYSTEM
llm = node("Model: uporządkuj", "n8n-nodes-base.httpRequest", 4.2, [1540, y], {
  "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
  "sendHeaders": True, "headerParameters": or_headers(),
  "sendBody": True, "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({ model: '" + TEXT_MODEL + "', temperature: 0.2, max_tokens: 1500, reasoning: { enabled: false }, response_format: { type: 'json_object' }, messages: [ { role: 'system', content: "
    + json.dumps(SYSTEM, ensure_ascii=False) + " }, { role: 'user', content: 'Długość nagrania: ' + Math.round(($('Tekst').first().json.duration_s || 0) / 60) + ' min\\n\\n<<<TRANSKRYPCJA>>>\\n' + $('Tekst').first().json.text.slice(0, 40000) + '\\n<<<KONIEC>>>' } ] }) }}",
  "options": {"timeout": 120000}}, credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
build = code("Złóż notatkę", [1760, y], """
// Bez odpowiedzi modelu notatka i tak powstaje — z samą transkrypcją.
const n = $('Tekst').first().json;
let m = {}; try { m = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); } catch (e) {}
const cut = (v, k) => (typeof v === 'string' ? v.replace(/\\s+/g, ' ').trim().slice(0, k) : '');
const pts = (a, k, len) => (Array.isArray(a) ? a : []).map((x) => cut(x, len)).filter((x) => x.length > 1).slice(0, k);
const when = new Date(n.created_at).toLocaleString('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
const title = cut(m.title, 60) || (n.name ? cut(n.name.replace(/\\.[a-z0-9]{2,4}$/i, ''), 60) : 'Notatka głosowa z ' + when);
const decisions = pts(m.decisions, 8, 200); const todo = pts(m.todo, 10, 200);
const lists = [];
if (decisions.length) lists.push({ name: 'Ustalenia', items: decisions.map((text) => ({ text, done: false })) });
if (todo.length) lists.push({ name: 'Do zrobienia', items: todo.map((text) => ({ text, done: false })) });
const mins = Math.max(1, Math.round((n.duration_s || 0) / 60));
const data = { look: { tint: 'blue', icon: 'mic' }, summary: cut(m.summary, 900), lists,
  voice: { duration_s: n.duration_s || 0, name: n.name || '', recorded_at: n.created_at, words: n.text.split(/\\s+/).length } };
const understood = cut(m.understood, 200) || 'Zapisałam notatkę głosową.';
return [{ json: { id: n.id, user_id: n.user_id, title, text: n.text, data, spec: { understood, voice: true },
  push_title: 'Notatka gotowa', push_body: title + (n.duration_s ? ` · ${mins} min` : '') } }];""")
save = pg("Zapisz notatkę", [1980, y], """
WITH it AS (
  INSERT INTO items (user_id, kind, source_text, title, spec, data)
  SELECT user_id, 'note', $2, $3, $4::jsonb, $5::jsonb FROM voice_notes WHERE id = $1::uuid AND status = 'summarizing'
  RETURNING id, user_id),
nt AS (INSERT INTO notifications (item_id, user_id, due_at, title, body) SELECT id, user_id, now(), $6, $7 FROM it RETURNING 1),
v AS (UPDATE voice_notes SET status = 'done', item_id = (SELECT id FROM it), audio = NULL, finished_at = now()
      WHERE id = $1::uuid AND EXISTS (SELECT 1 FROM it) RETURNING id)
SELECT (SELECT id FROM it) AS item_id, (SELECT count(*) FROM nt) AS notified""",
  "={{ [ $json.id, $json.text, $json.title, JSON.stringify($json.spec), JSON.stringify($json.data), $json.push_title, $json.push_body ] }}")
# 402 (wyczerpany klucz Luny): bez notatki z samą transkrypcją i bez kolejnych prób — nagranie zostaje, notatka ma błąd
# z tym samym komunikatem co reszta Luny, a „Spróbuj ponownie” w aplikacji wraca do kolejki po odnowieniu klucza.
klim = iff("Limit klucza?", [1650, y], "={{ " + is_key_limit_js() + " }}")
kfail = pg("Czeka na klucz", [1760, y + 200], """
UPDATE voice_notes SET status = 'error', error = $2, finished_at = now()
WHERE id = $1::uuid AND status = 'summarizing' RETURNING id, status""", "={{ [ $('Tekst').first().json.id, " + json.dumps(KEY_LIMIT, ensure_ascii=False) + " ] }}")
chain(t, claim, plik, wh, txt, tok); link(tok, summ, 0); link(tok, fail, 1); chain(summ, llm, klim); link(klim, kfail, 0); link(klim, build, 1); chain(build, save)

json.dump({"name": "Oboe: Notatki głosowe", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw", "saveDataSuccessExecution": "none"}},
          open("oboe-voice.json", "w"), ensure_ascii=False, indent=1)
print("Oboe: Notatki głosowe —", len(nodes), "węzłów")
