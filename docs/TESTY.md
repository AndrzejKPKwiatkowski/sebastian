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
