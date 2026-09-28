# Luna — notatki deweloperskie (PL)

> Dziennik decyzji i szczegółów wdrożenia prowadzony w trakcie budowy — po polsku, z datami.
> Opis projektu dla czytelnika z zewnątrz: [README](../README.md).

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
zapisujemy tylko **miniaturę** (≤800 px JPEG ~30–100 KB, robi ją przeglądarka) w tabeli `item_photos` (migracja 010) —
pobierana osobno `GET /api/items/photo?id=` wyłącznie z kluczem właściciela; lista rzeczy ma tylko `has_photo`. Usunięcie rzeczy kasuje zdjęcie. Nieczytelne zdjęcie bez tekstu → 422 „Nie udało mi się obejrzeć tego zdjęcia” (Luna nic nie wymyśla).

## Dyktowanie (28.09.2026, Łukasz)

Mikrofon w głównym polu otwiera okno **„Słucham”** (instrukcja z przykładem, licznik, Anuluj / Gotowe; limit 2 min) →
**„Odsłuchuję…”** → **„Zapisuję…”** → **podsumowanie**: „Usłyszałam: …” + „Co z tym zrobiłam” (`spec.understood`) z **Cofnij** (miękkie usunięcie) / Super.
Zapis bez pytania o zgodę — transkrypcja jest dokładna, a „Cofnij” ratuje pomyłki. Nieudany zapis → „Wstaw do pola” (tam działa kolejka offline).
- `POST /api/transcribe {audio: dataURL}` → workflow „Oboe: Dyktowanie” (`n8n/build_transcribe.py`, id w `n8n/.transcribe-wf-id`) →
  kontener **`whisper`** (speaches, `deepdml/faster-whisper-large-v3-turbo-ct2` int8, CPU, `cpus: 4`, `mem_limit: 4g`) w `/opt/infra`, bez portu publicznego.
  nginx: 4 MB tylko dla tej trasy. **Nagranie nie jest nigdzie zapisywane.**
- **`vad_filter=true` obowiązkowo** — bez niego Whisper na ciszy/szumie zmyśla „Dziękuję za uwagę.” / „Dzięki za oglądanie!”. Cisza → 422 „Nic nie usłyszałam”.
- Czas: ~6–8 s na transkrypcję (Whisper zawsze liczy okno 30 s, więc krótka notatka nie jest dużo szybsza) + ~2 s rozumienie. Test E2E: 9,4 s od „Gotowe” do zapisu.
- Format: Android/Chrome `audio/webm;codecs=opus`, iPhone `audio/mp4`. Aplikacja zeszła w tło w trakcie nagrywania → nagranie przepada, nic nie idzie.
- Test bez telefonu: Chromium z `--use-fake-device-for-media-stream --use-file-for-fake-audio-capture=plik.wav` (WAV z `say -v Zosia` + `afconvert`),
  na tymczasowym koncie testowym (nie na koncie Łukasza — rozumienie ustawia prawdziwe przypomnienia).

## Biurko — wersja na komputer (28.09.2026)

`luna.draminski.dev/biurko` — osobna strona (`public/biurko.html|js|css`) do DŁUŻSZYCH materiałów; wspólne z telefonem: klucz w przeglądarce, API, dane.
Decyzja: osobny interfejs, NIE osobna aplikacja (inna domena = osobne logowanie i rozjazd funkcji) i NIE responsywny `app.js` (ryzyko dla telefonu).
1. Wklej materiał (do 20 000 znaków; szkic w `localStorage` `luna-biurko-szkic`) → `POST /api/items/split {text}` →
   „Oboe: Biurko” (`n8n/build_desk.py`, id w `n8n/.desk-wf-id`, prompt `n8n/prompt-rozbij.txt`): DeepSeek 4.1 Flash dzieli materiał na
   samodzielne zdania z konkretnymi datami (kalendarz 120 dni), zakupy w jedną listę, pomija podpisy. **Nic nie zapisuje.** ~5–10 s.
