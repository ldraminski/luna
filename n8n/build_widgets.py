"""Buduje workflow n8n „Oboe: Generuj widget”. Wynik: oboe-widgets.json.

Wołany z „Oboe: API” (Execute Workflow, bez czekania) po dodaniu rzeczy, która potrzebuje własnego widgetu,
albo ręcznie z serwera: POST http://127.0.0.1:5678/webhook/oboe/admin/widget {"item_id": "..."} + X-Admin-Token.
"""
import json, uuid

PG = {"postgres": {"id": "IAfnl61Lb7KbTeZi", "name": "Oboe - Postgres (oboe-db)"}}
OR = {"openRouterApi": {"id": "kv8oGsmY1JN14X0m", "name": "OpenRouter account"}}
ADMIN = {"httpHeaderAuth": {"id": "9Rd7Zl7NxIcEvPtL", "name": "Oboe - admin (X-Admin-Token)"}}
TEXT_MODEL = "deepseek/deepseek-v4.1-flash"
# Porównanie 27.09 na tym samym widgecie: DeepSeek 4.1 najlepiej trzyma kontrakt (GLM 5.3 Flash rysował własną kartę,
# a bez limitu rozumowania ucinał kod; Kimi K2.7 Code wychodził poza ramkę i był 20× droższy).
CODE_MODEL = "deepseek/deepseek-v4.1-flash"
REPO = "/data/oboe-widgets"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def llm(name, pos, model, system, user_expr, max_tokens, json_mode=True, reasoning="{ enabled: false }", timeout=120000):
    assert "{{" not in system and "}}" not in system
    body = ("={{ JSON.stringify({ model: '" + model + "', temperature: 0.2, max_tokens: " + str(max_tokens)
            + (", reasoning: " + reasoning if reasoning else "")
            + (", response_format: { type: 'json_object' }" if json_mode else "")
            + ", messages: [ { role: 'system', content: " + json.dumps(system, ensure_ascii=False)
            + " }, { role: 'user', content: " + user_expr + " } ] }) }}")
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, {
      "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
      "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
      "sendHeaders": True, "headerParameters": {"parameters": [
        {"name": "HTTP-Referer", "value": "https://draminski.dev"}, {"name": "X-Title", "value": "Oboe widgety (n8n)"}]},
      "sendBody": True, "specifyBody": "json", "jsonBody": body, "options": {"timeout": timeout}},
      credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
def pg(name, pos, sql, params):
    return node(name, "n8n-nodes-base.postgres", 2.6, pos,
      {"operation": "executeQuery", "query": sql.strip(), "options": {"queryReplacement": params}}, credentials=PG)
def code(name, pos, js):
    return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-460, -380], {"width": 640, "height": 320, "content":
  "## Oboe: Generuj widget\n1. **Dobór** (DeepSeek): czy w bibliotece jest pasujący widget → użyj go ze stanem dla tej rzeczy.\n"
  "2. Jeśli nie — **programista** (GLM 5.3 Flash) pisze jeden plik HTML wg kontraktu (`prompt-widget.txt`).\n"
  "3. **Skan** (Code): twarde reguły — każde trafienie = odrzucenie.\n4. **Guardian** (DeepSeek): przegląd bezpieczeństwa.\n"
  "5. Zatwierdzony → plik `<slug>.v1.html` w `/data/oboe-widgets` + **commit git** + wpis w bibliotece (`widgets`, `widget_versions`).\n"
  "Status w `items.data.widget.status`: generating → ready | rejected. Widget działa w iframe sandbox + CSP sandbox, bez sieci.\n"
  "Źródło: `~/Work/oboe/n8n/build_widgets.py`."})

