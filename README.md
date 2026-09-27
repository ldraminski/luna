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

Widgety są niezmienne: każda wersja to nowy plik `<slug>/v<N>.html`; aktywną wersję wskazuje Postgres.

## Kontenery (w `/opt/infra/docker-compose.yml`)

- `oboe` — nginx: statyczna PWA + proxy `/api/*` → `http://n8n:5678/webhook/oboe/*` + `/widgets/` z CSP sandbox. `127.0.0.1:3320`.
- `oboe-db` — Postgres 16, bez `ports:`, n8n łączy się po nazwie `oboe-db:5432`.

## Wdrożenie

```bash
rsync -av --delete --exclude .git ~/Work/oboe/ vps.draminski.dev:/opt/oboe/app/
ssh vps.draminski.dev "cd /opt/oboe/app && docker build -t oboe:latest . && cd /opt/infra && docker compose up -d oboe"
```
