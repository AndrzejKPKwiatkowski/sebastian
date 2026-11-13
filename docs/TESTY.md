# Weryfikacja paczki 1.0

Data: 2026-10-01. Środowisko: Linux, Python 3.12. Nie wykonano połączeń do prywatnych skrzynek użytkownika ani do jego Maca.

Wynik: 8 testów automatycznych zaliczonych.

- Pilotaż wybiera 100 unikalnych UID, w tym 70 najnowszych.
- Symulowany IMAP potwierdza readonly=True i BODY.PEEK, pomijanie pobranych rekordów oraz obsługę kolejnych ograniczonych partii nowych wiadomości i historii.
- Parsowanie HTML usuwa skrypty z tekstu, nie pobiera zewnętrznych zasobów i oznacza skrócenie treści.
- Walidacja odrzuca niepoprawne wyniki AI i usuwa termin bez pasującego cytatu. Nie dowodzi to semantycznej trafności daty.
- Błąd AI zapisuje się w bazie; zwykła analiza go pomija, jawne --retry ponawia i zapisuje poprawny wynik. Wywołanie API było symulowane.
- Panel wymaga klucza, sprawdza host i token CSRF; decyzja zapisuje się w SQLite.
- Powtórny identyczny import tekstu nie dubluje fragmentów.
- Narzędzie Open WebUI blokuje nieuprawniony profil i nie zwraca firmowego ID przy prywatnym zakresie.

Dodatkowo: kompilacja składni Python, kontrola składni skryptów Bash, uruchomienie lokalnego serwera panelu, przegląd renderów wszystkich 30 stron PDF.

## Czego nie sprawdzono w tym środowisku

Prawdziwych serwerów IMAP, uprawnień i haseł, Pęku kluczy macOS, launchd, ruchu do rzeczywistej Ollamy, jakości odpowiedzi wybranego modelu oraz instalacji narzędzia we własnym Open WebUI/Docker. Ilustracje w PDF są schematami, nie zrzutami działającej instalacji użytkownika.

## Powtórzenie testów (opcjonalne)

Po aktywacji .venv:

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_sebastian.py -v
```

Testy używają tymczasowej bazy i nie logują się do poczty. Nie zastępują listy odbiorczej na Macu z podręcznika.


# Weryfikacja 2.0 — moduł nauki

Data: 2026-10-15. Środowisko: Linux, Python 3.13 (składnia sprawdzona także w 3.11). Bez połączeń z prawdziwymi skrzynkami, Dyskiem Google ani Ollamą.

Wynik: 17 testów automatycznych zaliczonych (8 dotychczasowych + 9 nowych w `test_learner.py`).

- Wątki: odpowiedź łączy się z mailem źródłowym (References), cytowana korespondencja jest wycinana, Twoje wysłane maile są oznaczone, decyzja i komentarz z panelu trafiają do tekstu wątku.
- Filtry: newsletter (kategoria), mail oznaczony w panelu jako Pomiń oraz nadawca no-reply nie trafiają do nauki; notatka z `import-text` trafia.
- Nowa odpowiedź w przeczytanym wątku przywraca go do kolejki; ten sam mail z archiwum i z Sebastiana (to samo Message-ID) nie dubluje się.
- Archiwum IMAP: tylko `select(readonly=True)` i `BODY.PEEK`, wyłącznie polecenia search/fetch, częściowe pobieranie treści, pomijanie Kosza, rozpoznanie folderu Wysłane, w Gmailu wyłącznie „Wszystkie”. Archiwum nie pojawia się w kolejce decyzji panelu.
- Fakty z mailem → Bieżące sprawy i Profil; kategoria spraw bieżących nie trafia do trwałego profilu.
- Import dawnego Drive Learnera (stan, fakty, teksty, ustawienia z config.py) i ochrona przed przypadkowym nadpisaniem.
- Ustawienia (`learn-set`): tak/nie, liczby, listy; nieznany klucz odrzucony.
- Zakładka Nauka wymaga zalogowania do panelu i pokazuje wątki.
- Dodatkowo: pełna pętla pracy z symulowanym modelem (kolejka → fakty → Bieżące sprawy → Profil → zatrzymanie).

Nie sprawdzono w tym środowisku: prawdziwych serwerów IMAP (Gmail, Murena, Partners), Pęku kluczy z poziomu launchd dla nowego zadania, rzeczywistej Ollamy i jakości faktów na Twoich mailach.

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_sebastian.py test_learner.py -v
```


# Weryfikacja 2.1 — załączniki

Data: 2026-10-15. Wynik: 22 testy zaliczone (8 Sebastiana + 9 nauki + 5 nowych dla załączników).

- Wątek z mailem zawierającym PDF i DOCX: tekst obu plików trafia do wątku, logo ze stopki (image001.png) i ZIP są pomijane, pliki tymczasowe są usuwane.
- Ponowne czytanie wątku korzysta z pamięci, bez łączenia z serwerem; ten sam plik w odpowiedzi nie jest powtarzany.
- Do serwera trafiają wyłącznie polecenia FETCH z RFC822.SIZE, BODY.PEEK[] i BODY.PEEK[HEADER.FIELDS (CONTENT-TYPE)], folder otwierany tylko do odczytu.
- Wiadomość przeniesiona na serwerze (inne UIDVALIDITY) jest pomijana bez błędu; wyłączone ustawienie nie łączy się z serwerem.
- Wątki bez załączników zachowują podpis z 2.0 (nie są czytane ponownie); wątek z załącznikiem wraca do kolejki.
- Archiwum z 2.0: rozpoznanie maili z załącznikami po nagłówku Content-Type.

