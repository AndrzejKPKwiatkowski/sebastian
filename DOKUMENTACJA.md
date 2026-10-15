# Sebastian — pełna dokumentacja projektu

**Wersja opisana w dokumencie: 2.1.1** (październik 2026)
Lokalny asystent poczty i spraw na Macu, z modułem nauki, który buduje wiedzę o właścicielu z Dysku Google, poczty i załączników.

> **Dla kogo jest ten dokument.** Dla osoby, która przejmuje projekt albo musi coś w nim zrobić ręcznie: zainstalować od zera, przenieść na inny komputer, naprawić, zaktualizować albo rozwinąć kod. Nie trzeba być programistą, żeby korzystać z rozdziałów 1–14. Rozdział 15 jest dla osoby, która zmienia kod.

---

## Spis treści

1. [Czym jest Sebastian](#1-czym-jest-sebastian)
2. [Zasady, których projekt pilnuje](#2-zasady-których-projekt-pilnuje)
3. [Jak to działa — architektura](#3-jak-to-działa--architektura)
4. [Wymagania](#4-wymagania)
5. [Instalacja od zera (wersja 2.1)](#5-instalacja-od-zera-wersja-21)
6. [Codzienna praca w panelu](#6-codzienna-praca-w-panelu)
7. [Praca w tle — harmonogramy macOS](#7-praca-w-tle--harmonogramy-macos)
8. [Moduł Nauka — szczegóły](#8-moduł-nauka--szczegóły)
9. [Połączenie z Open WebUI](#9-połączenie-z-open-webui)
10. [Mapa plików i danych](#10-mapa-plików-i-danych)
11. [Wszystkie polecenia](#11-wszystkie-polecenia)
12. [Wszystkie ustawienia](#12-wszystkie-ustawienia)
13. [Bezpieczeństwo i prywatność](#13-bezpieczeństwo-i-prywatność)
14. [Kopie zapasowe, przenoszenie, aktualizacje, rozwiązywanie problemów](#14-kopie-zapasowe-przenoszenie-aktualizacje-rozwiązywanie-problemów)
15. [Dla programisty — budowa kodu i zasady zmian](#15-dla-programisty--budowa-kodu-i-zasady-zmian)
16. [Historia wersji](#16-historia-wersji)
17. [Słowniczek](#17-słowniczek)

---

## 1. Czym jest Sebastian

Sebastian to program działający **wyłącznie na Macu właściciela** (Mac Studio M1 Max). Składa się z dwóch współpracujących części.

**Centrum spraw (panel).** Strona w przeglądarce pod adresem http://127.0.0.1:8765. Sebastian:

- codziennie rano pobiera nową pocztę z trzech skrzynek (Gmail, Murena, Partners/inPartners),
- prosi lokalny model AI (Ollama) o streszczenie, kategorię, priorytet i proponowany krok,
- pokazuje maile do decyzji: *pomiń / do zadań / zrobione*, z kategorią i komentarzem,
- prowadzi listę zadań, pozwala odpowiedzieć na maila (po podglądzie i potwierdzeniu), przygotować wydarzenie w kalendarzu (plik ICS) i sprawdzić konflikty terminów,
- zapamiętuje Twoje decyzje i używa ich jako przykładów przy kolejnych analizach („pamięć bota”).

**Nauka (od wersji 2.0).** Proces w tle, który bez Twojej obsługi:

- czyta Dysk Google, całą pocztę (także archiwum i wysłane) oraz załączniki,
- wyciąga z nich fakty o właścicielu,
- składa z nich dwa dokumenty: **Bieżące sprawy** (co się teraz dzieje) i **Profil wiedzy** (trwała wiedza: praca, ludzie, cele, styl pracy i komunikacji),
- opcjonalnie wysyła wszystko do baz wiedzy (RAG) w Open WebUI, żeby czat z lokalnym modelem „znał” właściciela.

**Open WebUI** to osobna aplikacja (w Dockerze), w której rozmawia się z lokalnym modelem. Sebastian przekazuje do niej raporty, pamięć i wiedzę z nauki (rozdział 9).

---

## 2. Zasady, których projekt pilnuje

Pilnuj ich przy każdej zmianie kodu i konfiguracji.

1. **Wszystko lokalnie.** Poczta, baza, fakty i teksty są na Macu. Model AI to lokalna Ollama (`127.0.0.1:11434`). Analiza poczty odmawia modeli z dopiskiem `cloud`.
2. **Skrzynki tylko do odczytu.** Pobieranie maili i załączników działa w trybie `readonly` z `BODY.PEEK`. Nic nie jest usuwane, przenoszone ani oznaczane jako przeczytane. Jedyny wyjątek to świadoma wysyłka odpowiedzi z panelu: po podglądzie, zaznaczeniu potwierdzenia i kliknięciu „Wyślij”. Opcjonalnie dochodzi dopisanie kopii do folderu Wysłane, jeśli właściciel to włączy.
3. **Decyzja należy do człowieka.** AI proponuje kategorię, priorytet, pominięcie i termin, ale nigdy sama nie pomija, nie zamyka spraw i nie wysyła maili.
4. **Treść maili to dane, nie polecenia.** Wszystkie prompty mówią modelowi, żeby nie wykonywał instrukcji znalezionych w mailach.
5. **Hasła tylko w Pęku kluczy macOS** (usługa `SebastianMail`). Nigdy w plikach.
6. **Nic z folderu `data/` nie trafia na GitHub.** Ani maile, ani baza, ani klucze. Pilnuje tego `.gitignore`, a w razie wątpliwości rozdział 13.
7. **Model nie jest trenowany.** „Uczenie się” oznacza przykłady decyzji, notatki i fakty, które model dostaje jako kontekst, czyli RAG. Wagi modelu się nie zmieniają.
8. **Dwa zakresy: prywatny i firmowy.** Konta mają przypisany zakres `private` (Gmail, Murena) albo `work` (Partners). Panel, pamięć i narzędzia Open WebUI je rozdzielają.

---

## 3. Jak to działa — architektura

```
                ┌──────────────── Mac Studio ────────────────────────────────────────────┐
  Gmail ───┐    │                                                                        │
  Murena ──┼─IMAP (tylko odczyt)─► sebastian.py  ── analiza ──► Ollama (lokalny model)    │
  Partners ┘    │   (pobieranie nowej poczty 06:30)            ▲                         │
     │          │        │                                     │                         │
     │          │        ▼                                     │                         │
     │          │  data/sebastian.sqlite3 ◄── decyzje ── Panel http://127.0.0.1:8765     │
     │          │  (maile, analizy, decyzje,                   (Flask, tylko na Macu)     │
     │          │   zadania, odpowiedzi, kalendarz)                                      │
     │          │        │  odczyt                                                       │
     │          │        ▼                                                               │
     └─IMAP archiwum + załączniki ─► NAUKA (learner*.py, w tle) ── fakty ──► Ollama      │
  Dysk Google ─────── API (odczyt) ─►   data/learner/stan.sqlite3                        │
                │                       data/learner/wyniki/  Bieżące sprawy, Profil     │
                │                       data/learner/teksty/  pełne teksty               │
                │                              │                                         │
                │   raport + pamięć (docker cp)│  profil, fakty, teksty (API)            │
                │                              ▼                                         │
                │                      Open WebUI (Docker) ── czat z lokalnym modelem     │
                └────────────────────────────────────────────────────────────────────────┘
```

### Składniki

| Część | Pliki | Co robi |
| --- | --- | --- |
| Rdzeń i polecenia | `sebastian.py` | Konfiguracja, baza, IMAP (pobieranie), analiza AI, raporty, panel Flask, wszystkie polecenia `python sebastian.py …` |
| Decyzje i pamięć przykładów | `feedback.py` | Kategorie (katalog tematów), dobór do 4 podobnych przykładów decyzji do każdej analizy |
| Priorytety i postęp | `progress.py` | Macierz Eisenhowera, wyjątki ważnych nadawców, szybkie „Pomiń” z cofnięciem, strona „Podsumowanie i postęp” |
| Szybkie przyciski | `quick_actions.py` | „Tak, przypisz kategorię”, „Do zadań”, „Zadanie wykonane”, zmiana priorytetu, z cofnięciem |
| Pamięć bota | `knowledge.py` | Twoje notatki i preferencje, eksport pamięci dla Open WebUI (`knowledge-*.json`), kopiowanie do Dockera |
| Poczta wychodząca i załączniki | `mail_actions.py` | Pobieranie załącznika na żądanie (panel), odpowiedzi SMTP z podglądem, stopki, kopia w Wysłanych |
| Kalendarz | `calendar_actions.py` | Szkic wydarzenia, eksport ICS, import kalendarzy ICS, konflikty, dojazd |
| Trasy panelu | `dashboard_actions.py` | Strony załączników, odpowiedzi, nazw i stopek, kalendarzy |
| Poranek | `morning.py` | Zadanie launchd: 06:30 pobranie nowej poczty i analiza, co 15 min odświeżanie kopii dla Open WebUI |
| Nauka — rdzeń | `learner.py` | Ustawienia, Dysk Google, odczyt dokumentów (PDF, Office, OCR), fakty, Bieżące sprawy, Profil, RAG, pętla pracy, polecenia `learn-*` |
| Nauka — poczta | `learner_mail.py` | Wątki z bazy Sebastiana, archiwum IMAP, filtry, tekst wątku dla modelu |
| Nauka — załączniki | `learner_attach.py` | Pobieranie i odczyt załączników, pamięć podręczna plików |
| Nauka — panel | `learner_web.py`, `templates/learner.html` | Zakładka „Nauka” (tylko podgląd) |
| Narzędzia Open WebUI | `openwebui_tool.py`, `openwebui_memory_tool.py` | Kod do wklejenia w Open WebUI → Tools: „moje sprawy” i „pamięć” |
| Wygląd panelu | `templates/*.html`, `static/*.js` | Szablony HTML (Jinja2) i drobne skrypty |
| Testy | `test_sebastian.py`, `test_learner.py` | Testy automatyczne (bez prawdziwych skrzynek i bez Ollamy) |

### Dwie bazy danych

- `data/sebastian.sqlite3`: maile pobrane przez Sebastiana, analizy, decyzje, zadania, odpowiedzi, kalendarz, notatki. **To serce panelu.**
- `data/learner/stan.sqlite3`: stan nauki: lista dokumentów i wątków, fakty, podsumowania, archiwum maili, załączniki, synchronizacja z Open WebUI.

Nauka **czyta** bazę Sebastiana, ale do niej nie pisze. Archiwum skrzynek, które dociąga nauka, trafia wyłącznie do bazy nauki, więc nie zaśmieca kolejki decyzji w panelu.

---

## 4. Wymagania

| Element | Wymaganie | Uwagi |
| --- | --- | --- |
| Komputer | Mac z procesorem Apple (M1 lub nowszy) | Sprawdzone pod Mac Studio M1 Max |
| System | macOS z ustawioną strefą czasu **Warszawa** | Poranek 06:30 liczy czas systemowy |
| Python | 3.11 lub nowszy | Na Macu właściciela: 3.12 (pyenv) |
| Ollama | Aplikacja Ollama, lokalny model | Analiza poczty: np. `qwen3.5:9b`. Nauka: np. `qwen2.5:14b`. Oba muszą być na liście `ollama list` |
| Homebrew | https://brew.sh | Do Tesseracta (OCR) |
| Tesseract | `brew install tesseract tesseract-lang` | Tekst ze skanów i zdjęć (Dysk, załączniki) |
| Docker Desktop + Open WebUI | opcjonalnie | Rozmowa z modelem z wiedzą Sebastiana |
| Hasła do skrzynek | IMAP/SMTP | Gmail: **hasło aplikacji** (wymaga 2FA). Murena: hasło konta. Partners: hasło według instrukcji firmy |
| Google Cloud | projekt z włączonym Google Drive API i kluczem OAuth „Aplikacja komputerowa” | Tylko do czytania Dysku przez naukę (rozdział 5.6) |
| Miejsce na dysku | kilka–kilkanaście GB | Archiwum maili, pełne teksty, kopie zapasowe |
| Pamięć RAM | 32 GB wystarcza dla modeli do 14B | Dwa modele (poranek + nauka) mogą być w pamięci jednocześnie |

**Biblioteki Pythona** instaluje `install.command`: `requirements.txt` (panel, poczta, kalendarz) i `requirements-learner.txt` (Dysk Google, PDF, Word, Excel, PowerPoint, OCR). Do testów służy dodatkowo `requirements-test.txt`.

---

## 5. Instalacja od zera (wersja 2.1)

> Każde polecenie wklejaj do **Terminala** (Cmd + Spacja → „Terminal”) i zatwierdzaj Enterem. Nie przepisuj znaku `%` z końca linii poleceń. Hasła wpisywane w Terminalu są niewidoczne. To normalne.

### 5.1. Pobranie programu

Z GitHuba (repozytorium prywatne, potrzebny dostęp):

```bash
mkdir -p ~/SebastianSystem
cd ~/SebastianSystem
git clone https://github.com/<właściciel>/<repozytorium>.git sebastian-start
cd sebastian-start
```

Albo z paczki ZIP: rozpakuj tak, żeby powstał folder `~/SebastianSystem/sebastian-start`.

> **Nie umieszczaj folderu w Pobranych, na Biurku, w Dokumentach ani w iCloud.** macOS blokuje tam programom działającym w tle dostęp do plików.

### 5.2. Instalacja bibliotek

```bash
cd ~/SebastianSystem/sebastian-start
bash install.command
source .venv/bin/activate
python sebastian.py doctor
```

`install.command` tworzy środowisko `.venv`, instaluje biblioteki i zakłada pustą bazę z kluczem panelu (`python sebastian.py init`). `doctor` pokazuje wersję Pythona i modele dostępne w Ollamie.

**Przy każdej kolejnej pracy w Terminalu** zaczynaj od:

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
```

Na początku linii pojawi się `(.venv)`.

### 5.3. Model do analizy poczty

```bash
ollama list
python sebastian.py model "qwen3.5:9b"
```

Wpisz dokładną nazwę z kolumny NAME. Tylko lokalne modele, bez dopisku `cloud`.

### 5.4. Skrzynki pocztowe

Adresy kont są w `data/config.json` (rozdział 12.1). Hasła zapisz w Pęku kluczy:

```bash
python sebastian.py password gmail
python sebastian.py password murena
python sebastian.py password partners
```

Sprawdź połączenia i znajdź nazwy folderów wysłanych (szukaj oznaczenia `\Sent`):

```bash
python sebastian.py folders gmail
python sebastian.py folders murena
python sebastian.py folders partners
```

Wskaż foldery wysłanych, wpisując dokładne nazwy z poprzedniego polecenia:

```bash
python sebastian.py sent partners "Sent"
```

Gmail ma nazwy zależne od języka. Nie wpisuj nazwy w ciemno.

**Szybki test na 5 mailach, bez zmian na serwerze:**

```bash
python sebastian.py pilot --account murena --limit 5
python sebastian.py analyze --limit 5
cat data/panel.token
python sebastian.py serve
```

Otwórz http://127.0.0.1:8765, zaloguj się kluczem z `panel.token`, porównaj streszczenia z mailami. Zatrzymaj panel: Control + C.

> `pilot` ustala granicę „stare/nowe” maile. Nie używaj go codziennie, od tego jest poranek.

### 5.5. Panel w tle i poranek

```bash
python sebastian.py morning-setup
```

Polecenie sprawdza Ollamę, model i skrzynki, a następnie instaluje dwa zadania macOS:

- **panel**, który działa zawsze po zalogowaniu,
- **poranek**, który od następnego dnia o 06:30 pobiera nową pocztę i ją analizuje.

Szczegóły w rozdziale 7. Test od razu, bez czekania do rana: `python sebastian.py morning-run --force`.

### 5.6. Nauka — dostęp do Dysku Google (jednorazowo, ok. 15 minut)

Nauka czyta Dysk przez oficjalne API Google, tylko do odczytu. Potrzebny jest własny klucz OAuth.

1. https://console.cloud.google.com → wybierz lub utwórz projekt.
2. Menu ☰ → **Interfejsy API i usługi → Biblioteka** → „Google Drive API” → **Włącz**.
3. Menu ☰ → **Platforma uwierzytelniania Google**:
   - **Odbiorcy**: typ „Zewnętrzny”, stan publikacji zostaw na **„Testowanie”**. W „Użytkownicy testowi” dodaj adres Gmail, na którym jest Dysk.
   - **Klienty → + Utwórz klienta** → typ **Aplikacja komputerowa** → Utwórz → **Pobierz JSON** (od razu, w okienku, które się pojawi).
4. Zapisz pobrany plik jako `~/SebastianSystem/sebastian-start/data/learner/credentials.json`. Folder `data/learner` tworzy się przy pierwszym poleceniu `learn-…`. Jeśli go nie ma: `mkdir -p data/learner`.
5. Zaloguj się:

   ```bash
   python sebastian.py learn-login
   ```

   W przeglądarce: konto Google → „Zaawansowane” → „Przejdź do aplikacji” → Zezwól.

> **Tryb „Testowanie” = logowanie ważne 7 dni.** Publikacja wymagałaby strony WWW i polityki prywatności, co przy prywatnym narzędziu nie ma sensu. Dzień przed wygaśnięciem Mac pokaże powiadomienie. Wtedy wystarczy `python sebastian.py learn-login`. Gdy logowanie wygaśnie, poczta uczy się dalej, czeka tylko Dysk.

Dysk jest opcjonalny. Bez `credentials.json` nauka pracuje tylko na poczcie.

### 5.7. Nauka — ustawienia i start

```bash
python sebastian.py learn-set OWNER_NAME "Andrzej Kwiatkowski"
python sebastian.py learn-set OWNER_CONTEXT "Planer finansowy w inPartners (Kraków), szef struktury. Sprawy prywatne i rodzinne. Pisze po polsku."
python sebastian.py learn-set MODEL "qwen2.5:14b"
python sebastian.py learn-mail-test
python sebastian.py learn-start
```

- `OWNER_NAME` i `OWNER_CONTEXT` muszą opisywać osobę, **do której należą skrzynki i Dysk**. Model zbiera fakty o tej osobie.
- `MODEL` ustawiaj tylko, jeśli nauka ma używać innego modelu niż analiza poczty. Pobierz go wcześniej: `ollama pull qwen2.5:14b`.
- `learn-mail-test` sprawdza logowanie i pokazuje foldery, które nauka przeczyta. Gdy macOS zapyta o Pęk kluczy, kliknij **Zawsze pozwalaj**. Bez tego nauka w tle nie zaloguje się do skrzynek.
- `learn-start` włącza naukę w tle na stałe.

Postęp: zakładka **Nauka** w panelu albo `python sebastian.py learn-status`.

### 5.8. Open WebUI (opcjonalnie)

Rozdział 9.

### 5.9. Lista kontrolna po instalacji

- [ ] `python sebastian.py doctor` pokazuje model.
- [ ] `folders` działa dla każdego konta.
- [ ] Panel otwiera się pod http://127.0.0.1:8765 po zalogowaniu na Maca, bez ręcznego `serve`.
- [ ] `morning-run --force` kończy się stanem `ok` lub `partial` z wyjaśnionymi uwagami.
- [ ] `learn-mail-test` pokazuje foldery z liczbą wiadomości.
- [ ] `learn-status` po godzinie pokazuje przeczytane wątki.
- [ ] Zakładka Nauka: po kilku godzinach pojawiają się „Bieżące sprawy”.
- [ ] FileVault włączony (Ustawienia systemowe → Prywatność i ochrona).

---

## 6. Codzienna praca w panelu

Adres: **http://127.0.0.1:8765**. Działa tylko na tym Macu, bo 127.0.0.1 na telefonie oznacza telefon. Logowanie kluczem z `data/panel.token`. U góry przełączasz zakres: **prywatne / firmowe**.

### 6.1. Widoki

| Widok | Co pokazuje |
| --- | --- |
| **Do decyzji** (start) | Maile bez Twojej decyzji, ułożone według priorytetu. Na ekranie do 100 pozycji |
| **Nowe — do decyzji** | Tylko maile pobrane przez poranek lub `sync` (nie archiwum) |
| **Zadania do wykonania** | Sprawy, które odłożyłeś „Do zadań” |
| **Wszystkie + zakończone** | Wszystko. Nieocenione na górze. Wyszukiwanie po temacie, treści, kategorii, komentarzu |
| **Podsumowanie i postęp** | Liczby: pobrane, przeanalizowane, decyzje, odpowiedzi, przykłady do nauki, historia poranków, ważni nadawcy |
| **Pamięć bota** | Twoje notatki i preferencje, stan kopii dla Open WebUI, pobranie narzędzia |
| **Nauka** | Bieżące sprawy, Profil wiedzy, postęp nauki (poczta, Dysk, archiwum, załączniki), dziennik |
| **Nazwy i stopki** | Nazwa nadawcy, stopka, krój i kolor dla każdej skrzynki, kopia w Wysłanych |
| **Kalendarze** | Import plików ICS Twoich kalendarzy do sprawdzania konfliktów |

### 6.2. Decyzja o mailu

Szybkie przyciski na liście:

| Przycisk | Skutek |
| --- | --- |
| **Pomiń — mało ważne** | Status „Pominięte” z powodem „szybkie pominięcie”. Znika z kolejki. Można cofnąć |
| **Tak, przypisz: kategoria** | Zatwierdza kategorię zaproponowaną przez AI. Znika z kolejki decyzji |
| **Zmień kategorię** | Wybór lub dodanie kategorii i podkategorii |
| **Do zadań** | Trafia do „Zadania do wykonania” z nazwą zadania |
| **Zadanie wykonane** | Status „Zrobione” |
| **Zmień priorytet** | Ręczny wybór jednej z 4 grup macierzy (ma pierwszeństwo przed AI) |

Pełna decyzja w karcie maila to status (Otwarte / Zrobione / Pomiń) plus kategoria, podkategoria, komentarz, powód pominięcia (obowiązkowy przy Pomiń), priorytet i przełącznik „wykorzystaj w przyszłych analizach”.

Ważne zasady:

- Status w panelu **nie zmienia niczego na serwerze pocztowym**.
- Każda szybka zmiana ma przycisk cofnięcia.
- Domyślne kategorie: InPartners → Klienci, Zespół, Prawo, Marketing, Asystenci, Partnerzy; Nieruchomość Rybnik; Rodzina; Agnieszka; Wyjazdy; Dom; Finanse osobiste; Zdrowie; Rozwój i nauka; Inne. Katalogi prywatny i firmowy są osobne.

### 6.3. Priorytet (macierz Eisenhowera)

1. Pilne i ważne
2. Pilne i mniej ważne
3. Niepilne i ważne
4. Niepilne i mniej ważne

**Pilne** oznacza termin potwierdzony cytatem w ciągu 0–3 dni. **Ważne** wynika z oceny AI popartej cytatem albo z rodzaju sprawy. Ręczny priorytet zawsze wygrywa.

Ogłoszenia Partners od wskazanych osób (Dawid Kozioł, Tomasz Pustówka) nigdy nie trafiają do „mało ważnych”. Dodatkowe wyjątki ustawisz w Podsumowaniu → „Ważni nadawcy”.

### 6.4. Jak Sebastian uczy się z decyzji (pamięć przykładów)

Przy każdej nowej analizie Sebastian dobiera **do 4 podobnych przykładów** spośród 200 ostatnio ocenionych maili z tego samego konta i zakresu (ten sam nadawca albo wspólne słowa). Dokłada też **do 12 aktywnych notatek** z Pamięci bota. Wyłączenie „wykorzystaj w analizach” w karcie maila wyklucza go z przykładów. Zmiana decyzji nie przelicza starych analiz.

### 6.5. Odpowiedź na maila

Karta maila → **Odpowiedz na maila** → treść → **Przejdź do podglądu** → zaznacz potwierdzenie → **Wyślij odpowiedź**.

- Wysyłka przez SMTP STARTTLS (port 587) hasłem z Pęku kluczy.
- Statusy wysyłki: Szkic, Serwer przyjął wiadomość, Nie wysłano, Wynik nieznany, Wysyłka częściowa. Przy „Wynik nieznany” najpierw sprawdź webmail, a dopiero potem wysyłaj ponownie.
- Brak CC/BCC i „odpowiedz wszystkim”. Oryginalne załączniki nie są odsyłane.
- Lokalna kopia EML jest zawsze zapisywana.

### 6.6. Kalendarz

Karta maila → **Utwórz wydarzenie** (lub propozycja AI) → popraw dane → **Zapisz i sprawdź konflikty** → **Pobierz ICS** → otwórz plik w swoim kalendarzu.

- Konflikty liczone są z zaimportowanych plików ICS (zakładka Kalendarze) i z wydarzeń wyeksportowanych przez Sebastiana. To nie jest synchronizacja na żywo.
- Dojazd: link do Google Maps, Ty wpisujesz czasy, a Sebastian dodaje bloki dojazdu i powrotu.

### 6.7. Notatki, WhatsApp, narady

Tekst z pliku (np. eksport czatu WhatsApp bez multimediów, transkrypcja spotkania, notatka):

```bash
python sebastian.py import-text imports/notatka.txt --scope private --source note
```

`--source`: `note`, `whatsapp` albo `meeting`. `--scope`: `private` albo `work`. Takie teksty widzi panel i **czyta je też nauka**.

### 6.8. Rytm pracy właściciela

- **Codziennie (5 min):** panel → Do decyzji → maks. 3 rzeczy do działania. Zakładka Nauka → Bieżące sprawy.
- **Raz w tygodniu:** `python sebastian.py learn-login`, gdy Mac pokaże powiadomienie.
- **Raz w miesiącu:** kopia zapasowa (rozdział 14.1) i rzut oka na `learn-status` (błędy, archiwum).

---

## 7. Praca w tle — harmonogramy macOS

Sebastian używa **LaunchAgents** (`~/Library/LaunchAgents/`). Działają po zalogowaniu na konto użytkownika, bez uprawnień administratora.

| Zadanie (Label) | Co uruchamia | Kiedy | Instaluje / usuwa |
| --- | --- | --- | --- |
| `pl.sebastian.panel` | `sebastian.py serve` | zawsze, restart po awarii | `morning-setup` / `schedule remove` |
| `pl.sebastian.jobs` | `sebastian.py morning-run` | 06:30 + co 15 minut | `morning-setup` / `schedule remove` |
| `pl.sebastian.learner` | `caffeinate -is … sebastian.py learn-run` | zawsze, restart po awarii | `learn-start` / `learn-stop` |

### Poranek (`morning-run`)

- Pobiera nowe maile z gotowych kont (do 200 na folder) i analizuje do 200 nowych.
- Do 4 prób dziennie po 06:30. Po pełnym sukcesie nie ponawia.
- Przy wywołaniach co 15 minut tylko odświeża raport i kopię dla Open WebUI.
- Historia przebiegów jest w „Podsumowanie i postęp”, a konfiguracja w `data/automation.json`.

### Nauka (`learn-run`)

- Pracuje bez przerwy.
- Gdy trwa poranek, czeka, żeby nie zajmować Ollamy.
- Nie usypia Maca (`caffeinate`).

### Warunki

Mac musi być włączony, zalogowany i nieuśpiony, z działającą Ollamą, Internetem i odblokowanym Pękiem kluczy. Docker jest potrzebny tylko do kopii w Open WebUI. Po restarcie Maca wystarczy się zalogować, a zadania ruszą same. Ollama powinna być w „Rzeczach otwieranych podczas logowania”.

### Sprawdzenie i ręczne sterowanie

```bash
launchctl print gui/$(id -u)/pl.sebastian.panel | head -5
launchctl print gui/$(id -u)/pl.sebastian.learner | head -5
launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel    # przeładuj panel (np. po aktualizacji kodu)
tail -n 30 data/logs/jobs.log
tail -f data/logs/learner.log
```

---

## 8. Moduł Nauka — szczegóły

### 8.1. Źródła

| Źródło | Jak czytane | Gdzie trafia |
| --- | --- | --- |
| Dysk Google | API Google, tylko odczyt. Plik pobierany na chwilę do `data/learner/tmp`, od razu usuwany | dokumenty w kolejce nauki |
| Poczta Sebastiana | odczyt z `data/sebastian.sqlite3`: maile, Twoje decyzje i komentarze z panelu, notatki, WhatsApp, narady | wątki |
| Archiwum skrzynek | IMAP, tylko odczyt, wszystkie foldery poza Koszem, Spamem i Szkicami. W Gmailu wyłącznie folder „Wszystkie” | `history_mails` w bazie nauki → wątki |
| Załączniki (2.1) | IMAP, pobierane przy czytaniu wątku. Ten sam plik czytany raz | tekst dołączony do wątku |

Archiwum dociąga osobny wątek w tle: porcjami po `MAIL_HISTORY_BATCH` na konto, od najnowszych. Gdy wszystko pobrane, co 6 godzin sprawdza nowe wiadomości i foldery.

### 8.2. Dokumenty Dysku

Obsługiwane: Dokumenty / Arkusze / Prezentacje Google, PDF (skany przez OCR), DOCX, PPTX, XLSX, TXT, MD, CSV, HTML, RTF/DOC/ODT (przez `textutil`), obrazy (OCR), opcjonalnie audio i wideo (transkrypcja `mlx-whisper`, domyślnie wyłączona).

Kolejność czytania: teksty → PDF i pliki biurowe → reszta → obrazy → nagrania. W każdej grupie od najnowszych. Zmieniony plik jest czytany ponownie przy kolejnym skanie (co 24 h).

### 8.3. Wątki poczty

- Maile są łączone w wątki po nagłówkach `References` / `In-Reply-To`. Ten sam mail z bazy Sebastiana i z archiwum (to samo `Message-ID`) liczy się raz.
- **Tekst wątku dla modelu:** wiadomości od najstarszej, z oznaczeniem „WYSŁANE PRZEZE MNIE” dla własnych, z decyzją i komentarzem z panelu, z wyciętą cytowaną korespondencją („W dniu … napisał:”). Załączniki są dołączone jako „📎 Załącznik: nazwa”. Przy bardzo długich wątkach zostają najnowsze wiadomości (limit `MAIL_THREAD_MAX_CHARS`).
- **Pomijane:** newslettery i maile z linkiem wypisania, nadawcy typu no-reply i powiadomienia, kategoria `newsletter`/`podejrzane` z analizy, maile oznaczone w panelu „Pomiń”. **Zawsze czytane:** Twoje wysłane oraz sprawy, przy których podjąłeś decyzję „Otwarte/Zrobione”.
- **Kolejność:** wątki z ostatnich `MAIL_RECENT_DAYS` (60) dni najpierw, potem starsze od najnowszych.
- **Nowa wiadomość w przeczytanym wątku** albo zmiana Twojej decyzji powoduje ponowne przeczytanie całego wątku.
- Ścieżka wątku (widoczna w panelu i w `teksty/`): `Poczta prywatna|firmowa/RRRR-MM/Temat` albo `Notatki i rozmowy/…`.

### 8.4. Załączniki

- Typy: PDF, DOCX, DOC, RTF, ODT, XLSX, PPTX, TXT, CSV, MD, HTML oraz obrazy JPG/PNG/TIFF/WEBP (OCR).
- Pomijane: obrazki w treści i ze stopek (np. `image001.png`, mniejsze niż `ATTACH_MIN_IMAGE_KB`), archiwa ZIP, maile większe niż `ATTACH_MAX_MB`, wiadomości przeniesione na serwerze.
- Pamięć podręczna: tekst każdego pliku jest zapisywany pod skrótem SHA-1 (tabela `attachments`), więc ta sama umowa w 5 mailach jest czytana raz.
- Archiwum z wersji 2.0: nauka sprawdza w tle sam nagłówek `Content-Type`, żeby wiedzieć, które maile mają załączniki. Takie wątki wracają do kolejki.

### 8.5. Fakty i kategorie

Model dostaje porcje tekstu (`CHUNK_CHARS`, domyślnie 6000 znaków) i zwraca fakty w JSON. Każdy fakt to jedno zdanie, z datą przy faktach z poczty. Kategorie:

Tożsamość i rola · Praca, firmy i projekty · Klienci i obszary doradztwa (ogólnie) · Ludzie i relacje · **Bieżące sprawy i zobowiązania** · Cele, plany i decyzje · Styl pracy i preferencje · **Styl komunikacji** (tylko z wysłanych maili) · Umiejętności, wiedza i narzędzia · Wartości, przekonania i przemyślenia · Historia i ważne wydarzenia · Zainteresowania i życie prywatne

Model ma zakaz zapisywania danych wrażliwych innych osób: PESEL, numery dokumentów i kont, hasła, adresy, kwoty majątku, zdrowie.

### 8.6. Wyniki

| Plik (`data/learner/wyniki/`) | Jak powstaje | Odświeżanie |
| --- | --- | --- |
| `Biezace_sprawy.md` | Od nowa z faktów z ostatnich `CURRENT_DAYS` (30) dni i otwartych zadań z panelu: sprawa, stan, następny krok, termin, z kim | co ~3 h, gdy są nowe fakty, i co najmniej raz na dobę |
| `Profil_wiedzy.md` | Na górze Bieżące sprawy, niżej sekcje kategorii. Każda sekcja jest scalana z nowymi faktami („notatka + nowości → nowa notatka”, maks. `CATEGORY_SUMMARY_WORDS` słów) | co `CONSOLIDATE_EVERY_HOURS` (6) h |
| `archiwum/` | Poprzednie wersje profilu | ostatnie 60 wersji |

Kategoria „Bieżące sprawy i zobowiązania” **nie** trafia do trwałych sekcji profilu, bo żyje w przeglądzie spraw.

### 8.7. Pełne teksty

Każdy przeczytany dokument i wątek (z załącznikami) zapisuje się jako Markdown w `data/learner/teksty/`, w strukturze folderów jak na Dysku lub w poczcie. Na górze pliku jest nazwa, ścieżka, data i źródło: link do Dysku albo do karty maila w panelu. To materiał dla bazy RAG i przyszłych „akt spraw i osób”.

### 8.8. Ile to trwa

Jedna porcja tekstu to ok. 15–40 s (model 14B na M1 Max). Dokument lub wątek zajmuje od kilkudziesięciu sekund do kilku minut, a duże wątki z załącznikami dłużej. Pełne archiwum kilku tysięcy wątków to od kilku dni do około dwóch tygodni. Bieżące sprawy pojawiają się w pierwszych godzinach.

---

## 9. Połączenie z Open WebUI

Są trzy niezależne mechanizmy. Można używać dowolnych.

| # | Mechanizm | Dane | Odświeżanie | Konfiguracja |
| --- | --- | --- | --- | --- |
| A | Narzędzie **„Sebastian — moje sprawy”** (`openwebui_tool.py`) | raport spraw z panelu (`bridge.json`) | poranek / co 15 min / `bridge` | Docker + Tools |
| B | Narzędzie **„Sebastian — pamięć”** (`openwebui_memory_tool.py`) | notatki i decyzje (`knowledge-private.json`, `knowledge-work.json`), wyszukiwanie BM25 | jak wyżej | Docker + Tools |
| C | **Bazy wiedzy (Knowledge, RAG)** zasilane przez naukę | Profil i Bieżące sprawy, fakty, pełne teksty | co 24 h / `learn-rag sync` | klucz API Open WebUI |

### 9.1. Kopiowanie do Dockera (A i B)

```bash
docker ps --format "table {{.Names}}\t{{.Image}}"
python sebastian.py webui "open-webui"      # dokładna nazwa kontenera z kolumny NAMES
python sebastian.py bridge
```

Pliki trafiają do `/app/backend/data/` w kontenerze: `sebastian-bridge.json`, `sebastian-knowledge-private.json`, `sebastian-knowledge-work.json`.

### 9.2. Dodanie narzędzi (A i B)

1. `pbcopy < openwebui_tool.py` (albo `openwebui_memory_tool.py`).
2. Open WebUI → **Workspace → Tools → +** → wklej kod → zapisz (np. „Sebastian — pamięć prywatna”).
3. **Valves:** `ALLOWED_EMAIL` to e-mail Twojego konta w Open WebUI. `ALLOWED_SCOPE` to `private` albo `work`, czyli osobne narzędzie dla każdego zakresu.
4. W czacie włącz narzędzie (Function Calling: Native) albo przypisz je do modelu: Workspace → Models → edycja → Tools.
5. Test: „Użyj narzędzia moje_preferencje i podaj źródło oraz datę pamięci”.

Funkcje narzędzi: `moje_sprawy(query, message_id)`, `szukaj_pamieci(query, source_id)`, `moje_preferencje()`.

> Narzędzia firmowego nie podłączaj do modelu współdzielonego z rodziną.

### 9.3. Bazy wiedzy z nauki (C)

1. **Model wyszukiwania po polsku:** `ollama pull bge-m3`. Open WebUI → Panel administratora → Ustawienia → Dokumenty → silnik osadzeń **Ollama**, model **bge-m3**. Ustaw to **przed** pierwszą wysyłką, bo zmiana później wymaga przeliczenia całej bazy.
2. Workspace → **Knowledge → +**: utwórz trzy bazy, np. „Sebastian — profil”, „Sebastian — fakty”, „Sebastian — teksty”. ID bazy to końcówka adresu strony bazy.
3. Klucz API: konto → Ustawienia → Konto → Klucze API.
4. Wpisz ustawienia:

   ```bash
   python sebastian.py learn-set OPENWEBUI_URL "http://localhost:3000"
   python sebastian.py learn-set OPENWEBUI_API_KEY "sk-…"
   python sebastian.py learn-set OPENWEBUI_KNOWLEDGE_ID "<ID bazy profil>"
   python sebastian.py learn-set RAG_FACTS_KNOWLEDGE_ID "<ID bazy fakty>"
   python sebastian.py learn-set RAG_TEXTS_KNOWLEDGE_ID "<ID bazy teksty>"
   python sebastian.py learn-start
   ```

5. Pierwsza wysyłka od razu: `python sebastian.py learn-rag sync`. Na próbę: `--limit 20`.
6. W Open WebUI utwórz model (Workspace → Models → +) z tymi bazami w polu **Knowledge** albo wybieraj bazę przez `#` w czacie.

Program wysyła tylko nowe i zmienione pliki (do `RAG_MAX_UPLOADS_PER_RUN` na rundę). Zakresy wysyłane do RAG wybierasz przez `RAG_SCOPES` (np. bez poczty firmowej: `"drive, private"`).

---

## 10. Mapa plików i danych

### 10.1. Repozytorium (kod — to, co jest na GitHubie)

```
sebastian-start/
├── sebastian.py              rdzeń i wszystkie polecenia
├── feedback.py               kategorie i przykłady decyzji
├── progress.py               priorytety, szybkie Pomiń, podsumowanie
├── quick_actions.py          szybkie przyciski z cofnięciem
├── knowledge.py              pamięć bota, eksport dla Open WebUI
├── mail_actions.py           odpowiedzi SMTP, załączniki na żądanie
├── calendar_actions.py       ICS, konflikty, dojazd
├── dashboard_actions.py      trasy panelu (odpowiedzi, stopki, kalendarze)
├── morning.py                poranek i harmonogram launchd
├── learner.py                nauka: rdzeń, Dysk, fakty, wyniki, RAG
├── learner_mail.py           nauka: poczta, archiwum, wątki
├── learner_attach.py         nauka: załączniki
├── learner_web.py            zakładka Nauka
├── openwebui_tool.py         narzędzie Open WebUI „moje sprawy”
├── openwebui_memory_tool.py  narzędzie Open WebUI „pamięć”
├── rollback.py               PRZESTARZAŁE (1.3) — nie używać, patrz 15.6
├── templates/  static/       panel (HTML, JS)
├── test_sebastian.py  test_learner.py
├── requirements*.txt  install.command  start.command
├── README.md  DOKUMENTACJA.md  ZACZNIJ_TUTAJ.txt
└── docs/
    ├── TESTY.md              co i jak przetestowano
    ├── aktualizacje/         instrukcje przejścia między wersjami (1.1 … 2.1)
    └── archiwum/             podręcznik PDF wersji 1.0
```

### 10.2. Dane (tylko na Macu — nigdy na GitHub)

```
sebastian-start/
├── .venv/                          środowisko Pythona (odtwarzalne: install.command)
├── backups/                        kopie z poleceń backup i aktualizatorów
└── data/
    ├── config.json                 konta, model, Docker (rozdział 12.1)
    ├── panel.token                 klucz logowania do panelu  🔒
    ├── session.key                 klucz sesji panelu          🔒
    ├── sebastian.sqlite3 (+-wal, -shm)   baza panelu (maile!)  🔒
    ├── automation.json             plan poranka
    ├── knowledge-sync.json         stan kopiowania do Open WebUI
    ├── job.lock  knowledge-sync.lock     blokady zadań
    ├── exports/                    bridge.json, raport-*.md, daily/, knowledge-*.json  🔒
    ├── logs/                       panel.*, jobs.*, learner.log, learner.out/.err
    └── learner/
        ├── learner.json            ustawienia nauki (zawiera klucz API Open WebUI)  🔒
        ├── credentials.json        klucz OAuth Google           🔒
        ├── token.json              logowanie do Dysku           🔒
        ├── stan.sqlite3            baza nauki (archiwum maili!) 🔒
        ├── wyniki/                 Biezace_sprawy.md, Profil_wiedzy.md, archiwum/
        ├── teksty/                 pełne teksty dokumentów i wątków  🔒
        ├── rag/fakty/              fakty pogrupowane pod RAG
        └── tmp/                    pliki chwilowe (zawsze puste po pracy)
```

🔒 oznacza dane wrażliwe: maile, dane klientów, klucze.

**Pęk kluczy macOS:** wpisy usługi `SebastianMail` o nazwach kont (`gmail`, `murena`, `partners`). Podgląd: aplikacja „Pęk kluczy” → wyszukaj „SebastianMail”.

### 10.3. Najważniejsze tabele

**`data/sebastian.sqlite3`**

| Tabela | Zawartość |
| --- | --- |
| `messages` | Maile i importy: konto, folder, UID, nagłówki, treść (do 12 000 znaków), analiza AI (JSON), decyzja (`status`, `topic`, `topic_sub`, `comment`, `skip_reason`, `priority_override`, `is_task`, `task_title`, `decided_at`, `learn`), `arrival` = `new`/`archive` |
| `cursors` | Granica nowych maili na folder (UIDVALIDITY + najwyższy UID) |
| `events` | Dziennik decyzji i zmian (audyt) |
| `undo_decisions` | Dane do cofania szybkich decyzji |
| `topics` | Katalog kategorii (osobno prywatny/firmowy) |
| `rules` | Stare reguły nadawców (z 1.0) |
| `goals` | „Mój większy plan” |
| `important_senders` | Wyjątki ważnych nadawców |
| `knowledge_notes`, `knowledge_meta` | Notatki i preferencje Pamięci bota |
| `identities` | Nazwy i stopki skrzynek |
| `outgoing` | Odpowiedzi: szkic, podgląd, stan wysyłki, EML |
| `calendar_sources`, `calendar_drafts` | Zaimportowane kalendarze, szkice wydarzeń |
| `runs`, `morning_runs`, `morning_items` | Historia pobierania i poranków |

**`data/learner/stan.sqlite3`**

| Tabela | Zawartość |
| --- | --- |
| `files` | Kolejka nauki: dokumenty Dysku (`id` = ID pliku Google) i wątki (`mail:…`, `import:…`), `status` (`new`/`done`/`skip`/`error`), `priority`, `scope` (`drive`/`private`/`work`), `sig` (podpis zawartości), `text_path` |
| `facts` | Fakty: źródło, kategoria, treść |
| `summaries` | Sekcje profilu (`__biezace__` = Bieżące sprawy) |
| `history_mails`, `history_folders` | Archiwum skrzynek i postęp per folder |
| `mail_members` | Które maile należą do którego wątku |
| `attachments`, `message_attachments`, `att_done` | Teksty załączników (pod SHA-1), powiązania, stan sprawdzenia |
| `rag_sync` | Co i kiedy wysłano do Open WebUI |
| `meta` | Znaczniki czasu (ostatni skan, profil, logowanie Google…) |

---

## 11. Wszystkie polecenia

Każde polecenie uruchamiaj w folderze `sebastian-start` z aktywnym `.venv`: `python sebastian.py POLECENIE`.

### 11.1. Sebastian — konfiguracja

| Polecenie | Co robi |
| --- | --- |
| `init` | Tworzy `data/`, `config.json`, brakujące klucze panelu i bazę. Bezpieczne do ponownego użycia, niczego nie nadpisuje |
| `doctor` | Wersja Pythona, modele w Ollamie, wybrany model, ścieżka danych |
| `model NAZWA` | Model do analizy poczty |
| `password KONTO` | Zapis hasła do Pęku kluczy (`gmail` / `murena` / `partners`) |
| `folders KONTO` | Lista folderów IMAP (nic nie pobiera) |
| `sent KONTO "FOLDER"` | Wskazuje folder wysłanych i dodaje go do pobierania |
| `webui KONTENER` | Nazwa kontenera Docker z Open WebUI |
| `morning-setup` (= `schedule install`) | Sprawdza i włącza panel w tle i poranek 06:30 |
| `schedule remove` | Wyłącza panel w tle i poranek |

### 11.2. Sebastian — poczta i analiza

| Polecenie | Co robi |
| --- | --- |
| `pilot --account K --limit N` | Próbka (70% najnowszych, 30% starszych) **i ustalenie granicy nowych maili**. Tylko przy konfiguracji |
| `sync --account K --limit N` | Nowe maile od granicy |
| `backfill --account K --limit N` | Kolejna porcja starszych maili do panelu (archiwum) |
| `analyze --limit N [--retry]` | Analiza AI nieprzeanalizowanych (`--retry` ponawia nieudane) |
| `run --limit N` | `sync` + `analyze` (dawny tryb, zastąpiony porankiem) |
| `morning-run [--force]` | Poranek teraz (`--force` niezależnie od godziny) |
| `import-text PLIK --scope S --source Z` | Import notatki, WhatsApp lub narady |
| `report` / `bridge` | Raporty w `data/exports` / kopia do Open WebUI |
| `serve` | Panel ręcznie (gdy harmonogram wyłączony) |
| `demo` | 3 fikcyjne maile (tylko z osobnym `SEBASTIAN_DATA`) |
| `backup` | Kopia bazy panelu i `config.json` do `backups/` |

`--account`: `all` (domyślnie), `gmail`, `murena`, `partners`. `--limit`: 1–1000 na folder.

### 11.3. Nauka

| Polecenie | Co robi |
| --- | --- |
| `learn-start` / `learn-stop` | Włącza / wyłącza naukę w tle. Po zmianie ustawień: `learn-start` |
| `learn-status` | Postęp: Dysk, wątki, archiwum per folder, załączniki, fakty, daty wyników |
| `learn-settings` | Wszystkie ustawienia (klucz API ukryty) |
| `learn-set KLUCZ WARTOŚĆ` | Zmiana ustawienia (`tak`/`nie`, liczby, listy po przecinku, JSON dla słowników) |
| `learn-login` | Logowanie do Dysku Google (co 7 dni) |
| `learn-mail-test [--account K]` | Test logowania i lista folderów do przeczytania |
| `learn-scan` | Odświeżenie listy dokumentów i wątków od razu |
| `learn-history --limit N` | Ręczne pobranie porcji archiwum |
| `learn-test ID` | Przeczytaj jedną pozycję i pokaż fakty (ID z zakładki Nauka albo z adresu pliku Google) |
| `learn-consolidate` | Odśwież Bieżące sprawy i Profil teraz |
| `learn-rag export` / `learn-rag sync [--limit N]` | Pliki faktów dla RAG / wysyłka do Open WebUI |
| `learn-retry` | Pozycje z błędem wracają do kolejki |
| `learn-import ŚCIEŻKA [--force]` | Przeniesienie stanu dawnego Drive Learnera (`~/drive-learner`) |
| `learn-run` | Pętla nauki na pierwszym planie (normalnie uruchamia ją launchd) |

---

## 12. Wszystkie ustawienia

### 12.1. `data/config.json` (Sebastian)

Edytuj poleceniami (`model`, `sent`, `webui`). Ręcznie: zatrzymaj panel i poranek (`schedule remove`), zrób kopię pliku, edytuj w edytorze tekstu **bez inteligentnych cudzysłowów**, potem `morning-setup`.

| Pole | Znaczenie |
| --- | --- |
| `model` | Model Ollamy do analizy poczty |
| `ollama` | Musi być `http://127.0.0.1:11434` (wymóg lokalności) |
| `webui_container`, `docker_path` | Kontener Open WebUI i ścieżka programu `docker` |
| `max_chars` | Maks. długość treści maila zapisywanej w panelu (12 000) |
| `accounts[]` | Konta: `id` (`gmail`/`murena`/`partners`), `scope` (`private`/`work`), `user` (adres), `host` (serwer IMAP), `folders` (lista), `sent_folder` |

Serwery: Gmail `imap.gmail.com`, Murena `mail.ecloud.global`, Partners `webmail.inpartners.pl`. IMAP 993 (TLS), SMTP 587 (STARTTLS).

### 12.2. `data/learner/learner.json` (Nauka)

Zmieniaj poleceniem `python sebastian.py learn-set KLUCZ WARTOŚĆ`, potem `learn-start`. Brakujące klucze mają wartości domyślne.

**Właściciel i model**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `OWNER_NAME` | `Andrzej Kwiatkowski` | Osoba, o której zbierana jest wiedza |
| `OWNER_CONTEXT` | krótki opis | Kontekst dla modelu (nie jest powtarzany jako fakt) |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Adres Ollamy |
| `MODEL` | puste = model Sebastiana | Model nauki |
| `NUM_CTX` | `8192` | Okno kontekstu na zapytanie |
| `KEEP_ALIVE` | `30m` | Jak długo model zostaje w pamięci |
| `PAUSE_BETWEEN_CALLS_S` | `1.0` | Przerwa między zapytaniami |

**Dysk Google**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `DRIVE_ENABLED` | `tak` | Czy czytać Dysk |
| `ONLY_MY_FILES` | `nie` | Tylko pliki, których jesteś właścicielem |
| `EXCLUDE_PATHS` | puste | Fragmenty ścieżek do pominięcia (dotyczy też ścieżek wątków poczty, np. `Poczta firmowa`) |
| `INCLUDE_ONLY_PATHS` | puste | Czytaj wyłącznie te foldery Dysku |
| `MAX_FILE_MB` | `60` | Większe pliki pomijane |
| `CHUNK_CHARS` / `CHUNK_OVERLAP` | `6000` / `400` | Wielkość porcji tekstu dla modelu |
| `MAX_CHUNKS_PER_FILE` | `25` | Maks. porcji na dokument lub wątek |
| `OCR_IMAGES` | `tak` | OCR obrazów i skanów |
| `OCR_LANG` | `pol+eng` | Języki OCR |
| `OCR_MIN_IMAGE_KB` | `40` | Mniejsze obrazy z Dysku pomijane |
| `OCR_PDF_MAX_PAGES` | `15` | OCR pierwszych N stron skanu PDF |
| `TRANSCRIBE_AUDIO` / `TRANSCRIBE_VIDEO` | `nie` | Transkrypcja nagrań (wymaga `pip install mlx-whisper` i `brew install ffmpeg`) |
| `TRANSCRIBE_MAX_MB` | `400` | Limit nagrania |
| `WHISPER_MODEL` | `mlx-community/whisper-large-v3-turbo` | Model transkrypcji |
| `SKIP_MUSIC` | `tak` | Pomijaj muzykę z folderów „muzyka/music” |
| `RESCAN_EVERY_HOURS` | `24` | Jak często sprawdzać zmiany na Dysku |

**Poczta**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `MAIL_ENABLED` | `tak` | Nauka z poczty |
| `MAIL_HISTORY` | `tak` | Dociąganie archiwum skrzynek |
| `MAIL_HISTORY_SINCE` | puste | Archiwum od daty (`RRRR-MM-DD`) |
| `MAIL_HISTORY_BATCH` | `150` | Maili na konto w jednej rundzie |
| `MAIL_ACCOUNTS` | puste = wszystkie | Konta do nauki, np. `gmail, partners` |
| `MAIL_FOLDERS` | `{}` = automatycznie | Foldery na konto, JSON: `{"partners": ["INBOX","Sent"]}` |
| `MAIL_EXTRA_OWN_ADDRESSES` | puste | Twoje dodatkowe adresy (aliasy), żeby rozpoznać wysłane |
| `MAIL_SKIP_SENDERS` | puste | Dodatkowe wzorce nadawców do pominięcia |
| `MAIL_RECENT_DAYS` | `60` | Wątki z tego okresu na początku kolejki |
| `MAIL_MAX_CHARS` | `15000` | Maks. treści jednego maila z archiwum |
| `MAIL_THREAD_MAX_CHARS` | `90000` | Maks. tekstu wątku (z załącznikami) dla modelu |
| `MAIL_SCAN_MINUTES` | `15` | Co ile minut odświeżać listę wątków |

**Załączniki**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `ATTACHMENTS_ENABLED` | `tak` | Czytanie załączników |
| `ATTACHMENTS_SCOPES` | `private, work` | Z których zakresów |
| `ATTACHMENTS_SINCE` | puste | Tylko z maili od daty |
| `ATTACH_MAX_MB` | `25` | Maks. wielkość maila z załącznikami |
| `ATTACH_MAX_CHARS` | `20000` | Ile tekstu jednego załącznika trafia do wątku |
| `ATTACH_MIN_IMAGE_KB` | `60` | Mniejsze obrazki pomijane (logo, stopki) |

**Wyniki**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `CATEGORY_SUMMARY_WORDS` | `700` | Maks. długość sekcji profilu |
| `CONSOLIDATE_EVERY_HOURS` | `6` | Odświeżanie profilu |
| `CURRENT_DAYS` | `30` | Bieżące sprawy z ilu dni |
| `CURRENT_WORDS` | `900` | Maks. długość Bieżących spraw |
| `CURRENT_EVERY_HOURS` | `3` | Odświeżanie Bieżących spraw przy nowych faktach |
| `CURRENT_MAX_CHARS` | `14000` | Ile faktów (znaków) trafia do przeglądu |
| `IDLE_SLEEP_MINUTES` | `15` | Przerwa, gdy nie ma nic do czytania |

**Pełne teksty i Open WebUI**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `SAVE_TEXT` | `tak` | Zapis pełnych tekstów w `teksty/` |
| `MAX_TEXT_MB` | `3` | Limit jednego tekstu |
| `OPENWEBUI_URL` | `http://localhost:3000` | Adres Open WebUI |
| `OPENWEBUI_API_KEY` | puste | Klucz API |
| `OPENWEBUI_KNOWLEDGE_ID` | puste | Baza na Profil i Bieżące sprawy |
| `RAG_FACTS_KNOWLEDGE_ID` | puste | Baza na fakty |
| `RAG_TEXTS_KNOWLEDGE_ID` | puste | Baza na pełne teksty |
| `RAG_SCOPES` | `drive, private, work` | Co wysyłać do RAG |
| `RAG_SYNC_EVERY_HOURS` | `24` | Automatyczna wysyłka |
| `RAG_MAX_UPLOADS_PER_RUN` | `300` | Limit plików na rundę |

---

## 13. Bezpieczeństwo i prywatność

### 13.1. Czego nigdy nie publikować

Folderu `data/` (w całości), `backups/`, `demo-data/`, `.venv/`, plików `*.sqlite3`, `panel.token`, `session.key`, `credentials.json`, `token.json`, `learner.json`. Wszystkie są w `.gitignore`.

**Przed każdym `git push`:**

```bash
git status
```

Na liście nie może być niczego z powyższych. Jeśli jest, **zatrzymaj się**.

### 13.2. Jeśli dane wyciekną (np. publiczne repozytorium)

Tak się zdarzyło 15.10.2026: repozytorium z folderem `data/` było publiczne. Procedura:

1. Repozytorium natychmiast zmień na **prywatne** (GitHub → Settings → Danger Zone → Change visibility).
2. **Nowe klucze panelu:** `rm data/panel.token data/session.key && python sebastian.py init && launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel`.
3. Dane zostają w historii commitów. Usuń stare repozytorium i wypchnij nowe, czyste (bez historii): `rm -rf .git && git init -b main && git add . && git status` (sprawdź!) `&& git commit -m "…" && git push`.
4. Jeśli wyciekł klucz API Open WebUI albo `credentials.json`, unieważnij je i utwórz nowe (Open WebUI → Klucze API; Google Cloud → Klienty → usuń klienta).
5. Jeśli w mailach były dane klientów, poinformuj osobę odpowiedzialną za ochronę danych w firmie. Ocena, czy zgłosić naruszenie, należy do niej.

### 13.3. Zasady na co dzień

- **FileVault** włączony, bo baza i teksty są zwykłymi plikami.
- Panel słucha tylko na `127.0.0.1`, czyli nie jest dostępny z sieci. Ma klucz logowania, ochronę CSRF i sprawdzanie hosta.
- Open WebUI: kopie w kontenerze może czytać administrator kontenera. Narzędzia sprawdzają e-mail użytkownika i zakres. Używaj **lokalnych** modeli i lokalnego silnika osadzeń (`bge-m3`).
- Zakres firmowy (`work`) zawiera dane klientów inPartners. Nie podłączaj go do modeli współdzielonych z innymi osobami.
- Model ma zakaz zapisywania w faktach danych wrażliwych innych osób. Pełne teksty w `teksty/` zawierają jednak całe dokumenty.
- Logi nie zawierają treści maili ani haseł. Przy prośbie o pomoc nie wysyłaj bazy, `panel.token`, `learner.json` ani maili klientów.

---

## 14. Kopie zapasowe, przenoszenie, aktualizacje, rozwiązywanie problemów

### 14.1. Kopia zapasowa

```bash
python sebastian.py backup                                         # baza panelu + config.json
python sebastian.py learn-stop
cp -R data ~/Kopia-Sebastian-$(date +%Y%m%d)                       # pełne dane (także nauka)
python sebastian.py learn-start
```

Przechowuj kopię na zaszyfrowanym dysku zewnętrznym. Kopia **nie zawiera haseł**, bo są w Pęku kluczy.

### 14.2. Przeniesienie na nowy Mac

1. Na nowym Macu: rozdziały 5.1–5.2 (kod i biblioteki).
2. Skopiuj cały folder `data/` ze starego Maca w to samo miejsce (`learn-stop` i `schedule remove` na starym Macu przed kopiowaniem).
3. Hasła od nowa: `python sebastian.py password …` dla każdego konta.
4. `python sebastian.py morning-setup`, `python sebastian.py learn-mail-test`, `python sebastian.py learn-login`, `python sebastian.py learn-start`.
5. Panel będzie miał ten sam klucz (`panel.token` jest w `data/`).

### 14.3. Aktualizacje

Aktualizacje przychodzą jako plik `Sebastian_aktualizacja_X_Y.py` albo paczka ZIP z instrukcją w `docs/aktualizacje/`. Zasady:

- Uruchamiaj w folderze `sebastian-start` z aktywnym `.venv`.
- Aktualizator sprawdza wersję, robi kopię w `backups/aktualizacja-X.Y-…`, podmienia pliki, testuje uruchomienie i w razie błędu sam przywraca poprzednią wersję. Komunikat **STOP** oznacza: nic nie zmieniono albo przywrócono kopię. Przeczytaj go i nie kontynuuj na ślepo.
- Po aktualizacji: odśwież panel (Command + R), sprawdź wersję w nagłówku, potem `git add . && git commit -m "Sebastian X.Y" && git push`.

### 14.4. Rozwiązywanie problemów

| Objaw | Przyczyna / działanie |
| --- | --- |
| `No module named …` | Brak `source .venv/bin/activate` albo bibliotek: `bash install.command` |
| `Connection refused` / Ollama nie odpowiada | Uruchom Ollamę. `python sebastian.py doctor` |
| `Model not found` / 404 z Ollamy | Nazwa modelu musi być dokładnie jak w `ollama list` (`model …` albo `learn-set MODEL …`) |
| `Logowanie IMAP nieudane` | Zmienione hasło: `password KONTO`. Gmail wymaga hasła aplikacji |
| `Brak UIDVALIDITY` / „zmieniło się UIDVALIDITY” | Serwer przenumerował folder: `pilot` tego konta, potem `morning-setup` |
| `Inne zadanie trwa` | Trwa poranek albo inne polecenie. Poczekaj (blokada `data/job.lock`) |
| Port 8765 zajęty | Panel już działa w tle. Nie uruchamiaj `serve` drugi raz |
| Panel nie działa po restarcie | Zaloguj się na Maca. `launchctl print gui/$(id -u)/pl.sebastian.panel`. Logi `data/logs/panel.err` |
| Rano brak nowych maili | Podsumowanie → historia poranków. `data/logs/jobs.log`. Czy Mac był włączony o 06:30? |
| WebUI: brak danych lub stare dane | Docker uruchomiony? `python sebastian.py bridge`. Pamięć bota → stan kopiowania |
| WebUI: „Brak dostępu” | `ALLOWED_EMAIL` w Valves musi być e-mailem konta Open WebUI |
| Nauka: „Logowanie Google wygasło” | `python sebastian.py learn-login` (poczta działa dalej) |
| Nauka: brak `credentials.json` | Rozdział 5.6, plik do `data/learner/` |
| Nauka nie startuje w tle / „Operation not permitted” | Folder w chronionym miejscu (Pobrane/Biurko/Dokumenty/iCloud): przenieś do `~/SebastianSystem` |
| Nauka nie loguje się do skrzynek w tle | Uruchom raz `learn-mail-test` przy Macu i kliknij **Zawsze pozwalaj** przy Pęku kluczy |
| Nauka: „Plik learner.json jest uszkodzony” | Popraw JSON albo usuń plik (wrócą ustawienia domyślne, w tym puste klucze Open WebUI) |
| Nauka stoi rano | Czeka na koniec poranka Sebastiana. To normalne |
| Dużo błędów w `learn-status` | `tail -n 100 data/logs/learner.log`, poprawa przyczyny, `learn-retry` |
| Profil miesza dwie osoby | `OWNER_NAME` / `OWNER_CONTEXT` (5.7), potem `learn-consolidate` |
| W logu `token repeat limit reached` / „Model zapętlił się na fragmencie” | Model utknął na powtarzalnym tekście (np. tabela z PDF). Od 2.1.1 program ponawia z inną temperaturą, a w razie potrzeby pomija ten jeden fragment. Pojedyncze wpisy są normalne. Gdy jest ich dużo, rozważ inny model (`learn-set MODEL …`) |
| Mac zwalnia | `learn-set PAUSE_BETWEEN_CALLS_S 3` albo mniejszy `MODEL`, potem `learn-start` |
| Kończy się miejsce | `du -sh data/learner/*`. Ogranicz `MAIL_HISTORY_SINCE` / `ATTACHMENTS_SINCE` albo wyłącz `SAVE_TEXT` |
| Komunikat aktualizatora „STOP” | Nic nie zmieniono albo przywrócono kopię. Skopiuj komunikat i skonsultuj |

Przy prośbie o pomoc podaj: dokładne polecenie, komunikat błędu i ostatnie ~30 linii odpowiedniego logu. **Bez** haseł, tokenów i treści maili.

---

## 15. Dla programisty — budowa kodu i zasady zmian

### 15.1. Wzorce w kodzie

- **Migracje tylko dodające.** Każdy moduł ma `migrate(c)`, które robi `CREATE TABLE IF NOT EXISTS` i `ALTER TABLE … ADD COLUMN` po sprawdzeniu `PRAGMA table_info`. Nigdy nie usuwaj ani nie zmieniaj znaczenia istniejących kolumn: stara wersja kodu musi dalej działać na nowszej bazie.
- **Rejestracja tras.** Moduły panelu mają `register(app, s)`, gdzie `s` to moduł `sebastian` (dostęp do `db()`, `config()`, `DATA`, `now()`). Logowanie i CSRF dla wszystkich tras zapewnia `protect()` w `make_app()`. Formularze POST muszą wysyłać `csrf`.
- **Nauka** łączy się z Sebastianem przez `learner.bind(s)`. Moduł nie ma efektów ubocznych przy imporcie, bo panel też go importuje. Sygnały i logowanie konfiguruje dopiero `run()`.
- **Polecenia `learn-*`** są obsługiwane przed blokadą `job.lock`, więc nie blokują poranka. Pozostałe polecenia biorą blokadę.
- **IMAP:** zawsze `select(…, readonly=True)` i `BODY.PEEK`. Testy to sprawdzają.
- **AI:** Sebastian używa `format` ze schematem JSON i walidacji (`validate_result`, terminy muszą mieć cytat z treści). Nauka używa `format: json` i odrzuca nieczytelne odpowiedzi. Dla modeli „myślących” (qwen3, deepseek-r1…) wysyłane jest `think: false`.
- **Podpis wątku (`files.sig`)** decyduje o ponownym czytaniu. Zmiana sposobu liczenia podpisu powoduje ponowne czytanie **wszystkich** wątków. Zmieniaj go tak, jak 2.1: tylko dla wątków, których zmiana dotyczy.
- **Kod jest w języku angielskim, komunikaty dla użytkownika po polsku.**

### 15.2. Testy

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_sebastian.py test_learner.py -v
```

Testy używają tymczasowego katalogu danych, symulowanego IMAP i symulowanej Ollamy. Nie dotykają prawdziwych skrzynek. Testy załączników wymagają `requirements-learner.txt`. Każda zmiana powinna dodać test do odpowiedniego pliku. Opis zakresu testów jest w `docs/TESTY.md`.

**Środowisko testowe z danymi demo** (bez prawdziwej poczty):

```bash
SEBASTIAN_DATA="$PWD/demo-data" python sebastian.py init
SEBASTIAN_DATA="$PWD/demo-data" python sebastian.py demo
SEBASTIAN_DATA="$PWD/demo-data" python sebastian.py serve
```

Panel demo nie może działać równocześnie z panelem w tle (ten sam port). Najpierw `schedule remove`.

### 15.3. Jak dodać funkcję

1. Nowy moduł `nazwa.py` z `migrate(c)` (jeśli potrzebuje tabel) i `register(app, s)` (jeśli ma strony).
2. Wywołaj `migrate` w `sebastian.db()` i `register` w `make_app()`.
3. Szablony w `templates/` dziedziczą z `base.html`. Link w nawigacji dodaj w `base.html`.
4. Polecenie CLI: parser w `main()`, obsługa w odpowiedniej gałęzi.
5. Testy, potem aktualizacja `DOKUMENTACJA.md` (polecenia, ustawienia, tabele) i notatka w `docs/aktualizacje/`.

### 15.4. Wydawanie aktualizacji

Wzorzec aktualizatora (zob. 1.4, 2.1):

- jeden plik `Sebastian_aktualizacja_X_Y.py` z zawartością nowych plików,
- sprawdzenie skrótów SHA-256 plików poprzedniej wersji (odmowa przy ręcznych zmianach, `--force` świadomie),
- zatrzymanie nauki, kopia plików i bazy w `backups/`, atomowa podmiana (`os.replace`),
- test importu i `learn-status`, przywrócenie kopii przy błędzie,
- przeładowanie panelu (`launchctl kickstart -k`) i wznowienie nauki.

### 15.5. Git

- Gałąź `main`. Commity opisowe po polsku, np. „Sebastian 2.1 – załączniki”.
- **Przed `git add`:** `git status`, czy nie ma danych (13.1).
- Nie dodawaj plików `*.bak-*`, kopii folderów ani paczek ZIP.

### 15.6. Znane ograniczenia i dług techniczny

- `rollback.py` (z 1.3) jest przestarzały i ma błąd (`stat().mtime` zamiast `st_mtime`). **Nie używać.** Do przywracania służą kopie z `backups/` i instrukcje w `docs/aktualizacje/`. Do usunięcia w kolejnej wersji.
- Gmail bez OAuth: wymaga hasła aplikacji (dostępnego tylko przy 2FA).
- Dysk Google: aplikacja w trybie „Testowanie”, logowanie co 7 dni.
- Panel analizuje tylko treść maila do 12 000 znaków. Załączniki czyta wyłącznie nauka.
- Narzędzie pamięci w Open WebUI szuka słów (BM25), nie znaczeń. Wyszukiwanie wektorowe zapewniają bazy Knowledge (9.3).
- Ta sama wiadomość w dwóch folderach może być w panelu dwoma rekordami (nauka deduplikuje po `Message-ID`).
- Brak CC/BCC i „odpowiedz wszystkim”. Kalendarz bez synchronizacji na żywo i bez API map.
- Nauka czyta wątek ponownie po każdej nowej odpowiedzi. Przy bardzo długich wątkach to koszt czasu.
- Akta spraw i osób (zestawienia per osoba lub sprawa z faktów i tekstów) to kolejny planowany etap. Dane są już zbierane (`teksty/`, `facts` ze źródłem i datą).

---

## 16. Historia wersji

| Wersja | Data | Najważniejsze |
| --- | --- | --- |
| 1.0 | 1.10.2026 | Pobieranie z 3 skrzynek (tylko odczyt), analiza AI, panel, raporty, narzędzie Open WebUI „moje sprawy”, import tekstu |
| 1.1 | 11.10.2026 | Kolejka decyzji, kategorie i podkategorie, komentarze, powód pominięcia, pamięć przykładów decyzji, `think=False` |
| 1.2 | 11.10.2026 | Załączniki na żądanie w panelu, odpowiedzi SMTP z podglądem, stopki, szkice kalendarza ICS, konflikty, dojazd |
| 1.3 | 11.10.2026 | Szybkie „Pomiń” z cofnięciem, macierz Eisenhowera, wyjątki ważnych nadawców, Podsumowanie i postęp, poranek 06:30 |
| 1.4 | 11.10.2026 | Szybkie przyciski (kategoria, zadanie, wykonane, priorytet), lista zadań, Pamięć bota (notatki) i narzędzie Open WebUI „pamięć” |
| 2.0 | 15.10.2026 | Połączenie z Drive Learnerem: moduł Nauka (Dysk, poczta Sebastiana, archiwum skrzynek), Bieżące sprawy, Profil wiedzy, RAG, zakładka Nauka, czyste repozytorium |
| 2.1 | 15.10.2026 | Nauka czyta załączniki (PDF, Office, skany, zdjęcia) |
| 2.1.1 | 15.10.2026 | Odporność na „zapętlenie” modelu (`token repeat limit reached`): kara za powtórzenia, ponowienie z inną temperaturą, pominięcie jednego trudnego fragmentu zamiast całego dokumentu |

Szczegóły każdej wersji: `docs/aktualizacje/AKTUALIZACJA_X_Y.md`.

---

## 17. Słowniczek

| Pojęcie | Znaczenie |
| --- | --- |
| **IMAP** | Protokół odczytu poczty z serwera. Sebastian używa go tylko do odczytu |
| **SMTP** | Protokół wysyłania poczty. Używany tylko przy świadomej odpowiedzi z panelu |
| **UID / UIDVALIDITY** | Numer wiadomości w folderze / „wersja” numeracji folderu. Zmiana UIDVALIDITY oznacza przenumerowanie folderu |
| **Pilot / sync / backfill** | Próbka z ustaleniem granicy / nowe maile od granicy / starsze maile do panelu |
| **Archiwum (nauka)** | Starsze maile dociągane przez naukę do jej własnej bazy, poza panelem |
| **Wątek** | Mail i odpowiedzi na niego, połączone nagłówkami. Jednostka nauki z poczty |
| **Fakt** | Jedno zdanie wiedzy o właścicielu wyciągnięte przez model, ze źródłem i datą |
| **Bieżące sprawy** | Przegląd spraw z ostatnich tygodni, odtwarzany od nowa |
| **Profil wiedzy** | Trwała, scalana wiedza o właścicielu w sekcjach |
| **RAG** | Wyszukiwanie pasujących fragmentów wiedzy i podawanie ich modelowi przy odpowiedzi |
| **Embedding / bge-m3** | Zamiana tekstu na wektor do wyszukiwania po znaczeniu; bge-m3 dobrze rozumie polski |
| **Zakres (scope)** | `private` (Gmail, Murena) albo `work` (Partners); `drive` dla Dysku w nauce |
| **LaunchAgent** | Zadanie macOS uruchamiane po zalogowaniu użytkownika |
| **Pęk kluczy** | Systemowy sejf haseł macOS (Keychain) |
| **Ollama** | Program uruchamiający modele AI lokalnie na Macu |
| **Open WebUI** | Aplikacja do czatu z lokalnymi modelami (w Dockerze) |
| **OCR** | Rozpoznawanie tekstu ze skanów i zdjęć (Tesseract) |
