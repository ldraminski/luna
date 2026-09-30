"""Komunikaty wspólne dla wielu workflowów Luny — JEDNO źródło (jak `maile.py`), żeby teksty się nie rozjechały.

402 z OpenRoutera = wyczerpany limit klucza Luny (alarm dostaje Łukasz z „Oboe: Limit klucza”). Ten sam tekst w głównym polu,
przy samym zdjęciu, w czacie „Popraw”, na Biurku i w notatkach głosowych; aplikacja dostaje wtedy HTTP 402 i np. zostawia
wpis z kolejki offline w telefonie (`public/app.js` → `flushOutbox()`).
"""
import json

KEY_LIMIT = "Mam chwilową przerwę — skończył się limit, z którego korzystam. Łukasz już o tym wie."
KEY_LIMIT_JS = json.dumps(KEY_LIMIT, ensure_ascii=False)          # literał JS do wklejenia w Code node / wyrażenie n8n

# Test JS na wynik węzła HTTP (onError: continueRegularOutput): brak odpowiedzi modelu + 402 / „insufficient credits”.
# Bez słowa „limit” — 429 od dostawcy (rate limit) to nie wyczerpany klucz.
def is_key_limit_js(j="$json"):
    return f"(!({j}).choices && /\\b402\\b|insufficient credits|more credits/i.test(JSON.stringify(({j}).error || {j})))"

def fill(js):
    """Podmienia znaczniki w plikach .js ładowanych do Code node: __KEY_LIMIT__ (tekst) i __IS_KEY_LIMIT__ (test na $json)."""
    return js.replace("__KEY_LIMIT__", KEY_LIMIT_JS).replace("__IS_KEY_LIMIT__", is_key_limit_js())