Nie sprawdzono tu: prawdziwych serwerów IMAP i jakości OCR na Twoich skanach.


# Weryfikacja 2.1.1 — „zapętlenie” modelu

Data: 2026-10-15. Wynik: 23 testy zaliczone.

- Symulowana Ollama zwraca `token repeat limit reached` dla jednego fragmentu: fragment jest ponawiany najwyżej 2 razy, potem pomijany. Fakty z pozostałych fragmentów zostają, a dokument nie jest oznaczany jako błąd.

# Weryfikacja 2.1.2 — check, scalenie Drive Learnera, start nauki

Data: 2026-10-15. Wynik: 26 testów zaliczonych.

- `learn-import --merge`: fakty z Dysku dostają niższe numery niż fakty z poczty, profil startuje od podsumowań z Dysku (`last_fact_id` = liczba faktów z Dysku), archiwum poczty, wątki i wybrany model zostają, ustawienia Dysku przechodzą, powstaje kopia przed scaleniem, drugie scalenie jest odrzucane.
- Zwykłe `learn-import` przy działającej nauce odmawia i wskazuje `--merge`.
- `check` działa bez Ollamy, launchd i gita (zgłasza problemy z podpowiedziami, kod wyjścia 1).
- Aktualizator na kopii instalacji 2.1.1: podmiana, test, ponowne uruchomienie rozpoznaje zainstalowaną wersję.

# Weryfikacja 2.1.3 — wygaśnięcie logowania do Dysku

Data: 2026-10-19. Wynik: 30 testów zaliczonych.

- Wygasłe logowanie: przy 20 kolejnych wątkach jedna próba połączenia, jeden wpis w dzienniku i jedno powiadomienie. Stan `expired` zapisany w bazie.
- Nowe logowanie (zmiana `token.json`) od razu uruchamia ponowną próbę. Udane połączenie przywraca stan `ok`.
- `learn-drive off` / `on` / wybór „2” z menu zmieniają ustawienie. `check` przy wyłączonym Dysku pokazuje stan jako świadomy wybór, nie problem.
- Zakładka Nauka pokazuje baner przy wygasłym logowaniu.

Nie sprawdzono tu: prawdziwego wygaśnięcia tokenu Google i powiadomień macOS. Sprawdzisz je na Macu poleceniem `python sebastian.py learn-drive`.


# Weryfikacja 2.2 — Dokumenty (skany → uporządkowany PDF)

Data: 2026-10-19. Wynik: 43 testy zaliczone (13 nowych w `test_docs.py`).

Testy generują własny „skan” (obrazy stron z tekstem księgi wieczystej) i udają model wizyjny oraz tekstowy:

- **Cały przebieg:** przygotowanie → czytanie stron → porządkowanie → PDF. Strona „pisana ręcznie” jest czytana dwa razy. Słowo, w którym odczyty się różnią, jest oznaczone jako niepewne, a strona trafia „do sprawdzenia”. Słowo oznaczone przez model `[?]` jest niepewne.
- **Weryfikacja cytatów:** wpis „wymyślony” przez model (cytatu nie ma w odczycie) jest oznaczony i trafia do „Do wyjaśnienia”. Odwołanie podsumowania do nieistniejącego wpisu jest odrzucane. Tekst przekreślony (`~~`) oznacza wpis jako wykreślony.
- **PDF:** strona 1 ma spis treści i numer księgi. Wszystkie linki „skan s. N” prowadzą do właściwych stron skanu (żaden link `scan:` nie zostaje). W bocznym spisie jest „6. Skany oryginału” i każda strona. Na skanie działa wyszukiwanie tekstu z odczytu pisma. Link „« spis treści” prowadzi do strony 1.
- **Wznawianie:** przerwanie w trakcie strony (Ctrl+C / zatrzymanie usługi) nie zapisuje niedokończonej strony. Po wznowieniu gotowe strony nie są czytane ponownie.
- **Poprawki w panelu:** zła CSRF → 403, zapis strony, „Złóż PDF z poprawkami” porządkuje ponownie tylko poprawioną stronę. Strona sprawdzona znika z listy „do sprawdzenia”. ZIP „do sprawdzenia” zawiera obraz strony i odczyt.
- **Duży plik w panelu:** wgranie pliku > 7 MB przechodzi (osobny limit tylko dla wgrywania), a inne formularze nadal mają limit 6 MB (413).
- **Folder „wrzuc-tutaj”:** świeżo kopiowany plik czeka, starszy trafia do kolejki. Blokada: drugi proces nie wejdzie, `busy()` działa.
- **Usługa nauki:** `learn-run` ma w środku wątek dokumentów, który opracowuje dokument z kolejki. Zatrzymanie kończy wątki.
- **Nauka:** opracowany dokument trafia do kolejki nauki (`doc:<nr>`) i jest przetwarzany jak dokument. Nie liczy się do „Dysku”.
- Polecenia `doc-*` są kierowane do modułu, a `doctor` nie.
- Dodatkowo, ręcznie: 12-stronicowy kolorowy skan 300 dpi (48 MB) po przygotowaniu przez ocrmypdf ma 5,1 MB (bez ocrmypdf 5,3 MB), strona przekrzywiona o 1,5° została wyprostowana, a polskie znaki w PDF są poprawne (Arial/DejaVu, tylko użyte litery).

