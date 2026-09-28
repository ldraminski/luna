"""Buduje workflow n8n „Oboe: Streść stronę”. Wynik: oboe-summary.json.

Wołany w tle: z „Oboe: API” po dodaniu rzeczy z `spec.summarize` (reason=created) i po „Sprawdź teraz” (reason=manual),
z „Oboe: Harmonogram” w terminie cyklicznym (reason=scheduled — wtedy push tylko przy ISTOTNEJ zmianie),
ręcznie z serwera: POST http://127.0.0.1:5678/webhook/oboe/admin/summarize {"item_id": ...} + X-Admin-Token.
"""
import json, uuid
from config import PG, OR, ADMIN, REFERER

TEXT_MODEL = "deepseek/deepseek-v4.1-flash"
UA = "Mozilla/5.0 (compatible; OboeBot/1.0; +" + REFERER + ")"

nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
def pg(name, pos, sql, params):
    return node(name, "n8n-nodes-base.postgres", 2.6, pos,
      {"operation": "executeQuery", "query": sql.strip(), "options": {"queryReplacement": params}}, credentials=PG)
def code(name, pos, js): return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})
def iff(name, pos, expr):
    return node(name, "n8n-nodes-base.if", 2.2, pos, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
      "conditions": [{"id": str(uuid.uuid4()), "leftValue": expr, "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
      "combinator": "and"}, "options": {}})
def http_get(name, pos, url, headers, fmt="json", redirects=True, timeout=15000):
    opts = {"timeout": timeout, "response": {"response": {"fullResponse": fmt == "text", "neverError": True, "responseFormat": fmt}}}
    if not redirects: opts["redirect"] = {"redirect": {"followRedirects": False}}
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, {"method": "GET", "url": url, "sendHeaders": True,
      "headerParameters": {"parameters": [{"name": k, "value": v} for k, v in headers]}, "options": opts}, onError="continueRegularOutput")

node("Opis", "n8n-nodes-base.stickyNote", 1, [-460, -420], {"width": 660, "height": 330, "content":
  "## Oboe: Streść stronę\n1. **Ochrona SSRF:** adres podaje użytkownik, pobiera nasz serwer → DNS przez DoH (A + AAAA) i tylko publiczne IP. "
  "Przekierowania NIE są śledzone automatycznie — jedno ręczne, z ponownym sprawdzeniem DNS.\n"
  "2. HTML → tekst (Code), odcisk FNV — gdy tekst się nie zmienił, model nie jest pytany.\n"
  "3. DeepSeek 4.1: nagłówek + punkty (+ co się zmieniło). Treść strony = dane, nie polecenia.\n"
  "4. `items.data.summary` + `summary_status` (working/ready/error). Push tylko przy reason=scheduled i istotnej zmianie.\n"
  "Pozostałe ryzyko: DNS rebinding między sprawdzeniem a pobraniem — akceptowalne przy wąskim gronie.\n"
  "Źródło: `~/Work/oboe/n8n/build_summary.py`."})

trig = node("Z innego workflow", "n8n-nodes-base.executeWorkflowTrigger", 1.1, [0, 0], {"inputSource": "passthrough"})
wh = node("POST admin/summarize", "n8n-nodes-base.webhook", 2, [0, 180],
  {"httpMethod": "POST", "path": "oboe/admin/summarize", "authentication": "headerAuth", "responseMode": "onReceived", "options": {}},
  credentials=ADMIN, webhookId=str(uuid.uuid4()))
inp = code("Wejście", [220, 80],
  "const b = ($json.body && typeof $json.body === 'object') ? $json.body : $json;\n"
  "const id = String(b.item_id || '');\nif (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Brak item_id');\n"
  "return [{ json: { item_id: id, reason: ['created', 'manual', 'scheduled'].includes(b.reason) ? b.reason : 'manual' } }];")
load = pg("Wczytaj", [440, 80], """
UPDATE items SET data = data || '{"summary_status": "working"}'::jsonb
WHERE id = $1::uuid AND spec->>'url' IS NOT NULL AND status = 'active'
RETURNING id, user_id, title, spec->>'url' AS url, data->'summary' AS prev""", "={{ [ $json.item_id ] }}")

