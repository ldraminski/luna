"""Buduje workflow n8n „Oboe: Kopia zapasowa” — codziennie 3:30 pełny eksport danych Luny do PRYWATNEGO bucketu R2. Wynik: oboe-backup.json.

Eksport logiczny (JSON, gzip): wszystkie tabele oboe-db + pliki widgetów z /data/oboe-widgets. Nic nie zostaje na serwerze (n8n nie ma
trwałego katalogu na pliki) — kopia idzie od razu poza OVH. Błąd wysyłki → powiadomienie push + mail dla adminów Luny.
Test / ręcznie: POST /webhook/oboe/admin/backup (X-Admin-Token, tylko z serwera) → {plik, bajty, tabele}.
Odtworzenie: README repo, sekcja „Kopia zapasowa”.
"""
import json, uuid
from config import PG, ADMIN, R2, BACKUP_BUCKET
BUCKET = BACKUP_BUCKET
TABLES = ["users", "sessions", "items", "notifications", "push_subscriptions", "widget_chats", "widgets", "widget_versions",
          "access_requests", "access_log", "item_photos", "reports"]
nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
node("Opis", "n8n-nodes-base.stickyNote", 1, [-420, -300], {"width": 600, "height": 250, "content":
  "## Oboe: Kopia zapasowa (Luna)\nCodziennie 3:30: eksport WSZYSTKICH tabel oboe-db + plików widgetów → JSON → gzip → prywatny bucket R2 `" + BUCKET + "`,\n"
  "klucz `oboe/RRRR-MM-DD.json.gz`. Nic nie zostaje na serwerze. Retencja: reguła cyklu życia w R2 (30 dni).\n"
  "Błąd wysyłki → powiadomienie push + mail dla adminów. Ręcznie: `POST /webhook/oboe/admin/backup` (X-Admin-Token).\n"
  "Źródło: `~/Work/oboe/n8n/build_backup.py`; odtworzenie: README repo."})
cron = node("Codziennie 3:30", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0], {"rule": {"interval": [{"field": "cronExpression", "expression": "30 3 * * *"}]}})
hook = node("POST admin/backup", "n8n-nodes-base.webhook", 2, [0, 200],
  {"httpMethod": "POST", "path": "oboe/admin/backup", "authentication": "headerAuth", "responseMode": "lastNode", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
dump = node("Eksport tabel", "n8n-nodes-base.postgres", 2.6, [220, 100], {"operation": "executeQuery", "query":
  "SELECT json_build_object('app', 'luna (oboe)', 'version', 1, 'created_at', now(), 'tables', json_build_object(\n  "
  + ",\n  ".join(f"'{t}', (SELECT coalesce(json_agg(x), '[]'::json) FROM {t} x)" for t in TABLES) + ")) AS dump", "options": {}}, credentials=PG)
files = node("Pliki widgetów", "n8n-nodes-base.readWriteFile", 1, [440, 100], {"operation": "read", "fileSelector": "/data/oboe-widgets/*.html", "options": {}},
  alwaysOutputData=True, onError="continueRegularOutput")
pack = node("Złóż kopię", "n8n-nodes-base.code", 2, [660, 100], {"jsCode": r"""// Jedna kopia: tabele + pliki widgetów (tekst HTML) → JSON → plik do spakowania.
const dump = $('Eksport tabel').first().json.dump;
const widgets = {};
for (let i = 0; i < $input.all().length; i++) {
  const it = $input.all()[i]; if (!it.binary?.data) continue;
  const buf = await this.helpers.getBinaryDataBuffer(i, 'data');
  widgets[it.binary.data.fileName] = buf.toString('utf8');
}
dump.widget_files = widgets;
const day = DateTime.now().setZone('Europe/Warsaw').toISODate();
const body = Buffer.from(JSON.stringify(dump));
const counts = Object.fromEntries(Object.entries(dump.tables).map(([k, v]) => [k, v.length]));
return [{ json: { file: `oboe/${day}.json`, bytes_raw: body.length, counts, widgets: Object.keys(widgets).length },
          binary: { data: await this.helpers.prepareBinaryData(body, `${day}.json`, 'application/json') } }];"""})
gz = node("Gzip", "n8n-nodes-base.compression", 1.1, [880, 100], {"operation": "compress", "binaryPropertyName": "data", "outputFormat": "gzip",
  "binaryPropertyOutput": "data"})
up_params = {"operation": "upload", "bucketName": BUCKET, "fileName": "={{ $('Złóż kopię').first().json.file }}.gz", "additionalFields": {}}
up = node("Wyślij do R2", "n8n-nodes-base.s3", 1, [1100, 100], up_params, onError="continueRegularOutput",
  **({"credentials": R2} if R2 else {"disabled": True}))
res = node("Wynik", "n8n-nodes-base.code", 2, [1320, 100], {"jsCode": r"""const k = $('Złóż kopię').first().json;
const gz = $('Gzip').first().binary?.data;
const sent = __R2__ && !$json.error && !$('Wyślij do R2').first()?.json?.error;   // bez credentialu R2 węzeł jest wyłączony i tylko przepuszcza dane
return [{ json: { ok: sent, file: k.file + '.gz', bytes_gz: gz?.fileSize || null, bytes_raw: k.bytes_raw, tables: k.counts, widgets: k.widgets,
  error: sent ? null : String($json.error?.message || $json.error || 'wysyłka wyłączona (brak credentialu R2)') } }];""".replace("__R2__", "true" if R2 else "false")})
bad = node("Błąd?", "n8n-nodes-base.if", 2.2, [1540, 100], {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
  "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.ok === false }}", "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
  "combinator": "and"}, "options": {}})
alarm = node("Powiadom adminów", "n8n-nodes-base.postgres", 2.6, [1760, 40], {"operation": "executeQuery", "query":
  "INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)\nSELECT NULL, id, now(), '{push,email}', 'Luna: kopia zapasowa się nie udała', $1 FROM users WHERE is_admin\nRETURNING user_id",
  "options": {"queryReplacement": "={{ [ 'Dzisiejsza kopia danych Luny nie trafiła do R2: ' + String($json.error).slice(0, 150) + '. Dane są bezpieczne w bazie, ale sprawdź to.' ] }}"}},
  credentials=PG)
link(cron, dump); link(hook, dump); link(dump, files); link(files, pack); link(pack, gz); link(gz, up); link(up, res); link(res, bad); link(bad, alarm, 0)
json.dump({"name": "Oboe: Kopia zapasowa", "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-backup.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów;", "R2:", "podłączone" if R2 else "wyłączone (czeka na credential)")