Nie sprawdzono tu: **jakości odczytu prawdziwym modelem wizyjnym** (`qwen2.5vl:7b`) na Twoich skanach, w szczególności pisma ręcznego i kurrenty, ani rzeczywistego czasu pracy na Macu. Sprawdzisz to poleceniem `python sebastian.py doc-test PLIK --strona N` na kilku trudnych stronach przed wrzuceniem całej księgi.


# Weryfikacja 2.3 — WhatsApp

Data: 2026-10-20. Wynik: 59 testów zaliczonych (16 nowych w `test_whatsapp.py`).

Bez prawdziwego WhatsAppa i bez Ollamy (model udawany, połączenie „plik” albo udawany klient neonize):

- **Przegląd:** dane z panelu (zadania z terminami, nowe maile, kalendarz z importowanego ICS) trafiają do modelu, a wynik to tekst i głosówka zaczynająca się od „Hej Andrzej!”. Bez modelu powstaje przegląd awaryjny z samych faktów. `WA_SCOPES private` wyklucza sprawy firmowe.
- **Harmonogram:** nie przed 07:00, nie po 11:30, nie dwa razy dziennie, tylko w wybrane dni. Czeka na poranną analizę, ale najwyżej godzinę. Wieczór o 20:30.
- **Usługa (`tick`):** powitanie raz po połączeniu, potem przegląd. Zlecenie z panelu („Wyślij przegląd teraz”) składa przegląd. Znak życia zapisany.
- **Rozmowa:** pomoc, zadania (numery i terminy), `zrobione 1` (status w bazie, wpis `whatsapp_done` w `events` i `undo_decisions`, drugi raz — „już zamknięte”, zły numer — komunikat), przegląd, `zapamiętaj:` (notatka prywatna), cisza/wznów, poczta, kalendarz, pytanie do modelu.
- **Wiadomości przychodzące:** duplikat ignorowany, nasze własne wiadomości (echo w czacie „Ty”) ignorowane. Wiadomość starsza niż 6 h jest zapisana bez odpowiedzi. Głosówka bez transkrypcji dostaje grzeczną odpowiedź, a głosówka z transkrypcją — odpowiedź tekstem i głosem.
- **Powiadomienia:** w ciszy nocnej czekają do rana, bez powtórzeń w ciągu doby, wyciszenie działa. `learner.notify` (np. „dokument gotowy”) trafia też na WhatsApp. Przy wyłączonym WhatsAppie nic nie jest kolejkowane.
- **Głos:** prawdziwy ffmpeg zamienia nagranie na Opus (format głosówki). Znaczniki i linki są usuwane z tekstu do czytania.
- **Filtr nadawcy na prawdziwych strukturach neonize 0.5.2:** osobny numer — tylko właściciel, także w adresacji LID (zapamiętany i rozpoznany przez bibliotekę); obcy, grupy i nasze wiadomości odrzucone. Czat „Ty” — tylko wiadomości właściciela do siebie, bez echa. Głosówka wysyłana jako PTT `audio/ogg; codecs=opus`, zawsze do właściciela.
- **Panel:** strona, podgląd (nic nie wysyła), zła CSRF → 403, „Wyślij teraz” → zlecenie.
- Dodatkowo, ręcznie: prawdziwy klient neonize tworzy się, rejestruje zdarzenia i przy braku sieci ponawia połączenie bez zawieszania usługi. Zatrzymanie działa.

Nie sprawdzono tu: **parowania i wysyłki na prawdziwym WhatsAppie** (sieć WhatsApp jest tu niedostępna), brzmienia polskiego głosu Piper (głosu nie da się tu pobrać), rozpoznawania mowy mlx-whisper (tylko Mac z Apple Silicon) ani jakości przeglądów pisanych przez prawdziwy model. Sprawdzisz to na Macu: `wa-test` (głos), `wa-brief --podglad`, `wa-login`, a potem „pomoc” na WhatsAppie.


# Weryfikacja 2.4 — rodzina i obserwacja Twojego WhatsAppa

Data: 2026-10-20. Wynik: 67 testów zaliczonych (8 nowych).