def fetch_pass(sfx, x0, y, url_expr):
    a = code("Adres do pobrania" + sfx, [x0, y], "const url = " + url_expr + ";\n"
      "const m = /^https?:\\/\\/([a-z0-9.-]+\\.[a-z]{2,})(:\\d+)?(\\/|$|\\?)/i.exec(url || '');\n"
      "if (!m) return [{ json: { ok: false, url, host: '', error: 'To nie wygląda na adres strony.' } }];\n"
      "if (m[2] && ![':80', ':443'].includes(m[2])) return [{ json: { ok: false, url, host: m[1], error: 'Tego adresu nie otworzę — nietypowy port.' } }];\n"
      "return [{ json: { ok: true, url, host: m[1].toLowerCase() } }];")
    d4 = http_get("DNS A" + sfx, [x0 + 220, y], "=https://cloudflare-dns.com/dns-query?type=A&name={{ encodeURIComponent($json.host) }}", [("accept", "application/dns-json")])
    d6 = http_get("DNS AAAA" + sfx, [x0 + 440, y], "=https://cloudflare-dns.com/dns-query?type=AAAA&name={{ encodeURIComponent($('Adres do pobrania" + sfx + "').first().json.host) }}", [("accept", "application/dns-json")])
    chk = code("Sprawdź adres" + sfx, [x0 + 660, y],
      open("sprawdz-adres.js").read()
      .replace("$('Adres do pobrania').first().json.url", "$('Adres do pobrania" + sfx + "').first().json.url")
      .replace("for (const it of $input.all()) for (const a of (it.json.Answer || []))",
               "for (const src of [$('DNS A" + sfx + "').first().json, $json]) for (const a of (src.Answer || []))")
      .replace("const url = $('Adres", "if (!$('Adres do pobrania" + sfx + "').first().json.ok) return [{ json: $('Adres do pobrania" + sfx + "').first().json }];\nconst url = $('Adres", 1))
    ok = iff("Adres OK?" + sfx, [x0 + 880, y], "={{ $json.ok }}")
    get = http_get("Pobierz stronę" + sfx, [x0 + 1100, y], "={{ $json.url }}",
      [("User-Agent", UA), ("Accept", "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"), ("Accept-Language", "pl,en;q=0.7")],
      fmt="text", redirects=False, timeout=20000)
    link(a, d4); link(d4, d6); link(d6, chk); link(chk, ok); link(ok, get, 0)
    return a, ok, get

a1, ok1, get1 = fetch_pass("", 660, 80, "$('Wczytaj').first().json.url")
redir = code("Przekierowanie?", [1980, 80], r"""
const s = Number($json.statusCode || 0); const loc = String(($json.headers || {}).location || '');
if (![301, 302, 303, 307, 308].includes(s) || !loc) return [{ json: { ...$json, redirect: false } }];
const base = $('Adres do pobrania').first().json.url; const origin = (base.match(/^https?:\/\/[^/?#]+/i) || [''])[0];
const next = /^https?:\/\//i.test(loc) ? loc : loc.startsWith('//') ? 'https:' + loc : loc.startsWith('/') ? origin + loc : origin + '/' + loc;
return [{ json: { redirect: true, next: next.slice(0, 500) } }];
""")
isr = iff("Jest przekierowanie?", [2200, 80], "={{ $json.redirect }}")
a2, ok2, get2 = fetch_pass(" 2", 2420, 260, "$('Przekierowanie?').first().json.next")
ext = code("Wyciągnij tekst", [3640, 80], open("wyciagnij-tekst.js").read())
extok = iff("Tekst OK?", [3860, 80], "={{ $json.ok }}")
same = iff("Bez zmian?", [4080, 0], "={{ !!$('Wczytaj').first().json.prev && ($('Wczytaj').first().json.prev || {}).hash === $json.hash }}")
nochg = pg("Zapisz: bez zmian", [4300, -120], """
UPDATE items SET data = jsonb_set(data || '{"summary_status": "ready"}'::jsonb, '{summary,checked_at}', to_jsonb(now()))
WHERE id = $1::uuid RETURNING id""", "={{ [ $('Wejście').first().json.item_id ] }}")
SYSTEM = open("prompt-streszczenie.txt").read(); assert "{{" not in SYSTEM and "}}" not in SYSTEM
llm = node("DeepSeek: streść", "n8n-nodes-base.httpRequest", 4.2, [4300, 60], {
  "method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi",
  "sendHeaders": True, "headerParameters": {"parameters": [{"name": "HTTP-Referer", "value": REFERER}, {"name": "X-Title", "value": "Oboe streszczenia (n8n)"}]},
  "sendBody": True, "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({ model: '" + TEXT_MODEL + "', temperature: 0.2, max_tokens: 1200, reasoning: { enabled: false }, response_format: { type: 'json_object' }, messages: [ { role: 'system', content: "
    + json.dumps(SYSTEM, ensure_ascii=False) + " }, { role: 'user', content: 'Adres: ' + $('Wczytaj').first().json.url + '\\\\nTytuł: ' + $json.title + '\\\\nOpis: ' + $json.desc + '\\\\n\\\\nPoprzednie streszczenie: ' + ($('Wczytaj').first().json.prev ? JSON.stringify({ headline: $('Wczytaj').first().json.prev.headline, bullets: $('Wczytaj').first().json.prev.bullets }) : 'brak') + '\\\\n\\\\n<<<TEKST STRONY>>>\\\\n' + $json.text + '\\\\n<<<KONIEC TEKSTU>>>' } ] }) }}",
  "options": {"timeout": 90000}}, credentials=OR, retryOnFail=True, maxTries=2, onError="continueRegularOutput")
