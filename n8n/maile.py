"""Teksty maili Luny — JEDNO źródło dla „Oboe: Wydaj token” i „Oboe: Dostęp” (żeby się nie rozjechały).
Funkcje zwracają wyrażenie n8n (={{ ... }}); `r` to wyrażenie JS z polami name/token, np. "$json.result"."""
APP_URL = "https://luna.draminski.dev"
NADAWCA = "Luna <n8n@renlab.ovh>"

def _hej(r):
    return "'Cześć' + (" + r + ".name ? ' ' + " + r + ".name : '') + '!\\n\\n"

_JAK = ("Jak zacząć:\\n"
  "1. Otwórz na telefonie: " + APP_URL + "\\n"
  "2. iPhone: Udostępnij → „Do ekranu początkowego”. Android: menu → „Zainstaluj aplikację”.\\n"
  "3. Uruchom Lunę Z EKRANU POCZĄTKOWEGO i dopiero tam wklej klucz. "
  "(Na iPhonie aplikacja z ekranu początkowego nie widzi tego, co wpiszesz w Safari.)\\n\\n")

def klucz_powitalny(r, wstep="Jestem Luna — Twoja prywatna asystentka. Zapisuję sprawy, terminy, listy i notatki, a potem pilnuję, żeby nic Ci nie umknęło."):
    return ("={{ " + _hej(r) + wstep + "\\n\\nOto Twój klucz:\\n\\n' + " + r + ".token + '\\n\\n" + _JAK +
      "Klucz działa bez końca. Nie przesyłaj go nikomu — kto go ma, widzi Twoje sprawy.\\n"
      "Zgubisz go? Wejdź na " + APP_URL + ", wpisz swój e-mail, a wyślę Ci nowy.\\n\\nDo usłyszenia!\\n— Luna' }}")

def klucz_nowy(r):
    return ("={{ " + _hej(r) + "Oto Twój nowy klucz do Luny:\\n\\n' + " + r + ".token + '\\n\\n"
      "Wklej go w aplikacji uruchomionej z ekranu początkowego. Klucze na Twoich innych urządzeniach dalej działają.\\n\\n"
      "Jeśli nie prosisz o nowy klucz, po prostu zignoruj tę wiadomość — nikt nie dostał dostępu.\\n\\n— Luna' }}")

def odrzucenie(r):
    return ("={{ " + _hej(r) + "Przykro mi — Łukasz odrzucił Twoją prośbę o dostęp do Luny.\\n\\n"
      "Jeśli to pomyłka, napisz do niego bezpośrednio.\\n\\n— Luna' }}")