- **Rodzina:** żona widzi tylko prywatne zadania i maile (zadanie firmowe niewidoczne; w prompcie modelu brak treści firmowych, jest „Rozmawiasz z Kasia (żona …)”). `zrobione`, `dokumenty`, `whatsapp` → „to może zrobić tylko …”. `zapamiętaj:` → notatka „Od Kasia: …”. Osobny przegląd (adresat, cel `brief:rano:<numer>`, znacznik wysłania osobno od Twojego), powitanie z informacją, że rozmowy widzi właściciel, odpowiedzi idą do niej, a obcy numer jest ignorowany. Usunięcie osoby działa.
- **Filtr połączenia (struktury neonize):** numer żony przyjęty z polem „od kogo”. Gdy Sebastian jest na numerze właściciela — wiadomości żony ignorowane, wysyłka do niej zablokowana.
- **Obserwacja:** „czeka na odpowiedź”, „nieodebrane”, „warto się odezwać” liczone bez modelu, lista pomijanych działa. Sugestie bez modelu z reguł, z modelem — streszczenia. Tekst podsumowania z listami Oddzwoń/Odpisz/Warto się odezwać. Przegląd poranny zawiera WhatsApp i osobną wiadomość „📱”. Komendy `do kogo`, `kto pisał`, `rozmowa jan`. Żona nie widzi Twojego WhatsAppa. Sprzątanie starych wiadomości. Zapis z kolejki i powiadomienie o wylogowaniu.
- **Odczyt struktur neonize w obserwacji:** tekst, nazwa z kontaktów albo profilu, głosówka, zdjęcie z podpisem, Twoje wiadomości, LID → numer, grupy pominięte (lub z nazwą grupy po włączeniu), statusy i reakcje pominięte, **brak oznaczania jako przeczytane**.
- Ręcznie: prawdziwy klient obserwacji tworzy się z obsługą połączeń przychodzących, przy braku sieci ponawia bez zawieszania.

Nie sprawdzono tu: połączenia z prawdziwym WhatsAppem (sieć niedostępna) — w szczególności tego, jak WhatsApp przekazuje połączonemu urządzeniu informacje o połączeniach i nazwy kontaktów na Twoim koncie. Sprawdzisz po `wa-watch login`: następnego dnia `python sebastian.py wa-watch podsumowanie`.


# Weryfikacja 2.5 — pamięć rozmów, załączniki, akta osób, dostęp pełny

Data: 2026-10-20. Wynik: 77 testów zaliczonych (10 nowych; `test_whatsapp.py`: 34).

- **Na stałe:** domyślnie `WA_WATCH_KEEP_DAYS 0` — sprzątanie niczego nie usuwa; po ustawieniu liczby dni starsze wiadomości znikają jak dotąd.
- **Załączniki:** PDF przesłany w rozmowie (także przez Ciebie) jest czytany raz (ten sam plik drugi raz — z pamięci), tekst trafia do zapisu rozmowy i podsumowań („📎 …”), zdjęcia bez tekstu są pomijane.
- **Historia przy połączeniu:** odczyt struktur `HistorySync` (rozmowy, Twoje wiadomości, nazwy), pominięte statusy, grupy i kanały, głosówki z historii oznaczone bez pobierania.
- **Nauka z rozmów:** miesiąc rozmowy → pozycja `wa:<rozmowa>:<miesiąc>` w nauce (zakres `whatsapp`), tekst z oznaczeniem Twoich wiadomości i załącznikami, przetworzenie przez `process_file`, ponowne przeczytanie po nowej wiadomości; fakty z WhatsAppa nie trafiają do osób z dostępem prywatnym ani do Open WebUI.
- **Akta osób:** aktualizacja z rozmowy (model udawany), `kto to Jan?` (także z odmianą i znakiem zapytania), akta w kontekście zwykłych pytań, plik `.md`, odmowa dla dostępu prywatnego.
- **Dostęp pełny:** osoba dodana z `--dostep pelny` widzi zadania firmowe, dokumenty, może zamykać zadania (własna numeracja), ma zakresy jak właściciel, a model dostaje informację, że rozmawia z osobą z pełnym dostępem. Powitanie mówi o pełnym dostępie. Numer spoza listy jest ignorowany. Nieznany poziom dostępu → błąd.

Nie sprawdzono tu: jak dużo historii przekaże prawdziwy telefon przy połączeniu, pobierania plików z serwerów WhatsAppa (sieć niedostępna) ani jakości akt pisanych przez prawdziwy model. Sprawdzisz na Macu: `python sebastian.py wa-watch` (liczba akt i załączników), potem `kto to <imię>` na WhatsAppie.


# Weryfikacja 2.5.1 — diagnostyka odrzuconych numerów

Data: 2026-10-20. Wynik: 78 testów zaliczonych (1 nowy).

- Wiadomość z numeru spoza listy: brak odpowiedzi, jeden wpis w logu na godzinę z zamaskowanym numerem (`+48123***789`) i **bez treści**; nadawca w adresacji LID bez numeru opisany jako „numer ukryty przez WhatsApp”. Lista „Odrzucone” w `wa-status` bez duplikatów, najwyżej 8 pozycji.
- Wszystkie testy 2.5 (lista dozwolonych, dostęp pełny i prywatny, filtr nadawcy) bez zmian.


# Weryfikacja 2.5.2 — nauka z rozmów WhatsApp w procesie nauki

Data: 2026-10-20. Wynik: 78 testów zaliczonych.

