# Oboe (覚え)

Przypomnienia i akcje z języka naturalnego, ekran złożony z widgetów (część generuje AI).
Założenia: `~/Work/agents/hikari/memory/project-app-powiadomienia.md`.
Design system: wariant A (pastel) — `~/Work/agents/hikari/sekkei/oboe/wariant-a.html`.

## Układ na VPS (`/opt/oboe`)

| Ścieżka | Co |
|---|---|
| `/opt/oboe/app` | kopia tego repo (rsync), z niej `docker build -t oboe:latest .` |
| `/opt/oboe/widgets` | **osobne repo git** z widgetami generowanymi przez AI — n8n zapisuje i commituje, nginx serwuje read-only pod `/widgets/` |
| `/opt/oboe/db.env` | hasło do `oboe-db` (0600, nie w git) |

Widgety są niezmienne: każda wersja to nowy plik `<slug>.v<N>.html` (płasko — węzeł zapisu n8n nie tworzy katalogów); aktywną wersję wskazuje Postgres.

## Kontenery (w `/opt/infra/docker-compose.yml`)

- `oboe` — nginx: statyczna PWA + proxy `/api/*` → `http://n8n:5678/webhook/oboe/*` + `/widgets/` z CSP sandbox. `127.0.0.1:3320`.
- `oboe-db` — Postgres 16, bez `ports:`, n8n łączy się po nazwie `oboe-db:5432`.

## Wdrożenie

```bash
rsync -av --delete --exclude .git ~/Work/oboe/ vps.draminski.dev:/opt/oboe/app/
ssh vps.draminski.dev "cd /opt/oboe/app && docker build -t oboe:latest . && cd /opt/infra && docker compose up -d oboe"
```

## Widgety od AI („Oboe: Generuj widget”, `n8n/build_widgets.py`)
Dobór z biblioteki (DeepSeek 4.1) → nowy kod (DeepSeek 4.1, kontrakt `n8n/prompt-widget.txt`) → skan (`n8n/skan.js`) →
guardian (`n8n/prompt-guardian.txt`) → plik + commit w `/opt/oboe/widgets` → `widgets`/`widget_versions`.
Front: `<iframe sandbox="allow-scripts">` + CSP sandbox z nginx; rozmowa `oboe:data` / `oboe:ready` / `oboe:resize` / `oboe:save`.
Ręczne ponowienie: `POST http://127.0.0.1:5678/webhook/oboe/admin/widget {"item_id": ...}` + X-Admin-Token (z serwera).

## Streszczanie stron („Oboe: Streść stronę”, `n8n/build_summary.py`)
Po dodaniu (created), „Sprawdź teraz” (manual, max co 2 min) i w terminie cyklicznym (scheduled — push tylko przy istotnej zmianie).
SSRF: DNS przez DoH (A+AAAA) → tylko publiczne IP, porty 80/443, przekierowania nie automatycznie — jedno ręczne z ponownym DNS.
Tekst bez zmian (odcisk FNV) = bez pytania modelu. Treść strony dla modelu to dane, nie polecenia.

## Czat „Popraw / Zrób widget”
`POST /api/items/widget-chat {id, message}` — rozmowa z projektantem (DeepSeek 4.1, `n8n/prompt-czat-widgetu.txt`) w `widget_chats`;
gdy AI jest pewne, zwraca `proposal` (plan + nowy schemat + stan przeniesiony z obecnego). `POST /api/items/widget-regenerate {id}`
dopiero po `proposal` → „Oboe: Generuj widget” mode=revise: stary kod z pliku + plan → programista → skan → guardian.
Widget tylko tej rzeczy → nowa wersja tego samego sluga (v2…); współdzielony → kopia z nowym slugiem. Odrzucona poprawka
zostawia stary widget (`revision_error`). Stan użytkownika zawsze przechodzi (bezpiecznik w „Projekt z czatu”).