2. Przegląd: popraw / usuń / dopisz. 3. Każde zdanie zwykłym `POST /api/items` (po 2 naraz, ~2–4 s na rzecz) → „co z tym zrobiłam” + Cofnij (`items/delete`).
- Boczna kolumna: najbliższe 30 dni (`spec.event_at || next_at`), nowe z tej sesji oznaczone „nowe”.
- nginx: `location = /biurko` → `biurko.html`; `/api/items/split` z limitem 256 KB. Dockerfile: pliki biurka w skrócie wersji i podmianie `__V__`.
- W widoku z telefonu na ekranie ≥1000 px (po zalogowaniu) link „Biurko — wklej dłuższy materiał →”.
- Test: Playwright na koncie testowym (mail ze żłobka + plan tygodnia → 8 rzeczy, 0 błędów).

## Raport dnia / tygodnia i przypomnienie o zaległych (28.09.2026, Łukasz)

Workflow „Oboe: Raport” (`n8n/build_report.py`, id w `n8n/.report-wf-id`), migracja `db/011-raporty.sql`.
- Co 5 min: komu wypadła godzina (`users.report_time`, domyślnie **9:00**, okno 4 h; `report_enabled`) i nie ma raportu na dziś (`reports`, jeden na dzień).
- **Pon = raport tygodnia** (7 dni), inne dni = **dziś + jutro**. Plan liczy KOD (`n8n/raport-plan.js`, cykliczne jak w aplikacji);
  DeepSeek (`n8n/prompt-raport.txt`) pisze tylko wstęp, rady „przygotuj się wcześniej”, pytanie o zaległe i treść pusha.
- Powiadomienia (przez Harmonogram, `item_id NULL`): „Twój plan na dziś / Twój tydzień z Luną” + gdy są zaległe osobne
  „Masz N przeterminowane rzeczy — wykonaj je albo oznacz jako zakończone — inaczej będę ci ciągle przypominać.”
- Aplikacja: raport otwiera się sam raz dziennie (`seen_at`), potem ikona raportu w nagłówku; na dole wybór godziny / wyłączenie (`POST /api/settings`).
  **Zaległe:** karta od dołu przy otwarciu / powrocie do aplikacji (najwyżej co 3 h, localStorage) z „Zrobione” / „Nieaktualne — zamknij”.
- Ręcznie (test): `POST /webhook/oboe/admin/report {email, weekly}` z X-Admin-Token, tylko z serwera.

## Kopia zapasowa i pilnowanie limitu (28.09.2026)

**Kopia — „Oboe: Kopia zapasowa”** (`n8n/build_backup.py`, id w `n8n/.backup-wf-id`): codziennie 3:30 eksport WSZYSTKICH tabel oboe-db
+ pliki widgetów (`/data/oboe-widgets/*.html`) → JSON → gzip → **prywatny** bucket R2 `luna-kopie`, klucz `oboe/RRRR-MM-DD.json.gz` (~180 KB).
Nic nie zostaje na serwerze (n8n nie ma trwałego katalogu na pliki). Błąd wysyłki → push + mail dla adminów.
**Stan 28.09: eksport działa, wysyłka CZEKA** na bucket + credential od Łukasza (credential analyzera ma dostęp tylko do publicznego
`analyzer-images` — tam kopii NIE wrzucamy). Po założeniu: `n8n/.backup-r2.json` = `{"id": "...", "name": "..."}` credentialu,
`python3 build_backup.py`, PUT, aktywacja, test `POST 127.0.0.1:5678/webhook/oboe/admin/backup` (X-Admin-Token). Retencja: reguła cyklu życia w R2 (30 dni).

Odtworzenie (na pustej bazie po `db/schema.sql` + migracjach, w tej kolejności tabel):
```bash
gunzip -c 2026-09-28.json.gz > kopia.json
for t in users widgets widget_versions items sessions notifications push_subscriptions widget_chats access_requests access_log item_photos reports; do
  python3 -c "import json,sys; print(json.dumps(json.load(open('kopia.json'))['tables']['$t']))" > /tmp/t.json
  docker exec -i oboe-db psql -U oboe -d oboe -v j="$(cat /tmp/t.json)" -c "INSERT INTO $t SELECT * FROM json_populate_recordset(NULL::$t, :'j'::json)"
done
# pliki widgetów: klucz widget_files w kopii → /opt/oboe/widgets/<nazwa> (+ git commit)
```

