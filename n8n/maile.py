"""Teksty maili Luny — JEDNO źródło dla „Oboe: Wydaj token” i „Oboe: Dostęp” (żeby się nie rozjechały).
Funkcje zwracają wyrażenie n8n (={{ ... }}); `r` to wyrażenie JS z polami name/token, np. "$json.result"."""
from config import APP_URL, SENDER as NADAWCA

def _hej(r):
    return "'Cześć' + (" + r + ".name ? ' ' + " + r + ".name : '') + '!\\n\\n"

_JAK = ("Jak zacząć — 3 kroki:\\n\\n"
  "1. Zainstaluj Lunę. Otwórz ten link NA TELEFONIE (na iPhonie w Safari) — pokażę Ci krok po kroku, co stuknąć:\\n"
  "   " + APP_URL + "/instalacja\\n\\n"
  "2. Otwórz Lunę z ekranu początkowego, tak jak każdą inną aplikację.\\n\\n"
  "3. Stuknij „Mam już klucz” i wklej klucz z tego maila. "
  "(Na iPhonie aplikacja z ekranu początkowego nie widzi tego, co wpiszesz w Safari — klucz wklejasz dopiero w niej.)\\n\\n")

O_LUNIE = ("Jestem Luna — Twoja prywatna asystentka w telefonie. Piszesz mi zwykłym zdaniem (albo wysyłasz zdjęcie), co masz na głowie, "
  "a ja to zapisuję i pilnuję za Ciebie:\\n"
  "• przypominam o terminach — dzień wcześniej i tuż przed wydarzeniem,\\n"
  "• pilnuję rzeczy, które się powtarzają (opłaty, przeglądy, cotygodniowe obowiązki),\\n"
  "• robię listy do odhaczania i notatki — także ze zdjęć,\\n"
  "• sprawdzam informacje w internecie i streszczam strony,\\n"
  "• co rano wysyłam krótki plan dnia, a w poniedziałki plan całego tygodnia.\\n\\n"
  "Luna działa w przeglądarce — dodajesz ją do ekranu początkowego jak zwykłą aplikację, niczego nie pobierasz ze sklepu. "
  "Twoje sprawy widzisz tylko Ty.")

def klucz_powitalny(r, wstep=O_LUNIE):
    return ("={{ " + _hej(r) + wstep + "\\n\\nOto Twój klucz:\\n\\n' + " + r + ".token + '\\n\\n" + _JAK +
      "Klucz działa bez końca. Nie przesyłaj go nikomu — kto go ma, widzi Twoje sprawy.\\n"
      "Zgubisz go? Wejdź na " + APP_URL + ", wpisz swój e-mail, a wyślę Ci nowy.\\n\\n"
      "Korzystając z Luny, akceptujesz regulamin i zasady prywatności: " + APP_URL + "/regulamin\\n\\nDo usłyszenia!\\n— Luna' }}")

def klucz_nowy(r):
    return ("={{ " + _hej(r) + "Oto Twój nowy klucz do Luny:\\n\\n' + " + r + ".token + '\\n\\n"
      "Wklej go w aplikacji uruchomionej z ekranu początkowego. Klucze na Twoich innych urządzeniach dalej działają.\\n\\n"
      "Jeśli nie prosisz o nowy klucz, po prostu zignoruj tę wiadomość — nikt nie dostał dostępu.\\n\\n— Luna' }}")

def odrzucenie(r):
    return ("={{ " + _hej(r) + "Przykro mi — Łukasz odrzucił Twoją prośbę o dostęp do Luny.\\n\\n"
      "Jeśli to pomyłka, napisz do niego bezpośrednio.\\n\\n— Luna' }}")