parse = code("Sprawdź streszczenie", [4520, 60], r"""
const t = $('Wyciągnij tekst').first().json; const prev = $('Wczytaj').first().json.prev;
let m;
try { m = JSON.parse(String($json.choices?.[0]?.message?.content || '').replace(/^```(json)?|```$/g, '').trim()); }
catch (e) { return [{ json: { ok: false, error: 'Nie udało mi się streścić tej strony.' } }]; }
const cut = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');
const summary = { headline: cut(m.headline, 160), bullets: (Array.isArray(m.bullets) ? m.bullets : []).map((b) => cut(String(b), 180)).filter(Boolean).slice(0, 5),
  changed: !!prev && m.changed === true, changes: prev ? cut(m.changes, 240) : '', page_title: t.title, hash: t.hash, checked_at: new Date().toISOString() };
if (!summary.headline) return [{ json: { ok: false, error: 'Nie udało mi się streścić tej strony.' } }];
return [{ json: { ok: true, summary } }];
""")
pok = iff("Streszczenie OK?", [4740, 60], "={{ $json.ok }}")
save = pg("Zapisz streszczenie", [4960, 0], """
UPDATE items SET updated_at = now(), data = (data - 'summary_error') || jsonb_build_object('summary', $2::jsonb, 'summary_status', 'ready')
WHERE id = $1::uuid RETURNING id, user_id, title""", "={{ [ $('Wejście').first().json.item_id, JSON.stringify($json.summary) ] }}")
notif = iff("Powiadomić o zmianie?", [5180, 0], "={{ $('Wejście').first().json.reason === 'scheduled' && $('Sprawdź streszczenie').first().json.summary.changed }}")
push = pg("Powiadomienie o zmianie", [5400, 0], """
INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)
VALUES ($1::uuid, $2::uuid, now(), '{push}', left('Zmiana: ' || $3, 80), left($4, 200)) RETURNING id""",
  "={{ [ $json.id, $json.user_id, $json.title, $('Sprawdź streszczenie').first().json.summary.changes || $('Sprawdź streszczenie').first().json.summary.headline ] }}")
err = pg("Zapisz błąd", [4300, 320], """
UPDATE items SET data = data || jsonb_build_object('summary_status', 'error', 'summary_error', left($2, 200))
WHERE id = $1::uuid RETURNING id""", "={{ [ $('Wejście').first().json.item_id, $json.error || 'Nie udało się streścić strony.' ] }}")

link(trig, inp); link(wh, inp); link(inp, load); link(load, a1)
link(ok1, err, 1); link(get1, redir); link(redir, isr); link(isr, a2, 0); link(isr, ext, 1)
link(ok2, err, 1); link(get2, ext)
link(ext, extok); link(extok, same, 0); link(extok, err, 1)
link(same, nochg, 0); link(same, llm, 1); link(llm, parse); link(parse, pok); link(pok, save, 0); link(pok, err, 1)
link(save, notif); link(notif, push, 0)

json.dump({"name": "Oboe: Streść stronę", "nodes": nodes, "connections": conns,
           "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-summary.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