**Limit — „Oboe: Limit klucza”** (`n8n/build_limit.py`, id w `n8n/.limit-wf-id`): co godzinę `GET /api/v1/key` kluczem Luny;
progi 80/95/100% → push + mail dla adminów, każdy raz (static data), <50% zeruje. Kwoty w zł wg kursu NBP.
W aplikacji przy wyczerpanym limicie (402): „Mam chwilową przerwę — skończył się limit… Łukasz już o tym wie.”

## Offline i niedziałający serwer (28.09.2026)

- **Czcionka Lexend hostowana u nas** (`public/fonts/`, SIL OFL, jeden plik zmienny na podzbiór latin/latin-ext). Wcześniej arkusz z Google
  blokował rysowanie strony → biały ekran bez sieci. NIE wracać do fonts.googleapis.com.
- **Service worker:** po 4 s bez odpowiedzi serwera bierze wersję z pamięci (wiszące połączenie ≠ brak sieci); czcionki w `SHELL_FILES`.
- **API:** limit czasu (15 s; dodawanie 90 s, czat 120 s); brak sieci / 5xx bez JSON-a → `ApiError(0)` = tryb offline.
- **Aplikacja:** ostatni stan w `localStorage` (`luna-stan`) — bez połączenia pokazuje go z paskiem „Brak połączenia z Luną — stan z 8:17”,
  NIE wylogowuje. Wpisy bez połączenia → kolejka `luna-kolejka` („Czeka na wysłanie”), wysyłają się same po powrocie (`online`, co 30 s, powrót do aplikacji).
  Zdjęć offline nie kolejkujemy (za duże na localStorage).
- **Przypomnienia przy padzie serwera:** harmonogram jest na tym samym serwerze — w czasie awarii nic nie wychodzi; po powrocie wysyła
  wszystkie zaległe (`due_at <= now()`, jeszcze niewysłane) za jednym razem.

## Przypomnienia i alarm w chwili terminu (28.09.2026, Łukasz)

- **Czas przypomnień** (`prompt-rozumienie.txt`): trzeba dojechać (umowa, żłobek, lekarz, urząd…) → **1:30 h i 5 min przed**; bez dojazdu (telefon, lek, TV)
  → 10 min przed; wydarzenie jutro lub później → też 20:00 dzień wcześniej. Nie wcześniej niż 6:00, nigdy „na dokładną godzinę” (wtedy alarm).
- **Alarm:** „Oboe: Harmonogram” chodzi **co 20 s**; krok „Alarmy” — jednorazowa rzecz z minionym terminem (start tylko dla ostatniej godziny)
  dostaje powiadomienie `kind='alarm'` co 20 s, dopóki `data.alarm.state` nie jest `off`, przełożona (`snoozed`, +5 min) ani odhaczona.
  Bezpiecznik 60 min (Apple może zablokować zasypujące pushe) → `off` + ostatni push. Alarm NIGDY mailem (fallback wyłączony dla `kind='alarm'`).
- Push alarmu: jeden na rzecz (`tag` + `renotify`), na Androidzie przyciski „Przełóż o 5 min” / „Wyłącz” (`POST /api/items/alarm` z SW).
  W aplikacji czerwona karta (`#alarm`) ma pierwszeństwo przed kartą zaległych. Migracja `db/012-alarm.sql` (`notifications.kind`).
- Udanych przebiegów Harmonogramu n8n nie zapisuje (`saveDataSuccessExecution: none`) — 4320/dobę.

## Wdrożenie

**Pamięć podręczna (27.09):** Cloudflare dokleja `max-age=14400` do CSS/JS mimo `no-cache` z nginx — telefon brał nowy HTML ze starym CSS.
Dlatego adresy mają `?v=__V__` (index.html, import w app.js, lista w sw.js), a Dockerfile podmienia `__V__` na skrót treści plików.
**Nie usuwać `__V__`** i nie dodawać nowych plików JS/CSS bez tego znacznika. Service worker pobiera zasoby z `cache: 'no-cache'`.

Workflowy n8n: `cd n8n && python3 build_all.py` (z `config.local.json`, poza repo) → `oboe-*.json` → PUT przez API n8n.
Workflowy w repo (`n8n/workflows/`) odświeża `python3 build_all.py --public` (atrapy z `config.example.json`).

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