- Odtworzony błąd z Maca: przetwarzanie pozycji `wa:…` przy niepodłączonym module WhatsAppa (tak jest w osobnym procesie nauki) kończyło się `AttributeError: … 'TZ'` — test na wersji 2.5/2.5.1 nie przechodzi, na 2.5.2 przechodzi (pozycja „przeczytana”, fakty zapisane).
- Pętla nauki: pozycja z trzema błędami z rzędu dostaje status „błąd” zamiast blokować kolejkę (sprawdzone przeglądem kodu; `learn-retry` przywraca pozycje z błędem).

Lekcja: test nauki z rozmów uruchamiał się w procesie, w którym WhatsApp był już podłączony — dlatego nie wykrył błędu. Test odtwarza teraz warunki osobnego procesu.


# Weryfikacja 2.6 — asystent na WhatsAppie

Data: 2026-11-03. Wynik: **84 testy zaliczone** (6 nowych w `test_whatsapp.py`).

- **Zakres asystenta:** widzi zadania firmowe, nie widzi prywatnych; „whatsapp” i „dokumenty” odmówione; model dostaje
  „dane wyłącznie z FIRMOWEJ poczty”; notatka `zapamiętaj:` trafia do Pamięci bota jako firmowa; powitanie „Cześć, Janie!”
  z opisem roli. Numer podany ze spacjami i bez kierunkowego zapisany w pełnej postaci (48…).
- **Zadania z WhatsAppa:** `dodaj zadanie: … do piątku` → wiersz w panelu (zakres firmowy, kategoria „termin”, termin
  w najbliższy piątek), widoczny w `zadania`, `szczegóły N` pokazuje autora, `zrobione N` zamyka; właściciel dostaje
  wiadomości „dodał zadanie” i „zamknął zadanie”. `dodaj zadanie: prywatne: …` (właściciel) → zadanie prywatne,
  niewidoczne dla asystenta. Rodzina nie może dodawać zadań. Panel (funkcja `enriched`) czyta takie zadanie poprawnie.
- **Terminy:** 15.11, 05.01.2027, 10.01 (→ przyszły rok), „do jutra”, „na piątek”; „do Kowalskiej” nie jest terminem.
- **Pytania:** pytanie z numerem trafia do właściciela, `pytania` je pokazuje, `odpowiedz 1: …` wraca do pytającego,
  `odp: …` bez numeru przy jednym otwartym pytaniu.
- **Pomysły:** zgłoszenie od asystenta → wiadomość do właściciela; własny pomysł właściciela bez powiadomienia;
  `pomysły` tylko dla właściciela; `wa-pomysly` w Terminalu; panel pokazuje pytania i pomysły.
- Poprawiony test rodziny, który miał wpisaną na sztywno datę 20.10 i od 21.10 przestał przechodzić (błąd testu, nie programu).


# Weryfikacja 2.7 — dodatki i Przypominacz

Data: 2026-11-09. Wynik: **100 testów zaliczonych** (16 nowych w `test_dodatki.py`). Bez WhatsAppa, Ollamy i Twilio
(udawane), z prawdziwym kalendarzem ICS w bazie i zegarem przesuwanym w teście.

- **Gniazdo:** Przypominacz wykryty i domyślnie włączony; „pomoc” pokazuje dodatki; wyłączenie działa; zepsuty dodatek
  (nieznane uprawnienie, błąd w kodzie) jest wyłączony z opisem problemu i nie psuje reszty; Twój dodatek domyślnie
  wyłączony, po włączeniu odpowiada; brak uprawnienia → błąd, po 3 błędach pauza; kalendarz podaje początek i koniec spotkań.
- **Godzina:** spotkania 10–11 i 16–17:30 → 17:45; bez spotkań 18:00; spotkanie rano → 17:00; spotkanie do 23 → 21:30;
  nagrane o 18:30 → dziś (19:30), o 21:00 → jutro. Terminy wprost: jutro, „o 16”, „o 9:30” (→ jutro), „za 2 godziny”,
  „za pół godziny”, „w piątek o 10”.
- **Rozpoznanie:** „Sebastian, przypomnij mi, żeby oddzwonić…” bez modelu → „Oddzwonić do pani Kowalskiej w sprawie umowy”
  i bez zwykłej odpowiedzi; głosówka bez słowa „przypomnij” → model dzieli na dwie sprawy; pytanie głosowe → zwykła
  odpowiedź; zwykły tekst i „zapamiętaj:” nie są przypomnieniem.
- **Cały wieczór:** kontekst z WhatsAppa w tle; o 17:40 nic, o 17:45 wiadomość z „↳ kontekstem” i głos „Hej Andrzeju!
  … Masz jedną sprawę…”; po 61 min „Andrzej, przypominam”; po kolejnych 16 min minka — dokładnie raz; następnego dnia
  sprawa wraca wieczorem z dopiskiem „czeka od wczoraj”.
- **Odpowiedzi:** „1 zrobione, 2 jutro” (a 3 czeka — bez drugiego telefonu), „3 do zadań” → zadanie w panelu; swobodne
  zdanie głosem → model: „po kolacji” = 20:30, „już ktoś kupił” = skreślone; pytanie z liczbą w trakcie przypomnienia →
  zwykła odpowiedź; „ok” kończy dzwonienie; reguły dla 10 wariantów zapisu.
