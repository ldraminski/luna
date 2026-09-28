"""Buduje workflow n8n „Oboe: Generuj widget”. Wynik: oboe-widgets.json.

Dwa wejścia:
- nowa rzecz (z „Oboe: API” po dodaniu, `spec.widget_brief`): dobór z biblioteki albo nowy widget;
- poprawka (mode=revise, z czatu „Popraw widget” po potwierdzeniu): projekt z czatu + stary kod → nowa wersja.
Ręcznie z serwera: POST http://127.0.0.1:5678/webhook/oboe/admin/widget {"item_id": ...} + X-Admin-Token.
"""
import json, uuid
from config import PG, OR, ADMIN, REFERER

TEXT_MODEL = "deepseek/deepseek-v4.1-flash"
# Decyzja Łukasza 27.09: na razie GLM 5.3 Flash (tańszy output, mocny w Image-to-WebDev). DO PRZETESTOWANIA na większej
# próbie vs DeepSeek 4.1 — w pierwszym teście DeepSeek lepiej trzymał kontrakt (GLM rysował własną kartę i tytuł).
# GLM: rozumowania nie da się wyłączyć, `effort` jest ignorowany — działa tylko reasoning.max_tokens.
CODE_MODEL = "z-ai/glm-5.3-flash"
CODE_OPTS = dict(json_mode=False, reasoning="{ max_tokens: 2000 }", provider="{ sort: 'throughput' }", timeout=240000)
REPO = "/data/oboe-widgets"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def llm(name, pos, model, system, user_expr, max_tokens, json_mode=True, reasoning="{ enabled: false }", timeout=120000, provider=None):
    assert "{{" not in system and "}}" not in system
    body = ("={{ JSON.stringify({ model: '" + model + "', temperature: 0.2, max_tokens: " + str(max_tokens)
            + (", reasoning: " + reasoning if reasoning else "") + (", provider: " + provider if provider else "")
            + (", response_format: { type: 'json_object' }" if json_mode else "")
            + ", messages: [ { role: 'system', content: " + json.dumps(system, ensure_ascii=False)
            + " }, { role: 'user', content: " + user_expr + " } ] }) }}")
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, {
      "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
      "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
      "sendHeaders": True, "headerParameters": {"parameters": [
        {"name": "HTTP-Referer", "value": REFERER}, {"name": "X-Title", "value": "Oboe widgety (n8n)"}]},
      "sendBody": True, "specifyBody": "json", "jsonBody": body, "options": {"timeout": timeout}},
      credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
def pg(name, pos, sql, params):
    return node(name, "n8n-nodes-base.postgres", 2.6, pos,
      {"operation": "executeQuery", "query": sql.strip(), "options": {"queryReplacement": params}}, credentials=PG)
def code(name, pos, js): return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})
def iff(name, pos, expr):
    return node(name, "n8n-nodes-base.if", 2.2, pos, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
      "conditions": [{"id": str(uuid.uuid4()), "leftValue": expr, "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
      "combinator": "and"}, "options": {}})

node("Opis", "n8n-nodes-base.stickyNote", 1, [-460, -460], {"width": 700, "height": 360, "content":
  "## Oboe: Generuj widget\n**Nowa rzecz:** dobór z biblioteki (DeepSeek) → użyj istniejącego ALBO projekt nowego.\n"
  "**Poprawka** (mode=revise, z czatu): projekt z czatu + stary kod z pliku.\n"
  "Dalej wspólnie: **Projekt** → programista (GLM 5.3 Flash) → **skan** → **guardian** → odrzucony? jedna **poprawka** z uwagami → drugi skan i guardian.\n"
  "**Wersja:** poprawka widgetu używanego tylko przez tę rzecz = nowa wersja tego samego sluga (v2, v3…); "
  "widget współdzielony albo nowy = nowy slug (v1) — nie zmieniamy widgetu innym.\n"
  "Plik `<slug>.v<N>.html` + commit git → `widgets`/`widget_versions` (ze specyfikacją).\n"
  "Odrzucona poprawka NIE zabiera starego widgetu — ustawia `revision_error`.\nŹródło: `~/Work/oboe/n8n/build_widgets.py`."})

