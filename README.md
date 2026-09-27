# Luna — prywatna asystentka (wewnętrznie: `oboe`)

Zapisuje sprawy, terminy, listy i notatki z języka naturalnego i odzywa się, kiedy trzeba; ekran złożony z widgetów (część generuje AI).

## Nazwy: Luna na zewnątrz, `oboe` w środku (decyzja Łukasza 27.09.2026)

Produkt nazywał się roboczo Oboe (覚え). Od 27.09.2026 **dla użytkownika to wyłącznie „Luna”**, a `oboe` zostaje
**tylko jako identyfikator techniczny** — zmiana nazw w środku to ryzyko bez żadnego zysku.

| Widzi użytkownik → **Luna** | Techniczne → zostaje **oboe** (nie zmieniać) |
|---|---|
| tytuł, manifest PWA, ikona, teksty w aplikacji | repo `~/Work/oboe`, katalog `/opt/oboe`, obraz `oboe:latest` |
| głos modeli: `understood`, powiadomienia, czat widgetu | kontenery `oboe`, `oboe-db`, baza i użytkownik `oboe` |
| nadawca i treść maili („Luna <n8n@renlab.ovh>”) | workflow n8n „Oboe: …”, webhooki `/webhook/oboe/…`, credentiale „Oboe - …” |
| adres `luna.draminski.dev` (`oboe.draminski.dev` usunięty 27.09) | protokół widgetów `oboe:data/ready/resize/save` (zmiana zepsuje gotowe widgety) |
| | `localStorage` `oboe-token`, IndexedDB `oboe`, cache SW `oboe-shell-*` (zmiana wyloguje ludzi) |

Zasady: nowy tekst dla ludzi → „Luna”, w 1. osobie, forma żeńska, na „ty” („Zapisałam. Przypomnę ci…”).
Nowy identyfikator w kodzie → dalej `oboe`. W komentarzach wolno „Luna (wewn. oboe)”.
**Przed każdym wdrożeniem:** `tools/sprawdz-nazwy.sh` — wyłapuje „Oboe” w tekstach widocznych dla użytkownika.
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

## Dostęp: prośba → akceptacja Łukasza → klucz mailem (27.09.2026)

Workflow „Oboe: Dostęp” (`n8n/build_access.py`, id w `n8n/.access-wf-id`), migracja `db/008-prosby-o-dostep.sql`.
1. Ekran startowy: imię + e-mail → `POST /api/access/request`.
   - konto istnieje → nowy klucz od razu mailem (stare klucze zostają);
   - nowa osoba → `access_requests` (pending) + powiadomienie dla adminów (`users.is_admin`) — push **i** mail — wysyłane przez „Oboe: Harmonogram”
     (`notifications.item_id = NULL`; bez działającego pusha idzie mail);
   - odrzucona w ciągu 30 dni → komunikat, bez nowego powiadomienia.
2. Admin widzi na górze listy „Prośby o dostęp” → Zaakceptuj / Odrzuć (`POST /api/access/decide`).
   Akceptacja = konto + klucz mailem; odrzucenie = mail „Przykro mi — Łukasz odrzucił Twoją prośbę”.
- **Klucz nigdy nie wraca w odpowiedzi HTTP** — tylko mailem. Limit: 3 prośby/h na e-mail, 40/h łącznie (`access_log`).
- Teksty wszystkich maili: `n8n/maile.py` (wspólne dla „Dostęp” i „Wydaj token”).
- „Oboe: Wydaj token” (ręcznie z serwera) zostaje jako awaryjne.

## Luna sprawdza w sieci (27.09.2026)

**Klucz:** Luna ma własny klucz OpenRoutera z limitem ustawionym przez Łukasza (27.09: 2 USD) — credential n8n „OpenRouter - Luna” (ZGSl0yv59gDWZKJG), używany w „Oboe: API”, „Streść stronę”, „Generuj widget”. Po wyczerpaniu limitu OpenRouter odpowiada 402 → Luna pokazuje „Model nie odpowiedział”.

