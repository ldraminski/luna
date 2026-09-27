#!/bin/sh
# Pilnuje podziału nazw: użytkownik widzi wyłącznie „Luna”, „oboe” zostaje tylko jako identyfikator techniczny.
# Uruchamiaj przed każdym wdrożeniem (README → Wdrożenie). Kod wyjścia 1 = w tekstach dla ludzi wyciekło „Oboe”.
cd "$(dirname "$0")/.." || exit 2
bad=$(
  # front: wszystko poza komentarzami
  grep -n "Oboe" public/index.html public/manifest.webmanifest public/*.js public/*.css 2>/dev/null \
    | grep -v -E '^[^:]+:[0-9]+:[[:space:]]*(//|/\*|\*|<!--)'
  # prompty: model mówi jako Luna i o Lunie
  grep -n "Oboe" n8n/prompt-*.txt
  # maile: nadawca, temat, treść, link
  grep -n "Oboe" n8n/build_admin.py n8n/build_scheduler.py | grep -E 'fromEmail|subject|"text"|TEXT|APP_URL|— Oboe'
)
if [ -n "$bad" ]; then
  echo "Nazwa „Oboe” w tekstach widocznych dla użytkownika — ma być „Luna”:"; echo "$bad"; exit 1
fi
echo "OK: użytkownik widzi tylko „Luna”."
