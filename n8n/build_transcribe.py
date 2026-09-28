"""Buduje workflow n8n „Oboe: Dyktowanie” — głosówka → tekst (Łukasz 28.09.2026). Wynik: oboe-transcribe.json.

POST /api/transcribe {audio: "data:audio/...;base64,..."}  — z kluczem użytkownika. Odpowiedź: {status: 200, text}.
Whisper działa u nas: kontener `whisper` (speaches, large-v3-turbo int8, CPU) w /opt/infra, bez portu publicznego.
Nagranie nie jest nigdzie zapisywane — idzie prosto do Whispera, dalej aplikacja wysyła tekst jak zwykły wpis.
vad_filter=true: bez niego Whisper na ciszy/szumie zmyśla „Dziękuję za uwagę.” / „Dzięki za oglądanie!” (sprawdzone 28.09).
"""
import json, uuid

PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
TOKEN = "($json.headers.authorization || '').replace(/^Bearer\\s+/i, '')"
ME = """me AS (
  UPDATE sessions SET last_used_at = now()
  WHERE token_hash = encode(digest($1, 'sha256'), 'hex') AND expires_at > now()
  RETURNING user_id)"""
WHISPER = "http://whisper:8000/v1/audio/transcriptions"
MODEL = "deepdml/faster-whisper-large-v3-turbo-ct2"
AUDIO_OK = "/^data:audio\\/[a-z0-9.+-]+(;[a-z0-9=._-]+)*;base64,[A-Za-z0-9+\\/=]+$/i.test(String($('POST transcribe').item.json.body.audio || ''))"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def respond(name, pos, body):
    return node(name, "n8n-nodes-base.respondToWebhook", 1.1, pos,
      {"respondWith": "json", "responseBody": body, "options": {"responseCode": "={{ $json.result.status || 200 }}"}})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-400, -220], {"width": 520, "height": 240, "content":
  "## Oboe: Dyktowanie\nMikrofon w Lunie → `POST /api/transcribe {audio: dataURL}` → Whisper u nas (kontener `whisper`, "
  "large-v3-turbo, CPU) → `{text}`. Aplikacja wysyła tekst dalej jak zwykły wpis.\n"
  "Nagranie nie jest zapisywane. `vad_filter` = cisza daje pusty tekst zamiast zmyśleń.\n"
  "Źródło: `~/Work/oboe/n8n/build_transcribe.py`."})
w = node("POST transcribe", "n8n-nodes-base.webhook", 2, [0, 0],
  {"httpMethod": "POST", "path": "oboe/transcribe", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4()))
sess = node("Sesja", "n8n-nodes-base.postgres", 2.6, [220, 0],
  {"operation": "executeQuery", "query": f"WITH {ME}\nSELECT (SELECT user_id FROM me) AS user_id",
   "options": {"queryReplacement": "={{ [ " + TOKEN + " ] }}"}}, credentials=PG)
iff = node("Zalogowany i jest nagranie?", "n8n-nodes-base.if", 2.2, [440, 0], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [
      {"id": str(uuid.uuid4()), "leftValue": "={{ $json.user_id }}", "rightValue": "",
       "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}},
      {"id": str(uuid.uuid4()), "leftValue": "={{ " + AUDIO_OK + " }}", "rightValue": "",
       "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
deny = node("Odmów", "n8n-nodes-base.respondToWebhook", 1.1, [660, 180],
  {"respondWith": "json", "options": {"responseCode": "={{ $json.user_id ? 400 : 401 }}"},
   "responseBody": "={{ $json.user_id ? { status: 400, error: 'Nie dostałam nagrania — spróbuj jeszcze raz.' } : { status: 401, error: 'Zaloguj się ponownie' } }}"})
plik = node("Nagranie → plik", "n8n-nodes-base.code", 2, [660, 0], {"jsCode": """
const url = String($('POST transcribe').first().json.body.audio);
const mime = url.slice(5, url.indexOf(';')).toLowerCase();
const ext = mime.includes('mp4') || mime.includes('m4a') || mime.includes('aac') ? 'm4a'
  : mime.includes('ogg') ? 'ogg' : mime.includes('wav') ? 'wav' : mime.includes('mpeg') ? 'mp3' : 'webm';
const buf = Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
const bin = await this.helpers.prepareBinaryData(buf, 'glosowka.' + ext, mime);
return [{ json: { bytes: buf.length }, binary: { audio: bin } }];""".strip()})
wh = node("Whisper", "n8n-nodes-base.httpRequest", 4.2, [880, 0], {
  "method": "POST", "url": WHISPER,
  "sendBody": True, "contentType": "multipart-form-data",
  "bodyParameters": {"parameters": [
    {"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "audio"},
    {"name": "model", "value": MODEL},
    {"name": "language", "value": "pl"},
    {"name": "vad_filter", "value": "true"}]},
  "options": {"timeout": 90000}},
  retryOnFail=True, maxTries=2, onError="continueRegularOutput")
txt = node("Tekst", "n8n-nodes-base.code", 2, [1100, 0], {"jsCode": """
const j = $input.first().json;
if (j.error || typeof j.text !== 'string') return [{ json: { result: { status: 502, error: 'Nie udało mi się odsłuchać nagrania — spróbuj jeszcze raz albo napisz.' } } }];
// Klasyczne zmyślenia Whispera po polsku (napisy z filmów) — gdyby VAD coś przepuścił.
const FAKE = /^(dzi[eę]kuj[eę] za (uwag[eę]|obejrzenie|ogl[aą]danie)|dzi[eę]ki za (ogl[aą]danie|uwag[eę])|napisy stworzone przez spo[lł]eczno[sś][cć] amara\\.org|do zobaczenia)[.!]*$/i;
const text = j.text.replace(/\\s+/g, ' ').trim();
if (!text || FAKE.test(text)) return [{ json: { result: { status: 422, error: 'Nic nie usłyszałam — spróbuj jeszcze raz, bliżej telefonu.' } } }];
return [{ json: { result: { status: 200, text: text.slice(0, 1000) } } }];""".strip()})
r = respond("Odpowiedz: tekst", [1320, 0], "={{ $json.result }}")
link(w, sess); link(sess, iff); link(iff, plik, 0); link(iff, deny, 1); link(plik, wh); link(wh, txt); link(txt, r)

json.dump({"name": "Oboe: Dyktowanie", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-transcribe.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