- **Komendy:** `przypomnienia`, `przypomnij teraz`; drugi telefon w ciszy nocnej pominięty (bez minki).
- **Twilio:** połączenie na numer właściciela z polskim głosem zamiast głosówki; drugie nieodebrane → od razu minka;
  brak tokenu → głosówka; niezałatwione sprawy dołączają do kolejnego przypomnienia.
- **Polecenia w Terminalu:** `dzis`, `sprawdz`, `dodaj`, `lista`, `ustaw`, `historia`.

Nie sprawdzono tu: prawdziwego WhatsAppa i głosu na Macu, jakości rozpoznawania przez qwen2.5 na prawdziwych głosówkach,
prawdziwego Twilio.


# Weryfikacja 2.8 — dodatek Rekrutacja

Data: 2026-11-11. Środowisko: Linux, Python 3.13. Bez Gmaila, Ollamy, Tailscale, WhatsAppa i launchd — wszystko udawane.

Wynik: 100 testów zaliczonych, 7 pominiętych (`test_sebastian`, `test_dodatki`, `test_whatsapp`, nowy `test_rekrutacja` — 35 testów).

- **Fakty i dokumenty:** wybór faktów z modelu odrzuca nieistniejące numery i niczego nie gubi; CV ma jedną stronę i zawiera
  wyłącznie dane z bazy (stanowiska, daty, punkty, narzędzia z poziomem, prawo jazdy, RODO); własna klauzula RODO pracodawcy trafia do CV;
  kontroler prawdy łapie zmyśloną liczbę lat, SAP, język niemiecki i certyfikat, a nie zgłasza prawdziwych faktów.
- **Duplikaty:** „ABC Sp. z o.o. / … (K/M)” = „abc / …”; ta sama oferta drugi raz → `duplikat`; ta sama firma bez ogłoszenia dwa razy → jedna aplikacja.
- **Przebieg:** przygotowanie → nic nie wychodzi bez zatwierdzenia → wysyłka z dwoma PDF-ami i właściwym tematem; okno godzin,
  sobota, pauza i limit blokują wysyłkę; błąd wysyłki → `blad` z opisem (nic nie ginie); raport raz dziennie ze skrzynki Sebastiana.
- **Panel:** link pierwszego wejścia działa raz; bez CSRF → 400; obcy host → 403; 5 błędnych haseł → przerwa; całe powitanie (8 kroków)
  zapisuje dane, narzędzia z poziomami i ustawienia pracy; dodanie oferty, przygotowanie w tle, zatwierdzenie, wysyłka; brak dostępu do
  plików spoza folderu aplikacji; wszystkie strony renderują się bez błędów.
- **Odpowiedzi:** zaproszenie → status, WhatsApp na numer Agi z listy, mail od Sebastiana, pytanie „czy termin pasuje”, odpowiedź Agi
  zapamiętana, szkic w wątku (`Re:`); ta sama wiadomość drugi raz nie jest liczona; odmowa → podziękowanie; prywatna poczta nie jest
  zapisywana; autoresponder nie zmienia statusu; przypomnienie po 10 dniach dokładnie raz.
- **Źródła i formularze:** strona z listą → tylko pasujący link, drugi przegląd nic nie dubluje, Pracuj.pl wyłączony automatycznie; JSON-LD
  JobPosting; oferta z Gdańska i oferta z niską oceną pominięte; autopilot; import firm i aplikacja bez ogłoszenia; kanał formularza z zestawem pól
  (oczekiwania netto); Recruitee: poprawne pola, zgoda RODO zaznaczona, wymagane pytanie otwarte → bez wysyłki.
- **Po niezależnym przeglądzie kodu (15 poprawek):** własne powiadomienia i raporty Sebastiana nie są czytane jako odpowiedzi
  (znacznik `X-Sebastian-Rekrutacja` i adres nadawcy); adresy IOD/RODO z ogłoszenia nigdy nie są adresatem; „niestety … zapraszamy”
  to zaproszenie, a podziękowanie wychodzi tylko przy odmowie potwierdzonej przez model, w oknie wysyłki i nie na adresy no-reply;
  brak odpowiedzi kontrolera prawdy = „do sprawdzenia” (autopilot nie wyśle); stara poczta z domeny pracodawcy sprzed wysyłki jest
  pomijana; aplikacja jest zajmowana przed wysyłką (`wysylanie`), po restarcie nie wychodzi drugi raz, błąd „nic nie wyszło” wraca do
  kolejki, a „mogło wyjść” czeka na Agę; szkic odpowiedzi wychodzi raz; Recruitee da się zatwierdzić bez maila; pominiętą ofertę można
  przygotować ponownie; oferty ponad limit przeglądu nie przepadają; „raport teraz” nie odwołuje wieczornego; linki tylko http(s);
  przekierowania źródeł sprawdzane krok po kroku; skrzynka czytana od najstarszych, pozycja zapisywana po przetworzeniu wiadomości.

