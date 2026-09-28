"""Teksty maili Luny — JEDNO źródło dla „Oboe: Wydaj token” i „Oboe: Dostęp” (żeby się nie rozjechały).
Funkcje zwracają wyrażenie n8n (={{ ... }}); `r` to wyrażenie JS z polami name/token, np. "$json.result"."""
from config import APP_URL, SENDER as NADAWCA

def _hej(r):
    return "'Cześć' + (" + r + ".name ? ' ' + " + r + ".name : '') + '!\\n\\n"

_JAK = ("Jak zacząć — 3 kroki:\\n"
  "1. Zainstaluj Lunę: otwórz NA TELEFONIE " + APP_URL + "/instalacja — pokażę Ci krok po kroku, co stuknąć (na iPhonie otwórz w Safari).\\n"
  "2. Otwórz Lunę z ekranu początkowego, tak jak każdą inną aplikację.\\n"
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


# ---------- wersje HTML (28.09): duży przycisk do przewodnika instalacji + klucz w ramce ----------
# Tekstowe wersje wyżej zostają jako „text” (programy bez HTML); nadawca wysyła oba formaty.
_ESC = "(s => String(s || '').replace(/[&<>\"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;'})[c]))"
_BOX = "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;max-width:520px;margin:0 auto;color:#0f2a33;font-size:15px;line-height:1.55"
_BTN = "display:inline-block;background:#094457;color:#ffffff;text-decoration:none;padding:15px 30px;border-radius:999px;font-weight:600;font-size:16px"
_KEY = "font-family:ui-monospace,Menlo,Consolas,monospace;font-size:15px;background:#f3f7f8;border:1px solid #d3e0e3;border-radius:12px;padding:14px 16px;word-break:break-all"
_SMALL = "font-size:13px;color:#48636b"

O_LUNIE_HTML = ("<p>Jestem Luna — Twoja prywatna asystentka w telefonie. Piszesz mi zwykłym zdaniem (albo mówisz lub wysyłasz zdjęcie), "
  "co masz na głowie, a ja to zapisuję i pilnuję za Ciebie:</p><ul style=\"padding-left:20px;margin:8px 0\">"
  "<li>przypominam o terminach — dzień wcześniej i tuż przed wydarzeniem,</li>"
  "<li>pilnuję rzeczy, które się powtarzają (opłaty, przeglądy, cotygodniowe obowiązki),</li>"
  "<li>robię listy do odhaczania i notatki — także ze zdjęć,</li>"
  "<li>co rano wysyłam krótki plan dnia.</li></ul>")

def _html_hej(r):
    return "'<div style=\"" + _BOX + "\"><p>Cześć' + (" + r + ".name ? ' ' + " + _ESC + "(" + r + ".name) : '') + '!</p>"

def _html_kroki(r):
    return ("<h3 style=\"font-size:17px;margin:24px 0 8px\">Jak zacząć — 3 kroki</h3>"
      "<p><b>1. Zainstaluj Lunę.</b> Otwórz ten przycisk <b>na telefonie</b> — pokażę Ci krok po kroku, co stuknąć "
      "(na iPhonie otwórz go w Safari):</p>"
      "<p style=\"text-align:center;margin:18px 0\"><a href=\"" + APP_URL + "/instalacja\" style=\"" + _BTN + "\">Zainstaluj Lunę</a></p>"
      "<p><b>2. Otwórz Lunę z ekranu początkowego</b> — tak jak każdą inną aplikację.</p>"
      "<p><b>3. Stuknij „Mam już klucz” i wklej ten klucz</b> (przytrzymaj go palcem, żeby skopiować):</p>"
      "<div style=\"" + _KEY + "\">' + " + _ESC + "(" + r + ".token) + '</div>")

def html_powitalny(r, wstep_html=O_LUNIE_HTML):
    return ("={{ " + _html_hej(r) + wstep_html + _html_kroki(r) +
      "<p style=\"" + _SMALL + ";margin-top:18px\">Klucz działa bez końca. Nie przesyłaj go nikomu — kto go ma, widzi Twoje sprawy. "
      "Zgubisz go? Wejdź na <a href=\"" + APP_URL + "\">" + APP_URL.replace("https://", "") + "</a>, wpisz swój e-mail, a wyślę Ci nowy.</p>"
      "<p style=\"" + _SMALL + "\">Korzystając z Luny, akceptujesz <a href=\"" + APP_URL + "/regulamin\">regulamin i zasady prywatności</a>.</p>"
      "<p>Do usłyszenia!<br>— Luna</p></div>' }}")

def html_nowy(r):
    return ("={{ " + _html_hej(r) + "<p>Oto Twój nowy klucz do Luny:</p><div style=\"" + _KEY + "\">' + " + _ESC + "(" + r + ".token) + '</div>"
      "<p>Wklej go w aplikacji uruchomionej z ekranu początkowego (stuknij „Mam już klucz”). Klucze na Twoich innych urządzeniach dalej działają.</p>"
      "<p>Nie masz jeszcze Luny na tym telefonie? <a href=\"" + APP_URL + "/instalacja\">Zobacz, jak ją zainstalować</a>.</p>"
      "<p style=\"" + _SMALL + "\">Jeśli nie prosisz o nowy klucz, po prostu zignoruj tę wiadomość — nikt nie dostał dostępu.</p>"
      "<p>— Luna</p></div>' }}")
