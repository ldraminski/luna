"""Ustawienia instancji dla builderów workflowów: credentiale n8n i adresy.

Prawdziwe wartości leżą w `config.local.json` (poza repo). Bez niego buildery biorą `config.example.json`
— wygenerowane workflowy są wtedy poprawne, ale credentiale trzeba podpiąć w n8n po imporcie.
"""
import json, os

_dir = os.path.dirname(os.path.abspath(__file__))
_local = os.path.join(_dir, "config.local.json")
# LUNA_CONFIG=example wymusza atrapy — tak powstają workflowy publikowane w repo (build_all.py --public).
_use_local = os.path.exists(_local) and os.environ.get("LUNA_CONFIG") != "example"
C = json.load(open(_local if _use_local else os.path.join(_dir, "config.example.json")))

def _cred(key):
    c = C["credentials"].get(key)
    return {c["type"]: {"id": c["id"], "name": c["name"]}} if c and c.get("id") else None

PG = _cred("postgres")          # Postgres Luny (oboe-db)
OR = _cred("openrouter")        # OpenRouter — klucz Luny z limitem
SMTP = _cred("smtp")            # wysyłka maili
ADMIN = _cred("admin")          # Header Auth: X-Admin-Token dla tras /admin/*
VAPID = _cred("vapid")          # węzeł Crypto: klucz prywatny VAPID (podpis Web Push)
R2 = _cred("r2")                # S3/R2 na kopie zapasowe (opcjonalnie)

APP_URL = C["app_url"]          # adres aplikacji w mailach i linkach
SENDER = C["sender"]            # nadawca maili, np. "Luna <luna@example.com>"
VAPID_PUB = C["vapid_public"]   # klucz publiczny VAPID (ten sam w public/api.js)
VAPID_SUB = C["vapid_subject"]  # „sub” w JWT VAPID (adres kontaktowy albo URL)
REFERER = C["openrouter_referer"]
WHISPER_URL = C["whisper_url"]
BACKUP_BUCKET = C.get("backup_bucket", "luna-kopie")

def workflow_id(name):
    """Id pod-workflowu w n8n (np. „widgets”), zapisane po utworzeniu w `.<name>-wf-id` — poza repo, bo zależy od instancji."""
    f = os.path.join(_dir, f".{name}-wf-id")
    if _use_local and os.path.exists(f):
        return open(f).read().strip()
    return f"REPLACE_WITH_{name.upper()}_WORKFLOW_ID"