Nie sprawdzono tu: prawdziwego Gmaila (logowanie hasłem aplikacji, IMAP), prawdziwych stron startowych źródeł (z tego środowiska
nie ma do nich dostępu), formularza Recruitee na żywo, jakości listów z modelu na Macu, wyglądu w Safari, nasłuchu na adresie Tailscale
i zapory macOS.


# Weryfikacja 2.8.1

Data: 2026-11-11. Wynik: `test_rekrutacja` — 46 testów zaliczonych; `test_sebastian`, `test_dodatki`, `test_whatsapp` bez zmian (zaliczone).

- RODO: informacja o administratorze nie jest zgodą → w CV klauzula domyślna z nazwą firmy; prawdziwa zgoda przechodzi bez zmian; migracja przelicza czekające aplikacje.
- Sprzedaż i obsługa klienta przechodzą filtry; przy ustawionym wykluczeniu nadal są pomijane; social media wykluczone.
- CV: od najnowszego; ranking z oferty decyduje o długości opisu; stanowiska opcjonalne tylko na życzenie modelu; tylko „Kraków” w kontakcie; jedna strona.
- Adres firmy: strona z nazwą firmy i adres w jej domenie (IOD pominięty); obca strona z podobną nazwą odrzucona; mail „w nawiązaniu do ogłoszenia … (link)”; adres zgadnięty → bez autopilota; liczby w linkach nie są zgłaszane przez kontrolę prawdy.
- Agregatory: Adzuna i Jooble — poprawne parametry (Kraków, promień z ustawień), bez klucza „czeka na klucz”.
- Import wiedzy: z eksportu tylko wiadomości użytkowniczki z rozmów o pracy; niepewne i zarobki nigdy nie trafiają do bazy; dopisywanie bez duplikatów; uzupełnienia z pliku idempotentne.

Nie sprawdzono tu: prawdziwych odpowiedzi Jooble, Adzuny i Brave, prawdziwych stron firm.


# Weryfikacja 2.8.2

Data: 2026-11-12. Wynik: `test_rekrutacja` — 50 testów zaliczonych; `test_sebastian`, `test_dodatki`, `test_whatsapp` zaliczone.

- Najwyżej 3 punkty przy stanowisku, w kolejności od modelu; kursy od najnowszego (bez roku na końcu).
- Profil pod ofertę: przechodzi tylko tekst bez liczb i narzędzi spoza faktów; zapisany jako wersja Sebastiana.
- Edycja CV: własne punkty i opis, ukrycie stanowiska, przywrócenie wersji Sebastiana; brak zmian nie tworzy „własnej wersji”; zatwierdzona aplikacja wraca do zatwierdzenia; wysłanej nie można zmienić.
- Podgląd: CV z prawdziwymi danymi mieści się na jednej stronie i jest wypełnione.


# Weryfikacja 2.8.3

Data: 2026-11-12. Wynik: `test_rekrutacja` — 57 testów zaliczonych; `test_sebastian`, `test_dodatki`, `test_whatsapp` zaliczone.

- Klauzula RODO: luka po „stanowisko” uzupełniona, dwie zgody w jednym zdaniu, bez stanowiska — bez „na stanowisko”.
- Język: formy męskie, przesadne obietnice i zdania bez sensu wykrywane; „działem”, „jestem gotowa” nie są błędem.
- List z formami męskimi → druga próba → list z faktów (bez błędów); mail zawsze z szablonu, „list motywacyjny”.
- List PDF: dane nadawczyni nad treścią, „Dotyczy”, „Z poważaniem”, klauzula RODO; jedna strona (sprawdzone wizualnie).
- Oferta: wynagrodzenie tylko z treści ogłoszenia, dopasowanie wymagań (mam/częściowo/brak), strona aplikacji z dojazdem i pobieraniem.
- Migracja: czekające aplikacje przygotowane od nowa, jednorazowo.
- Izolacja: przy `SEBASTIAN_TESTY=1` kontekst dodatku nie wywołuje `security` (ani odczytu, ani zapisu); próbne hasła z dawnych testów są ignorowane; brak hasła skrzynki nie psuje kolejki (zatwierdzone czekają).


# Weryfikacja 2.8.4

Data: 2026-11-12. Wynik: `test_rekrutacja` — 63 testy zaliczone; `test_sebastian`, `test_dodatki`, `test_whatsapp` zaliczone.
Przypadki z prawdziwej skrzynki: list „Droga Agnieszko… przygotowywałaś” odrzucony i zastąpiony listem z faktów; eRecruiter „Czy to Twoja
aplikacja?” → potwierdź aplikację (mimo że model mówi „zaproszenie”); „Twoje zgłoszenie trafiło…” → potwierdzenie; „skontaktujemy się
wyłącznie z wybranymi” → potwierdzenie (nie odmowa); Pracuj.pl „sprawdź kompetencje innych kandydatów” → reklama; prawdziwe zaproszenie
z adresu no-reply i prawdziwa odmowa rozpoznane; „&nbsp;” usunięte, przycisk potwierdzenia wyciągnięty; migracja poprawia zapisane wiadomości.


# Weryfikacja 2.8.5

