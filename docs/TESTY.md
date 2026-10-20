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
