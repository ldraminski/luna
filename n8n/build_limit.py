"""Buduje workflow n8n „Oboe: Limit klucza” — co godzinę sprawdza zużycie klucza OpenRoutera Luny. Wynik: oboe-limit.json.

Progi 80 / 95 / 100% → powiadomienie dla adminów Luny (push + mail, przez „Oboe: Harmonogram”), każdy próg raz.
Stan progu w static data workflow; spadek poniżej 50% (Łukasz podniósł limit / reset) zeruje. Kwoty w zł (kurs NBP), USD w nawiasie.
"""
import json, uuid
from config import PG, OR
nodes, conns = [], {}
def node(name, typ, ver, pos, params, **kw):
    n = {"id": str(uuid.uuid4()), "name": name, "type": typ, "typeVersion": ver, "position": pos, "parameters": params}
    n.update(kw); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})
node("Opis", "n8n-nodes-base.stickyNote", 1, [-420, -260], {"width": 560, "height": 220, "content":
  "## Oboe: Limit klucza (Luna)\nCo godzinę: `GET openrouter.ai/api/v1/key` kluczem Luny (credential „OpenRouter - Luna”, limit ustawia Łukasz).\n"
  "Progi 80/95/100% → powiadomienie push + mail dla `users.is_admin`, każdy raz (static data). <50% → reset.\n"
  "Kwoty w zł wg kursu NBP. Źródło: `~/Work/oboe/n8n/build_limit.py`."})
cron = node("Co godzinę", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 0], {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}})
key = node("Zużycie klucza", "n8n-nodes-base.httpRequest", 4.2, [220, 0], {"method": "GET", "url": "https://openrouter.ai/api/v1/key",
  "authentication": "predefinedCredentialType", "nodeCredentialType": "openRouterApi", "options": {"timeout": 30000}},
  credentials=OR, retryOnFail=True, maxTries=3)
nbp = node("Kurs USD (NBP)", "n8n-nodes-base.httpRequest", 4.2, [440, 0], {"method": "GET",
  "url": "https://api.nbp.pl/api/exchangerates/rates/a/usd/?format=json", "options": {"timeout": 15000}}, onError="continueRegularOutput")
chk = node("Próg?", "n8n-nodes-base.code", 2, [660, 0], {"jsCode": r"""const k = $('Zużycie klucza').first().json.data || {};
const usd = Number($json.rates?.[0]?.mid) || 3.7;          // NBP; awaryjnie ~3,70
const limit = Number(k.limit); const used = Number(k.usage) || 0;
if (!(limit > 0)) return [];                              // klucz bez limitu — nie ma czego pilnować
const pct = used / limit * 100;
const st = $getWorkflowStaticData('global');
if (pct < 50) { st.level = 0; return []; }
const level = pct >= 100 ? 100 : pct >= 95 ? 95 : pct >= 80 ? 80 : 0;
if (!level || level <= (st.level || 0)) return [];
st.level = level;
const zl = (x) => (x * usd).toFixed(2).replace('.', ',') + ' zł';
const title = level >= 100 ? 'Luna: limit klucza wyczerpany' : `Luna: wykorzystano ${Math.floor(pct)}% limitu`;
const body = `Zużyto ${zl(used)} z ${zl(limit)} (${used.toFixed(2)} z ${limit.toFixed(2)} USD). `
  + (level >= 100 ? 'Luna nie odpowiada, dopóki nie podniesiesz limitu w panelu OpenRouter.' : 'Podnieś limit w panelu OpenRouter, zanim Luna przestanie odpowiadać.');
return [{ json: { title, body, level } }];"""})
send = node("Powiadom adminów", "n8n-nodes-base.postgres", 2.6, [880, 0], {"operation": "executeQuery", "query":
  "INSERT INTO notifications (item_id, user_id, due_at, channels, title, body)\nSELECT NULL, id, now(), '{push,email}', $1, $2 FROM users WHERE is_admin\nRETURNING user_id",
  "options": {"queryReplacement": "={{ [ $json.title, $json.body ] }}"}}, credentials=PG)
link(cron, key); link(key, nbp); link(nbp, chk); link(chk, send)
json.dump({"name": "Oboe: Limit klucza", "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1", "timezone": "Europe/Warsaw"}},
          open("oboe-limit.json", "w"), ensure_ascii=False, indent=1)
print(len(nodes), "węzłów")