trig = node("Z API", "n8n-nodes-base.executeWorkflowTrigger", 1.1, [0, 0], {"inputSource": "passthrough"})
wh = node("POST admin/widget", "n8n-nodes-base.webhook", 2, [0, 180],
  {"httpMethod": "POST", "path": "oboe/admin/widget", "authentication": "headerAuth", "responseMode": "onReceived", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
inp = code("Wejście", [220, 80],
  "const id = String(($json.body && $json.body.item_id) || $json.item_id || '');\n"
  "if (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Brak item_id');\nreturn [{ json: { item_id: id } }];")
load = pg("Wczytaj rzecz i bibliotekę", [440, 80], """
WITH upd AS (
  UPDATE items SET data = jsonb_set(data, '{widget}', coalesce(data->'widget', '{}'::jsonb) || '{"status": "generating"}'::jsonb)
  WHERE id = $1::uuid RETURNING id, title, source_text, spec, data)
SELECT upd.*, coalesce((SELECT json_agg(json_build_object('slug', w.slug, 'title', w.title, 'description', w.description,
         'input_schema', w.input_schema)) FROM widgets w WHERE NOT w.builtin AND w.active_version IS NOT NULL), '[]'::json) AS library
FROM upd""", "={{ [ $json.item_id ] }}")

pick = llm("Dobór", [660, 80], TEXT_MODEL, open("prompt-dobor.txt").read(),
  "'Zdanie użytkownika: ' + $json.source_text + '\\\\nTytuł rzeczy: ' + $json.title + '\\\\nPotrzeba: ' + (($json.spec || {}).widget_brief || '') + '\\\\n\\\\nBiblioteka widgetów (JSON):\\\\n' + JSON.stringify($json.library)",
  2000)
chk = code("Sprawdź dobór", [880, 80], r"""
const it = $('Wczytaj rzecz i bibliotekę').first().json;
const lib = it.library || [];
let m;
try { m = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); }
catch (e) { return [{ json: { mode: 'fail', notes: 'Dobór: model nie oddał JSON-a' } }]; }
const state = m.state && typeof m.state === 'object' ? m.state : {};
if (JSON.stringify(state).length > 20000) return [{ json: { mode: 'fail', notes: 'Stan większy niż 20 KB' } }];
if (m.reuse && lib.some((w) => w.slug === m.reuse)) return [{ json: { mode: 'reuse', slug: m.reuse, state } }];
const slug = String(m.slug || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l')
  .replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
if (slug.length < 3 || !m.spec) return [{ json: { mode: 'fail', notes: 'Dobór: brak sluga albo specyfikacji' } }];
return [{ json: { mode: 'new', slug, title: String(m.title || slug).slice(0, 40), description: String(m.description || '').slice(0, 200),
  input_schema: m.input_schema && typeof m.input_schema === 'object' ? m.input_schema : {}, state, spec: String(m.spec).slice(0, 2000) } }];
""")
sw = node("Tryb", "n8n-nodes-base.switch", 3.2, [1100, 80], {"rules": {"values": [
  {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.mode }}", "rightValue": m,
      "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
   "renameOutput": True, "outputKey": m} for m in ("reuse", "new", "fail")]}, "options": {}})

reuse = pg("Użyj istniejącego", [1340, -140], """
UPDATE items SET updated_at = now(), data = jsonb_set(data, '{widget}', jsonb_build_object(
  'slug', $2::text, 'version', (SELECT active_version FROM widgets WHERE slug = $2), 'status', 'ready', 'state', $3::jsonb, 'reused', true))
WHERE id = $1::uuid RETURNING id""",
  "={{ [ $('Wejście').first().json.item_id, $json.slug, JSON.stringify($json.state) ] }}")

coder = llm("Programista", [1340, 80], CODE_MODEL, open("prompt-widget.txt").read(),
  "'Widget: ' + $json.title + '\\\\nOpis: ' + $json.description + '\\\\nSchemat stanu: ' + JSON.stringify($json.input_schema) + '\\\\nPrzykładowy stan: ' + JSON.stringify($json.state) + '\\\\n\\\\nSpecyfikacja:\\\\n' + $json.spec",
  12000, json_mode=False, timeout=240000)
scan = code("Skan", [1560, 80], open("skan.js").read())
guard = llm("Guardian", [1780, 80], TEXT_MODEL, open("prompt-guardian.txt").read(),
  "'Wynik automatycznego skanu: ' + ($json.violations.length ? $json.violations.join('; ') : 'bez trafień') + '\\\\n\\\\nKod widgetu:\\\\n' + $json.html.slice(0, 60000)",
  1500)