W „Oboe: API” → POST items: gdy model rozumienia ustawi `research.query` (pytanie albo termin zależny od informacji z internetu),
DeepSeek 4.1 Flash szuka przez **wtyczkę web OpenRoutera** (`plugins: [{id: 'web', max_results: 5}]`, prompt `n8n/prompt-sieci.txt`),
a potem rozumie zdanie **drugi raz** ze znalezionymi faktami → termin i przypomnienia z wyniku („o której X na TVP 1, przypomnij 10 min przed”).
Wynik: `items.data.research = {query, answer, sources[{url,title,host}], checked_at}`; karta „Sprawdziłam w sieci” ze źródłami.
- Samo pytanie → notatka z odpowiedzią, bez przypomnienia. Brak pewnej informacji → Luna mówi to wprost i nie ustawia terminu.
- Koszt ok. 3 gr za sprawdzenie (0,0076 USD w teście), czas 6–9 s; zwykłe wpisy bez zmian (~2 s).
- Link + „zrób notatkę / co ważne” → jednorazowe streszczenie („Oboe: Streść stronę”), bez pilnowania.
- Wyniki wyszukiwania to dane, nie polecenia (prompt) — model niczego nie wykonuje, tekst na karcie escapowany.

## Widget = kafelek; „Popraw” = rozmowa z Luną (28.09.2026, decyzja Łukasza)

- **Każdy kafelek to widget.** Wbudowane części: termin, powtarzanie, przypomnienia, **listy z nazwami** (`data.lists = [{name, items:[{text,done}], reset}]`,
  migracja `db/009-wiele-list.sql`), szczegóły, wygląd, odpowiedź z sieci, strona. Widget na zamówienie (kod AI) — tylko gdy tych części nie wystarcza.
- **Czat „Popraw”** (`n8n/prompt-popraw.txt`, trasy `items/widget-chat` i `items/widget-regenerate`): Luna rozmawia o jednej rzeczy,
  pokazuje plan („Tak to zrobię: • …”), a po „Zrób to” `n8n/zastosuj.js` wprowadza wszystkie zmiany naraz (tytuł, termin i przypomnienia,
  listy: dopisz/usuń/zmień nazwę/nowa lista/usuń listę, szczegóły, wygląd, usunięcie widgetu). Widget na zamówienie przebudowuje się w tle.
- **Nie dublujemy:** Luna rozszerza istniejącą listę; nową dodaje na wyraźną prośbę i mówi to wprost. Blokada w kodzie: widget AI wyglądający na listę jest odrzucany.
  Widgety-listy `lista-zakupow` i `obowiazki-do-zrobienia` wycofane z biblioteki (`active_version = NULL`).
- **Zdjęcie w rozmowie:** przeglądarka zmniejsza je do 1600 px JPEG → `deepseek/deepseek-v4.1-flash` (obsługuje obrazy) odczytuje treść → do rozmowy trafia TYLKO tekst
  (`[ZDJĘCIE] …`), samo zdjęcie nie jest zapisywane. nginx: limit 4 MB tylko dla `/api/items/widget-chat` (reszta API 64 KB).

## Zdjęcie przy dodawaniu (28.09.2026, Łukasz)

Przycisk aparatu w głównym polu (miniatura z ✕ nad polem). `POST /api/items` przyjmuje `image` (JPEG ≤1600 px, nginx 4 MB tylko dla tej trasy).
DeepSeek 4.1 Flash robi analizę „jak analyzer.draminski.dev” (krótki tytuł, opis 2–3 zdania) + odczytany tekst — BEZ `response_format`
(z nim DeepSeek potrafił oddać samo `{"type":"json_object"}`), z drugą próbą. Potem ZWYKŁE rozumienie: termin na zdjęciu → przypomnienie,
lista → lista, miejsce/rzecz → zwykła notatka z polami (adres, godziny, cena). Z tekstem użytkownika — tekst decyduje. `data.photo` = opis + tekst;
samego zdjęcia nie zapisujemy. Nieczytelne zdjęcie bez tekstu → 422 „Nie udało mi się obejrzeć tego zdjęcia” (Luna nic nie wymyśla).

## Wdrożenie

**Pamięć podręczna (27.09):** Cloudflare dokleja `max-age=14400` do CSS/JS mimo `no-cache` z nginx — telefon brał nowy HTML ze starym CSS.
Dlatego adresy mają `?v=__V__` (index.html, import w app.js, lista w sw.js), a Dockerfile podmienia `__V__` na skrót treści plików.
**Nie usuwać `__V__`** i nie dodawać nowych plików JS/CSS bez tego znacznika. Service worker pobiera zasoby z `cache: 'no-cache'`.

```bash
tools/sprawdz-nazwy.sh || exit 1
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