trig = node("Z API", "n8n-nodes-base.executeWorkflowTrigger", 1.1, [0, 0], {"inputSource": "passthrough"})
wh = node("POST admin/widget", "n8n-nodes-base.webhook", 2, [0, 180],
  {"httpMethod": "POST", "path": "oboe/admin/widget", "authentication": "headerAuth", "responseMode": "onReceived", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
inp = code("Wejście", [220, 80],
  "const b = ($json.body && typeof $json.body === 'object') ? $json.body : $json;\n"
  "const id = String(b.item_id || '');\nif (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Brak item_id');\n"
  "return [{ json: { item_id: id, mode: b.mode === 'revise' ? 'revise' : 'new', chat_id: Number(b.chat_id) || null } }];")
isrev = iff("Poprawka?", [440, 80], "={{ $json.mode === 'revise' }}")

# --- ścieżka: nowa rzecz
load = pg("Wczytaj rzecz i bibliotekę", [660, 200], """
WITH upd AS (
  UPDATE items SET data = jsonb_set(data, '{widget}', coalesce(data->'widget', '{}'::jsonb) || '{"status": "generating"}'::jsonb)
  WHERE id = $1::uuid RETURNING id, title, source_text, spec, data)
SELECT upd.*, coalesce((SELECT json_agg(json_build_object('slug', w.slug, 'title', w.title, 'description', w.description,
         'input_schema', w.input_schema)) FROM widgets w WHERE NOT w.builtin AND w.active_version IS NOT NULL), '[]'::json) AS library
FROM upd""", "={{ [ $json.item_id ] }}")
pick = llm("Dobór", [880, 200], TEXT_MODEL, open("prompt-dobor.txt").read(),
  "'Zdanie użytkownika: ' + $json.source_text + '\\\\nTytuł rzeczy: ' + $json.title + '\\\\nPotrzeba: ' + (($json.spec || {}).widget_brief || '') + '\\\\n\\\\nBiblioteka widgetów (JSON):\\\\n' + JSON.stringify($json.library)",
  2000)
chk = code("Sprawdź dobór", [1100, 200], r"""
const it = $('Wczytaj rzecz i bibliotekę').first().json;
const lib = it.library || [];
let m;
try { m = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); }
catch (e) { return [{ json: { mode: 'fail', notes: 'Dobór: model nie oddał JSON-a' } }]; }
const state = m.state && typeof m.state === 'object' ? m.state : {};
if (JSON.stringify(state).length > 20000) return [{ json: { mode: 'fail', notes: 'Stan większy niż 20 KB' } }];
if (m.reuse && lib.some((w) => w.slug === m.reuse)) return [{ json: { mode: 'reuse', slug: m.reuse, state } }];
if (!m.slug || !m.spec) return [{ json: { mode: 'fail', notes: 'Dobór: brak sluga albo specyfikacji' } }];
return [{ json: { mode: 'new', slug: m.slug, title: m.title, description: m.description, input_schema: m.input_schema, state, spec: m.spec } }];
""")
sw = node("Tryb", "n8n-nodes-base.switch", 3.2, [1320, 200], {"rules": {"values": [
  {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
    "conditions": [{"id": str(uuid.uuid4()), "leftValue": "={{ $json.mode }}", "rightValue": m,
      "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
   "renameOutput": True, "outputKey": m} for m in ("reuse", "new", "fail")]}, "options": {}})
reuse = pg("Użyj istniejącego", [1540, 20], """
UPDATE items SET updated_at = now(), data = jsonb_set(data, '{widget}', jsonb_build_object(
  'slug', $2::text, 'version', (SELECT active_version FROM widgets WHERE slug = $2), 'status', 'ready', 'state', $3::jsonb, 'reused', true))
WHERE id = $1::uuid RETURNING id""",
  "={{ [ $('Wejście').first().json.item_id, $json.slug, JSON.stringify($json.state) ] }}")

# --- ścieżka: poprawka z czatu
rload = pg("Wczytaj poprawkę", [660, -160], """
SELECT i.id, i.title, i.data->'widget' AS widget, c.proposal,
  (SELECT v.file_path FROM widget_versions v WHERE v.slug = i.data->'widget'->>'slug'
     AND v.version = (i.data->'widget'->>'version')::int) AS file_path
FROM items i JOIN widget_chats c ON c.item_id = i.id AND c.id = $2
WHERE i.id = $1::uuid AND jsonb_typeof(c.proposal) = 'object'""", "={{ [ $json.item_id, $json.chat_id ] }}")
hasold = iff("Jest stary kod?", [880, -160], "={{ !!$json.file_path && /^[a-z0-9-]+\\.v\\d+\\.html$/.test($json.file_path) }}")
rfile = node("Czytaj stary kod", "n8n-nodes-base.readWriteFile", 1.1, [1100, -260],
  {"operation": "read", "fileSelector": "=" + REPO + "/{{ $json.file_path }}", "options": {}}, onError="continueRegularOutput")
rtext = node("Stary kod jako tekst", "n8n-nodes-base.extractFromFile", 1.1, [1320, -260],
  {"operation": "text", "destinationKey": "html", "options": {}}, onError="continueRegularOutput")
rproj = code("Projekt z czatu", [1540, -160], r"""
const r = $('Wczytaj poprawkę').first().json; const p = r.proposal || {};
let prev = '';
try { prev = $('Stary kod jako tekst').isExecuted ? String($('Stary kod jako tekst').first().json.html || '') : ''; } catch (e) {}
return [{ json: { mode: 'new', revise: true, slug: (r.widget || {}).slug || p.title, title: p.title, description: p.description,
  // Bezpiecznik: bez stanu w projekcie przenosimy stary stan — dane użytkownika nie mogą zniknąć przy poprawce.
  input_schema: p.input_schema, state: p.state && typeof p.state === 'object' && Object.keys(p.state).length ? p.state : (r.widget || {}).state || {},
  spec: p.spec, prev_html: prev.slice(0, 50000) } }];
""")

# --- wspólne: projekt → kod → kontrola
proj = code("Projekt", [1760, 80], r"""
const m = $json;
const slug = String(m.slug || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l')
  .replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'widget';
return [{ json: { revise: !!m.revise, slug: slug.length < 3 ? 'widget-' + slug : slug, title: String(m.title || slug).slice(0, 40),
  description: String(m.description || '').slice(0, 200), input_schema: m.input_schema && typeof m.input_schema === 'object' ? m.input_schema : {},
  state: m.state && typeof m.state === 'object' ? m.state : {}, spec: String(m.spec || '').slice(0, 2000), prev_html: m.prev_html || '' } }];
""")
WIDGET_SYS = open("prompt-widget.txt").read()
coder = llm("Programista", [1980, 80], CODE_MODEL, WIDGET_SYS,
  "'Widget: ' + $json.title + '\\\\nOpis: ' + $json.description + '\\\\nSchemat stanu: ' + JSON.stringify($json.input_schema) + '\\\\nPrzykładowy stan: ' + JSON.stringify($json.state) + '\\\\n\\\\nSpecyfikacja:\\\\n' + $json.spec + ($json.prev_html ? '\\\\n\\\\nPOPRZEDNIA WERSJA WIDGETU — przebuduj ją zgodnie ze specyfikacją powyżej; zachowaj to, co działało i nie jest objęte zmianą:\\\\n' + $json.prev_html : '')",
  12000, **CODE_OPTS)
scan = code("Skan", [2200, 80], open("skan.js").read())
guard = llm("Guardian", [2420, 80], TEXT_MODEL, open("prompt-guardian.txt").read(),
  "'Wynik automatycznego skanu: ' + ($json.violations.length ? $json.violations.join('; ') : 'bez trafień') + '\\\\n\\\\nKod widgetu:\\\\n' + $json.html.slice(0, 60000)",
  1500)
VERDICT = r"""
const s = $('__SKAN__').first().json; const d = $('Projekt').first().json;
let g = {};
try { g = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); } catch (e) {}
const problems = [...s.violations, ...(Array.isArray(g.problems) ? g.problems.map(String) : [])];
const approved = g.approved === true && s.violations.length === 0;
return [{ json: { ...d, prev_html: undefined, html: s.html, approved,
  notes: (approved ? '__OK__' : '__NO__: ' + (problems.join('; ') || 'guardian nie odpowiedział') + '. ') + String(g.notes || '').slice(0, 500) } }];
"""
verdict = code("Werdykt", [2640, 80], VERDICT.replace("__SKAN__", "Skan").replace("__OK__", "").replace("__NO__", "ODRZUCONY"))
ok = iff("Zatwierdzony?", [2860, 80], "={{ $json.approved }}")
fix = llm("Poprawka", [3080, 300], CODE_MODEL, WIDGET_SYS,
  "'Twój poprzedni kod widgetu został ODRZUCONY. Popraw WSZYSTKIE problemy i oddaj cały poprawiony plik (samo HTML, od <!doctype html>).\\\\n\\\\nProblemy:\\\\n' + $json.notes + '\\\\n\\\\nPoprzedni kod:\\\\n' + $json.html",
  12000, **CODE_OPTS)
scan2 = code("Skan 2", [3300, 300], open("skan.js").read())
guard2 = llm("Guardian 2", [3520, 300], TEXT_MODEL, open("prompt-guardian.txt").read(),
  "'Wynik automatycznego skanu: ' + ($json.violations.length ? $json.violations.join('; ') : 'bez trafień') + '\\\\n\\\\nKod widgetu:\\\\n' + $json.html.slice(0, 60000)",
  1500)
verdict2 = code("Werdykt 2", [3740, 300], VERDICT.replace("__SKAN__", "Skan 2").replace("__OK__", "Zatwierdzony po poprawce. ").replace("__NO__", "ODRZUCONY po poprawce"))
ok2 = iff("Zatwierdzony po poprawce?", [3960, 300], "={{ $json.approved }}")

# --- zapis
ver = pg("Wersja", [4180, 0], """
WITH cur AS (
  SELECT w.slug, (SELECT coalesce(max(v.version), 0) FROM widget_versions v WHERE v.slug = w.slug) AS maxv,
    EXISTS (SELECT 1 FROM items x WHERE x.data->'widget'->>'slug' = w.slug AND x.id <> $3::uuid) AS shared
  FROM widgets w WHERE w.slug = $1 AND NOT w.builtin),
own AS (SELECT * FROM cur WHERE $2::boolean AND NOT shared)
SELECT CASE WHEN EXISTS (SELECT 1 FROM own) THEN $1
            WHEN EXISTS (SELECT 1 FROM widgets WHERE slug = $1) THEN $1 || '-' || substr(md5(random()::text), 1, 4)
            ELSE $1 END AS slug,
       coalesce((SELECT maxv + 1 FROM own), 1) AS version""",
  "={{ [ $json.slug, $json.revise, $('Wejście').first().json.item_id ] }}")
prep = code("Złóż plik", [4400, 0],
  "const v = $('Werdykt 2').isExecuted ? $('Werdykt 2').first().json : $('Werdykt').first().json;\n"
  "return [{ json: { ...v, slug: $json.slug, version: Number($json.version), file: $json.slug + '.v' + $json.version + '.html' } }];")
tofile = node("Do pliku", "n8n-nodes-base.convertToFile", 1.1, [4620, 0], {
  "operation": "toText", "sourceProperty": "html", "binaryPropertyName": "data", "options": {"fileName": "={{ $json.file }}", "encoding": "utf8"}})
write = node("Zapisz plik", "n8n-nodes-base.readWriteFile", 1.1, [4840, 0], {
  "operation": "write", "fileName": "=" + REPO + "/{{ $('Złóż plik').first().json.file }}", "dataPropertyName": "data", "options": {}})
gadd = node("Git add", "n8n-nodes-base.git", 1.1, [5060, 0], {
  "operation": "add", "repositoryPath": REPO, "pathsToAdd": "={{ $('Złóż plik').first().json.file }}"})
gcom = node("Git commit", "n8n-nodes-base.git", 1.1, [5280, 0], {
  "operation": "commit", "repositoryPath": REPO,
  "message": "=Widget {{ $('Złóż plik').first().json.slug }} v{{ $('Złóż plik').first().json.version }} — {{ $('Złóż plik').first().json.title }}{{ $('Złóż plik').first().json.revise ? ' (poprawka z czatu)' : '' }} (zatwierdzony przez guardiana)", "options": {}})
save = pg("Zapisz w bibliotece", [5500, 0], """
WITH w AS (
  INSERT INTO widgets (slug, title, description, input_schema, active_version, builtin, created_by)
  VALUES ($1, $2, $3, $4::jsonb, $9::int, false, (SELECT user_id FROM items WHERE id = $6::uuid))
  ON CONFLICT (slug) DO UPDATE SET active_version = EXCLUDED.active_version, title = EXCLUDED.title,
    description = EXCLUDED.description, input_schema = EXCLUDED.input_schema
  RETURNING slug),
v AS (
  INSERT INTO widget_versions (slug, version, file_path, guardian, guardian_notes, model, spec, item_id)
  SELECT slug, $9::int, slug || '.v' || $9 || '.html', 'approved', $7, $8, $10, $6::uuid FROM w RETURNING slug)
UPDATE items SET updated_at = now(), data = jsonb_set(data, '{widget}', jsonb_build_object(
  'slug', (SELECT slug FROM v), 'version', $9::int, 'status', 'ready', 'state', $5::jsonb))
WHERE id = $6::uuid RETURNING id""",
  "={{ [ $json.slug, $json.title, $json.description, JSON.stringify($json.input_schema), JSON.stringify($json.state), $('Wejście').first().json.item_id, $json.notes, '" + CODE_MODEL + "', $json.version, $json.spec ] }}")
# Git commit nie przenosi pól — zapis bierze je z „Złóż plik”
savein = code("Dane do zapisu", [5390, 0], "return [{ json: $('Złóż plik').first().json }];")
rej = pg("Odrzucony", [4180, 400], """
UPDATE items SET updated_at = now(), data = CASE
  WHEN data->'widget'->>'slug' IS NOT NULL AND (data->'widget'->>'pending')::boolean IS TRUE
    THEN jsonb_set(data, '{widget}', (data->'widget' - 'pending') || jsonb_build_object('revision_error', left($2, 600)))
  ELSE jsonb_set(data, '{widget}', jsonb_build_object('status', 'rejected', 'notes', left($2, 600), 'at', now())) END
WHERE id = $1::uuid RETURNING id""", "={{ [ $('Wejście').first().json.item_id, $json.notes || 'nieznany błąd' ] }}")

link(trig, inp); link(wh, inp); link(inp, isrev)
link(isrev, rload, 0); link(isrev, load, 1)
link(rload, hasold); link(hasold, rfile, 0); link(hasold, rproj, 1); link(rfile, rtext); link(rtext, rproj); link(rproj, proj)
link(load, pick); link(pick, chk); link(chk, sw); link(sw, reuse, 0); link(sw, proj, 1); link(sw, rej, 2)
link(proj, coder); link(coder, scan); link(scan, guard); link(guard, verdict); link(verdict, ok)
link(ok, ver, 0); link(ok, fix, 1); link(fix, scan2); link(scan2, guard2); link(guard2, verdict2); link(verdict2, ok2)
link(ok2, ver, 0); link(ok2, rej, 1)
link(ver, prep); link(prep, tofile); link(tofile, write); link(write, gadd); link(gadd, gcom); link(gcom, savein); link(savein, save)

json.dump({"name": "Oboe: Generuj widget", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-widgets.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