verdict = code("Werdykt", [2000, 80], r"""
const s = $('Skan').first().json; const d = $('Sprawdź dobór').first().json;
let g = {};
try { g = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); } catch (e) {}
const problems = [...s.violations, ...(Array.isArray(g.problems) ? g.problems.map(String) : [])];
const approved = g.approved === true && s.violations.length === 0;
return [{ json: { ...d, html: s.html, approved,
  notes: (approved ? '' : 'ODRZUCONY: ' + (problems.join('; ') || 'guardian nie odpowiedział') + '. ') + String(g.notes || '').slice(0, 500) } }];
""")
ok = node("Zatwierdzony?", "n8n-nodes-base.if", 2.2, [2220, 80], {
  "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.approved }}", "rightValue": "",
      "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}})
free = pg("Wolny slug", [2440, 0], """
SELECT CASE WHEN EXISTS (SELECT 1 FROM widgets WHERE slug = $1)
  THEN $1 || '-' || substr(md5(random()::text), 1, 4) ELSE $1 END AS slug""", "={{ [ $json.slug ] }}")
tofile = node("Do pliku", "n8n-nodes-base.convertToFile", 1.1, [2660, 0], {
  "operation": "toText", "sourceProperty": "html", "binaryPropertyName": "data",
  "options": {"fileName": "={{ $json.slug }}.v1.html", "encoding": "utf8"}})
# Convert to File bierze pole html z bieżącego elementu — składamy je w Code przed nim
prep = code("Złóż plik", [2550, 0], "return [{ json: { slug: $json.slug, html: $('Werdykt').first().json.html } }];")
write = node("Zapisz plik", "n8n-nodes-base.readWriteFile", 1.1, [2880, 0], {
  "operation": "write", "fileName": "=" + REPO + "/{{ $('Złóż plik').first().json.slug }}.v1.html", "dataPropertyName": "data", "options": {}})
gadd = node("Git add", "n8n-nodes-base.git", 1.1, [3100, 0], {
  "operation": "add", "repositoryPath": REPO, "pathsToAdd": "={{ $('Złóż plik').first().json.slug }}.v1.html"})
gcom = node("Git commit", "n8n-nodes-base.git", 1.1, [3320, 0], {
  "operation": "commit", "repositoryPath": REPO,
  "message": "=Widget {{ $('Złóż plik').first().json.slug }} v1 — {{ $('Werdykt').first().json.title }} (zatwierdzony przez guardiana)", "options": {}})
save = pg("Zapisz w bibliotece", [3540, 0], """
WITH w AS (
  INSERT INTO widgets (slug, title, description, input_schema, active_version, builtin, created_by)
  VALUES ($1, $2, $3, $4::jsonb, 1, false, (SELECT user_id FROM items WHERE id = $6::uuid)) RETURNING slug),
v AS (
  INSERT INTO widget_versions (slug, version, file_path, guardian, guardian_notes, model)
  SELECT slug, 1, slug || '.v1.html', 'approved', $7, $8 FROM w RETURNING slug)
UPDATE items SET updated_at = now(), data = jsonb_set(data, '{widget}', jsonb_build_object(
  'slug', (SELECT slug FROM v), 'version', 1, 'status', 'ready', 'state', $5::jsonb))
WHERE id = $6::uuid RETURNING id""",
  "={{ [ $('Złóż plik').first().json.slug, $('Werdykt').first().json.title, $('Werdykt').first().json.description, JSON.stringify($('Werdykt').first().json.input_schema), JSON.stringify($('Werdykt').first().json.state), $('Wejście').first().json.item_id, $('Werdykt').first().json.notes, '" + CODE_MODEL + "' ] }}")
rej = pg("Odrzucony", [2440, 220], """
UPDATE items SET updated_at = now(), data = jsonb_set(data, '{widget}', jsonb_build_object(
  'status', 'rejected', 'notes', left($2, 600), 'at', now()))
WHERE id = $1::uuid RETURNING id""", "={{ [ $('Wejście').first().json.item_id, $json.notes || 'nieznany błąd' ] }}")

link(trig, inp); link(wh, inp); link(inp, load); link(load, pick); link(pick, chk); link(chk, sw)
link(sw, reuse, 0); link(sw, coder, 1); link(sw, rej, 2)
link(coder, scan); link(scan, guard); link(guard, verdict); link(verdict, ok)
link(ok, free, 0); link(ok, rej, 1)
link(free, prep); link(prep, tofile); link(tofile, write); link(write, gadd); link(gadd, gcom); link(gcom, save)

json.dump({"name": "Oboe: Generuj widget", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-widgets.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