Data: 2026-11-12. `test_rekrutacja` — 65 testów zaliczonych; pozostałe zestawy zaliczone. Wyjaśnienia ze zrzutu Agi porządkowane (bez „FAKTY”, „kandydatka”, powtórzeń wymagania); wymaganie spoza treści ogłoszenia pomijane; stara analiza odświeżana raz.


# Weryfikacja 2.9

Data: 2026-11-12. `test_rekrutacja` — 70 testów zaliczonych; pozostałe zestawy zaliczone. Owca: rano raz, przypomnienie w pierwszym tygodniu, potem tylko w tyle, gratulacje raz, nic w weekend; link z celem tylko z tokenem i z dnia maila; daty z terminów (20.11, 17 listopada, jutro; 10.00 h to godzina); etapy zaproszenie → dzień rozmowy → jak poszło → oferta → przyjęcie (z potwierdzeniem) → koniec, każdy mail raz. Maile i karta „Dziś” obejrzane w przeglądarce.


# Weryfikacja 2.10

Data: 2026-11-12. `test_rekrutacja` — 75 testów zaliczonych; pozostałe zestawy zaliczone. Alert Pracuj.pl: 4 oferty w mailu → 2 w kolejce (bez kierowcy i bez Bochni przy 20 km), firma z treści maila, bez powiadomień, bez powtórek; potwierdzenie z portalu i mail od pracodawcy nie są alertem. CBOP: bez nazwy partnera i w dzień nic; wieczorem zapytanie z Partner i Wojewodztwo 12, ZIP z JSON → oferta z e-mailem urzędu gminy (magazynier i Tarnów odfiltrowane), raz na dobę, „Niepoprawna autoryzacja” rozpoznana. Zakładka i strona „Więcej ofert” działają; mail „Mam pomysł!” wychodzi dopiero w następny dzień roboczy rano, raz. Strukturę zapytania CBOP oparto na instrukcji ePraca (wersja 3); prawdziwego połączenia z CBOP nie sprawdzono (wymaga nazwy partnera).


# Weryfikacja 2.11

Data: 2026-11-12. `test_rekrutacja` — 77 testów zaliczonych; pozostałe zestawy zaliczone. Raport wieczorny: HTML z owcą wieczorną, odpowiedzi, lista wysłanych, przycisk do panelu, linia owcy w wersji tekstowej. Powiadomienie o zaproszeniu: HTML z owcą, streszczeniem, terminem i linkiem do wiadomości. Oba obejrzane w przeglądarce.


# Weryfikacja 2.12

Data: 2026-11-13. `test_rekrutacja` — 83 testy zaliczone; pozostałe zestawy zaliczone. Gemini (symulowane API): wybór modelu (najnowszy stabilny flash), bez klucza zero zapytań, w zapytaniu brak imienia, nazwiska, e-maila i telefonu, podpis dopisany lokalnie, 429 → przerwa i list lokalny, dzienny limit i wyłącznik, czekający list napisany na nowo raz (z PDF). Prawdziwego klucza Gemini nie sprawdzono.

# Weryfikacja 2.12.1

- `Rewrite2121.test_backoff_grows_and_resets` — przerwy po 429 rosną od ok. minuty, zerują się po sukcesie.
- `Rewrite2121.test_local_text_not_marked_as_gemini` — bez odpowiedzi Gemini list nie jest oznaczany jako przepisany.
- `Rewrite2121.test_command_rewrites_all_and_keeps_approved` — `przepisz` przepisuje czekające, zatwierdzone tylko z flagą.
- W testach tempo (`PACE`) wyłączone; bez sieci.

# Weryfikacja 2.13

`Conversation213` (bez sieci, model udawany):
- „nie mam dziś czasu” bez modelu → pytanie o termin, owca milczy do końca dnia; „w czwartek o 10” → przypomnienie 12.11 10:00;
- odpowiedź modelu: przerwa, przypomnienie, pamięć; kolejna wiadomość ma w poleceniu historię i pamięć; cel dnia z rozmowy; bez powtórek w pamięci;
- zły rodzaj gramatyczny → poprawka, potem reguły;
- mail od Agi: odpowiedź w tym samym wątku, bez cytatu, obcy nadawca pominięty, bez podwójnej odpowiedzi, wyłączenie w ustawieniach;
- WhatsApp od Agi przez `dodatki_host.on_message` → odpowiedź na jej numer; „/…” i obce numery przechodzą dalej;
- przypomnienie wychodzi raz i kończy przerwę; dni przerwy nie przerywają serii;
- wiadomość o kryzysie → troska i telefon zaufania, bez modelu i bez pchania;
- rozpoznawanie terminów (dzień tygodnia, „jutro wieczorem”, „za tydzień”, data); strona Rozmowa w panelu.

# Weryfikacja 2.13.1

`GeminiLimits2131`: kolejność modeli (flash → starszy flash → flash-lite, bez preview i pro); dzienny limit (QuotaFailure *PerDay*) blokuje model do rana i następne zapytanie idzie innym; 503 → krótka przerwa i inny model; `retryDelay` z odpowiedzi Google; gdy wszystkie odpoczywają — przerwa bez zapytań; przepisywanie nie woła modelu lokalnego.
