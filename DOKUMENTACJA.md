# Sebastian — pełna dokumentacja projektu

**Wersja opisana w dokumencie: 2.4** (październik 2026)
Lokalny asystent poczty i spraw na Macu, z modułem nauki, który buduje wiedzę o właścicielu z Dysku Google, poczty i załączników, modułem Dokumenty, który zamienia duże skany (także pisane ręcznie, np. księgi wieczyste) w uporządkowany PDF ze spisem treści, oraz Sebastianem na WhatsAppie: poranny przegląd z głosówką, rozmowa w ciągu dnia (także z rodziną — tylko sprawy prywatne) i podsumowania Twojego własnego WhatsAppa (kto pisał, komu odpisać, do kogo oddzwonić).

> **Dla kogo jest ten dokument.** Dla osoby, która przejmuje projekt albo musi coś w nim zrobić ręcznie: zainstalować od zera, przenieść na inny komputer, naprawić, zaktualizować albo rozwinąć kod. Nie trzeba być programistą, żeby korzystać z rozdziałów 1–14. Rozdział 15 jest dla osoby, która zmienia kod.

---

## Spis treści

1. [Czym jest Sebastian](#1-czym-jest-sebastian)
2. [Zasady, których projekt pilnuje](#2-zasady-których-projekt-pilnuje)
3. [Jak to działa — architektura](#3-jak-to-działa--architektura)
4. [Wymagania](#4-wymagania)
5. [Instalacja od zera (wersja 2.4)](#5-instalacja-od-zera-wersja-24)
6. [Codzienna praca w panelu](#6-codzienna-praca-w-panelu)
7. [Praca w tle — harmonogramy macOS](#7-praca-w-tle--harmonogramy-macos)
8. [Moduł Nauka — szczegóły](#8-moduł-nauka--szczegóły)
8a. [Dokumenty — skany i księgi wieczyste (od 2.2)](#8a-dokumenty--skany-i-księgi-wieczyste-od-22)
8b. [WhatsApp — Sebastian w telefonie (od 2.3)](#8b-whatsapp--sebastian-w-telefonie-od-23)
    - [8b.8. Rodzina (od 2.4)](#8b8-rodzina--żona-pisze-do-sebastiana-od-24) · [8b.9. Twój WhatsApp (od 2.4)](#8b9-twój-whatsapp--kto-pisał-komu-odpisać-do-kogo-oddzwonić-od-24)
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

Sebastian to program działający **wyłącznie na Macu właściciela** (Mac Studio M1 Max). Składa się z czterech współpracujących części.

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

**Dokumenty (od wersji 2.2).** Działają w tej samej usłudze w tle co nauka:

- przyjmują duże skany (np. księgę wieczystą, także starą, pisaną ręcznie, albo niemiecki Grundbuch),
- prostują i zmniejszają skan, czytają każdą stronę lokalnym **modelem wizyjnym**; pismo ręczne czytają dwa razy i zaznaczają miejsca niepewne,
- porządkują wpisy (działy księgi, właściciele, hipoteki, służebności…) i składają **mały PDF ze spisem treści i klikalnymi odnośnikami** do wpisów i stron skanu,
- pozwalają w panelu porównać odczyt ze skanem i go poprawić (rozdział 8a).

**WhatsApp (od wersji 2.3).** Sebastian jako kontakt w telefonie:

- codziennie rano wysyła krótki przegląd dnia i głosówkę („Hej Andrzej! …”), w której opowiada, na co zwrócić uwagę,
- odpowiada na Twoje wiadomości i głosówki: zadania, pilne sprawy, kalendarz, „zrobione 2”, „zapamiętaj: …” i zwykłe pytania o Twoje sprawy,
- przysyła powiadomienia (dokument gotowy, wygasło logowanie…), z ciszą nocną (rozdział 8b),
- (od 2.4) rozmawia też z rodziną — np. z żoną — wyłącznie o sprawach prywatnych, i wysyła jej osobny przegląd,
- (od 2.4) czyta Twoje własne konto WhatsApp (tylko odczyt) i podsumowuje: kto pisał, o czym, komu odpisać, do kogo oddzwonić, z kim dawno nie rozmawiałeś.

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
  skany (panel / wrzuc-tutaj) ─► DOKUMENTY (learner_docs.py) ─ model wizyjny ─┘          │
  telefon ⇄ WhatsApp (E2E) ⇄ WHATSAPP (whatsapp*.py, w tle) ─ przegląd, rozmowa ─► Ollama │
                │                 głos: Piper → głosówka · słuch: mlx-whisper · odczyt baz│
                │                       data/dokumenty/  …_opracowanie.pdf  ──► nauka    │
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
| Dokumenty | `learner_docs.py` | Przygotowanie skanu (ocrmypdf), czytanie stron modelem wizyjnym, wpisy KW, składanie PDF, polecenia `doc-*` |
| Dokumenty — panel | `learner_docs_web.py`, `templates/docs.html`, `doc.html`, `doc_page.html` | Zakładka „Dokumenty”: wgrywanie, postęp, sprawdzanie i poprawki stron |
| WhatsApp | `whatsapp.py` | Przegląd (dane → model → tekst + głosówka), rozmowa i komendy, kolejka wysyłki, harmonogram, usługa `wa-run`, polecenia `wa-*` |
| WhatsApp — połączenie | `whatsapp_link.py` | Połączenie z WhatsAppem (neonize), filtr „tylko właściciel i rodzina z listy”, parowanie QR/kodem |
| WhatsApp — obserwacja | `whatsapp_watch.py` | (2.4) Odczyt Twojego konta WhatsApp, flagi „czeka na odpowiedź”/„nieodebrane”, podsumowania i sugestie |
| WhatsApp — panel | `whatsapp_web.py`, `templates/whatsapp.html` | Zakładka „WhatsApp”: stan, podgląd i odsłuch przeglądu, wysyłka, historia rozmowy |
| Narzędzia Open WebUI | `openwebui_tool.py`, `openwebui_memory_tool.py` | Kod do wklejenia w Open WebUI → Tools: „moje sprawy” i „pamięć” |
| Wygląd panelu | `templates/*.html`, `static/*.js` | Szablony HTML (Jinja2) i drobne skrypty |
| Testy | `test_sebastian.py`, `test_learner.py`, `test_docs.py`, `test_whatsapp.py` | Testy automatyczne (bez prawdziwych skrzynek i bez Ollamy) |

### Bazy danych

- `data/sebastian.sqlite3`: maile pobrane przez Sebastiana, analizy, decyzje, zadania, odpowiedzi, kalendarz, notatki. **To serce panelu.**
- `data/learner/stan.sqlite3`: stan nauki: lista dokumentów i wątków, fakty, podsumowania, archiwum maili, załączniki, synchronizacja z Open WebUI.
- `data/dokumenty/dokumenty.sqlite3` (od 2.2): dokumenty ze skanów i odczyt każdej strony.
- `data/whatsapp/whatsapp.sqlite3` (od 2.3): kolejka wysyłki, rozmowa, historia przeglądów.

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
| Tesseract | `brew install tesseract tesseract-lang` | Tekst ze skanów i zdjęć (Dysk, załączniki, Dokumenty) |
| ocrmypdf | `brew install ocrmypdf` | Dokumenty: prostowanie, kompresja i warstwa OCR skanów (zalecane, rozdział 8a.3) |
| Model wizyjny | `ollama pull qwen2.5vl:7b` (ok. 6 GB) | Dokumenty: czytanie stron, także pisma ręcznego. Wymaga Ollamy 0.7+ |
| ffmpeg, libmagic | `brew install ffmpeg libmagic` | WhatsApp: głosówki i biblioteka połączenia (rozdział 8b.4) |
| Konto WhatsApp dla Sebastiana | zalecane: osobny numer (karta SIM/eSIM + WhatsApp Business) | Można też użyć własnego numeru (czat „Ty”), rozdział 8b.1 |
| Docker Desktop + Open WebUI | opcjonalnie | Rozmowa z modelem z wiedzą Sebastiana |
| Hasła do skrzynek | IMAP/SMTP | Gmail: **hasło aplikacji** (wymaga 2FA). Murena: hasło konta. Partners: hasło według instrukcji firmy |
| Google Cloud | projekt z włączonym Google Drive API i kluczem OAuth „Aplikacja komputerowa” | Tylko do czytania Dysku przez naukę (rozdział 5.6) |
| Miejsce na dysku | kilka–kilkanaście GB | Archiwum maili, pełne teksty, kopie zapasowe |
| Pamięć RAM | 32 GB wystarcza dla modeli do 14B | Dwa modele (poranek + nauka) mogą być w pamięci jednocześnie. Model wizyjny 7–8B mieści się obok; większe (ok. 30B) — nie |

**Biblioteki Pythona** instaluje `install.command`: `requirements.txt` (panel, poczta, kalendarz) i `requirements-learner.txt` (Dysk Google, PDF, Word, Excel, PowerPoint, OCR, składanie PDF w Dokumentach). Do testów służy dodatkowo `requirements-test.txt`.

---

## 5. Instalacja od zera (wersja 2.4)

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
   python sebastian.py learn-drive login
   ```

   W przeglądarce: konto Google → „Zaawansowane” → „Przejdź do aplikacji” → Zezwól.

> **Tryb „Testowanie” = logowanie ważne 7 dni.** Publikacja wymagałaby strony WWW i polityki prywatności, co przy prywatnym narzędziu nie ma sensu. Dzień przed wygaśnięciem Mac pokaże powiadomienie. Gdy logowanie wygaśnie, **poczta uczy się dalej**, a nauka wpisze do dziennika jeden komunikat i pokaże powiadomienie (najwyżej raz na dobę) oraz baner w zakładce Nauka. Wtedy `python sebastian.py learn-drive` i wybór: zaloguj ponownie albo wyłącz Dysk, jeśli jego wiedza jest już kompletna. Wiedza z Dysku zostaje w obu przypadkach.

Dysk jest opcjonalny. Bez `credentials.json` nauka pracuje tylko na poczcie. Gdy Dysk jest już przeczytany w całości, możesz go wyłączyć: `python sebastian.py learn-drive off`. Wiedza z Dysku zostaje, a cotygodniowe logowanie przestaje być potrzebne (rozdział 8.9).

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
- [ ] Dokumenty: `brew install ocrmypdf`, `ollama pull qwen2.5vl:7b`; w `check` sekcja „6. Dokumenty” bez ✗ (rozdział 8a.3).
- [ ] WhatsApp: `wa-setup`, `wa-login`, `wa-test` (próbna głosówka). Sebastian przysłał powitanie, a na „pomoc” odpowiada listą komend (rozdział 8b.4).
- [ ] `python sebastian.py check` kończy się „✓ Wszystko działa” albo tylko ostrzeżeniami, które rozumiesz.

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

- **Codziennie (5 min):** przegląd i głosówka na WhatsAppie przy kawie. Potem panel → Do decyzji → maks. 3 rzeczy do działania. W ciągu dnia: pytania do Sebastiana na WhatsAppie („pilne”, „zadania”, „zrobione 2”).
- **Gdy przychodzi duży skan (np. księga wieczysta):** panel → Dokumenty → wgraj. Po opracowaniu przejrzyj strony „do sprawdzenia” i kliknij „Złóż PDF z poprawkami” (rozdział 8a).
- **Raz w tygodniu (jeśli Dysk jest włączony):** `python sebastian.py learn-drive` → 1, gdy Mac pokaże powiadomienie. Jeśli Dysk jest już w pełni przeczytany, możesz go wyłączyć (`learn-drive off`) i ten krok odpada.
- **Raz w tygodniu lub po każdej zmianie:** `python sebastian.py check`, czyli pełne sprawdzenie systemu z podpowiedziami.
- **Raz w miesiącu:** kopia zapasowa (rozdział 14.1) i rzut oka na `learn-status` (błędy, archiwum).

---

## 7. Praca w tle — harmonogramy macOS

Sebastian używa **LaunchAgents** (`~/Library/LaunchAgents/`). Działają po zalogowaniu na konto użytkownika, bez uprawnień administratora.

| Zadanie (Label) | Co uruchamia | Kiedy | Instaluje / usuwa |
| --- | --- | --- | --- |
| `pl.sebastian.panel` | `sebastian.py serve` | zawsze, restart po awarii | `morning-setup` / `schedule remove` |
| `pl.sebastian.jobs` | `sebastian.py morning-run` | 06:30 + co 15 minut | `morning-setup` / `schedule remove` |
| `pl.sebastian.learner` | `caffeinate -is … sebastian.py learn-run` | zawsze, restart po awarii | `learn-start` / `learn-stop` |
| `pl.sebastian.whatsapp` | `caffeinate -i … sebastian.py wa-run` | zawsze, restart po awarii (od 2.3) | `wa-start` / `wa-stop` |

### Poranek (`morning-run`)

- Pobiera nowe maile z gotowych kont (do 200 na folder) i analizuje do 200 nowych.
- Do 4 prób dziennie po 06:30. Po pełnym sukcesie nie ponawia.
- Przy wywołaniach co 15 minut tylko odświeża raport i kopię dla Open WebUI.
- Historia przebiegów jest w „Podsumowanie i postęp”, a konfiguracja w `data/automation.json`.

### Nauka (`learn-run`)

- Pracuje bez przerwy.
- Gdy trwa poranek, czeka, żeby nie zajmować Ollamy.
- Nie usypia Maca (`caffeinate`).
- Od 2.2 w tej samej usłudze działa wątek **Dokumenty**. Pilnuje `data/dokumenty/wrzuc-tutaj/` i po kolei opracowuje dokumenty z kolejki. Na czas analizy dokumentu nauka z poczty czeka (rozdział 8a.4).

### Warunki

Mac musi być włączony, zalogowany i nieuśpiony, z działającą Ollamą, Internetem i odblokowanym Pękiem kluczy. Docker jest potrzebny tylko do kopii w Open WebUI. Po restarcie Maca wystarczy się zalogować, a zadania ruszą same. Ollama powinna być w „Rzeczach otwieranych podczas logowania”.

### Sprawdzenie i ręczne sterowanie

```bash
launchctl print gui/$(id -u)/pl.sebastian.panel | head -5
launchctl print gui/$(id -u)/pl.sebastian.learner | head -5
launchctl print gui/$(id -u)/pl.sebastian.whatsapp | head -5
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

**Gdy model się „zatnie” (od 2.1.1).** Lokalne modele potrafią przy powtarzalnym tekście, np. tabelach z PDF-ów, zacząć w kółko generować to samo. Ollama przerywa wtedy z komunikatem `token repeat limit reached`. Nauka:

1. wysyła każde zapytanie z karą za powtórzenia (`repeat_penalty`),
2. zacięty fragment ponawia raz z inną temperaturą,
3. jeśli to nie pomoże, pomija **tylko ten fragment**, a fakty z reszty dokumentu zostają. Dokument jest oznaczany jako błąd dopiero wtedy, gdy żaden fragment się nie uda albo Ollama w ogóle nie odpowiada.

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

### 8.9. Dostęp do Dysku Google — logowanie, wygaśnięcie, wyłączenie (od 2.1.3)

Logowanie do Dysku działa 7 dni (aplikacja Google w trybie „Testowanie”, rozdział 5.6). Stan dostępu widać w trzech miejscach: `learn-status` (wiersz „Dostęp do Dysku”), `check` (sekcja 4) i zakładka **Nauka** w panelu.

| Stan | Co robi nauka | Co możesz zrobić |
| --- | --- | --- |
| **aktywny** | czyta nowe i zmienione pliki z Dysku (skan co 24 h) | nic; dzień przed wygaśnięciem przyjdzie powiadomienie |
| **logowanie wygasło** | jeden wpis w dzienniku i powiadomienie (najwyżej raz na dobę), baner w panelu. **Poczta uczy się dalej**, wiedza z Dysku zostaje. Ponowna próba dopiero po nowym logowaniu albo co 12 h | `python sebastian.py learn-drive` → 1 (zaloguj) albo 2 (wyłącz) |
| **wyłączony** | nie łączy się z Dyskiem; wiedza z Dysku zostaje w profilu, faktach i tekstach | `python sebastian.py learn-drive on`, potem `learn-drive login` |

Po ponownym zalogowaniu nauka sama to zauważy (zmiana pliku `data/learner/token.json`) i wróci do Dysku bez restartu. Wyłączenie i włączenie przez `learn-drive` same przeładowują naukę w tle.

**Kiedy wyłączyć Dysk:** gdy cały Dysk jest już przeczytany, a nowe pliki pojawiają się rzadko. Raz na jakiś czas można go włączyć, zalogować i pozwolić nauce dociągnąć zmiany (ok. doby), a potem znów wyłączyć.

---

## 8a. Dokumenty — skany i księgi wieczyste (od 2.2)

Moduł **Dokumenty** zamienia opasły skan (np. księgę wieczystą, Grundbuch, akta sprawy) w **mały, uporządkowany PDF**. Pierwsza strona to spis treści z klikalnymi odnośnikami. Moduł czyta druk, maszynopis i **pismo ręczne**. Wszystko dzieje się lokalnie na Macu, w `data/dokumenty/`.

### 8a.1. Co powstaje

Plik `…_opracowanie.pdf` w folderze dokumentu, otwierany z panelu (Dokumenty → dokument → **Otwórz PDF**):

| Część | Zawartość |
| --- | --- |
| Strona 1 | Nazwa, numer księgi i sąd (rozpoznane z tekstu), liczba stron wg rodzaju, **strony do sprawdzenia** (linki), legenda znaczników, **spis treści**: podsumowanie, stan aktualny z najważniejszymi wpisami (linki do wpisów i do skanu), wszystkie wpisy wg działów, do wyjaśnienia, odczyt, skany |
| 1. Podsumowanie | Krótkie streszczenie przygotowane przez model wyłącznie z wpisów |
| 2. Stan aktualny | Wpisy nieoznaczone jako wykreślone, pogrupowane wg działów KW: I-O, I-Sp, II, III, IV, wzmianki, inne. Przy każdym link „skan s. N” |
| 3. Wszystkie wpisy | Także wykreślone (przekreślone), z dokładnym cytatem z odczytu. Gdy cytatu nie da się znaleźć w odczycie, wpis ma ostrzeżenie |
| 4. Do wyjaśnienia | Rzeczy do sprawdzenia: np. stare hipoteki bez wykreślenia, rozbieżności, niepewne nazwiska i kwoty, wpisy niepotwierdzone cytatem |
| 5. Odczyt strona po stronie | Pełny tekst każdej strony: żółte tło = niepewne, czerwone = nieczytelne, przekreślenie = tekst wykreślony. Pod stroną: różnice między dwoma odczytami pisma |
| 6. Skany | Oczyszczone, wyprostowane i zmniejszone skany. Na dole każdej strony link „« spis treści”. Pod skanem jest niewidoczna warstwa tekstu, także z pisma ręcznego, więc Cmd+F znajduje słowa na skanach |

W bocznym panelu PDF (zakładki) jest pełny spis, w tym każda strona skanu z rodzajem, działem i oznaczeniem „do sprawdzenia”.

Dla dokumentów, które nie są księgą wieczystą (rodzaj „inny dokument”), części 2–3 grupują pozycje wg rozdziałów dokumentu: strony umowy, nieruchomości, kwoty, terminy, zobowiązania.

### 8a.2. Jak to działa — cztery etapy

1. **Przygotowanie skanu** (minuty). Strony są renderowane w 200 dpi jako JPEG. Kolor zostaje tylko na stronach, które go mają, np. z czerwonymi wykreśleniami albo kolorowymi pieczęciami. `ocrmypdf` prostuje i obraca strony oraz dodaje warstwę tekstu z Tesseracta (polski, niemiecki, angielski). Strony, które mają prawdziwy tekst (np. wydruk z elektronicznej księgi), zostają bez zmian i nie są czytane przez model. Typowo plik maleje kilka–kilkanaście razy.
2. **Czytanie stron** (najdłuższy etap). Model wizyjny (`DOC_VISION_MODEL`, domyślnie `qwen2.5vl:7b`) ogląda każdą stronę:
   - najpierw ją rozpoznaje: druk, maszynopis, rękopis, mieszana, pusta albo rysunek; wykreślenia, pieczęcie, podpisy, dopiski, język,
   - **druk i maszynopis**: poprawia odczyt Tesseracta, patrząc na obraz, zwłaszcza cyfry, polskie znaki i tabele,
   - **pismo ręczne i strony mieszane**: tnie stronę na poziome pasy w odstępach między wierszami (rozkładówki najpierw na lewą i prawą połowę), powiększa je i czyta **dwa razy** (drugi raz innym poleceniem albo drugim modelem `DOC_VISION_MODEL_2`). Słowa, w których odczyty się różnią, są oznaczane jako niepewne `⟦…⟧`, a zgodność obu odczytów daje „pewność” strony,
   - model ma zakaz zgadywania: niepewne słowo oznacza `[?]`, nieczytelne `[nieczytelne]`, przekreślone `~~…~~`, pieczęć `[pieczęć: …]`, podpis `[podpis]`, dopisek `[margines: …]`. Tekst niemiecki (np. kurrenta) przepisuje w oryginale, bez tłumaczenia.
3. **Porządkowanie** (model tekstowy nauki, `MODEL`). Strona po stronie powstaje lista wpisów (dział, rodzaj, tytuł, treść, numer, data, kwota, osoby, wykreślony). **Każdy wpis musi mieć dokładny cytat z odczytu.** Program sprawdza, czy cytat naprawdę jest na stronie. Jeśli nie, wpis trafia do „Do wyjaśnienia”. Numer księgi (np. `KR1P/00012345/6`) i sąd są wyszukiwane w tekście wprost, bez modelu. Na końcu model pisze podsumowanie i listę rzeczy do wyjaśnienia, wyłącznie na podstawie wpisów (odwołania do nieistniejących wpisów są odrzucane).
4. **Składanie PDF** (sekundy–minuty). Raport w `reportlab`, skany dołączone przez PyMuPDF, linki, zakładki i warstwa tekstu. Czcionka: Arial z macOS (polskie znaki), tylko użyte litery.

Każda strona i każdy etap zapisuje postęp w `data/dokumenty/dokumenty.sqlite3`. Po restarcie Maca, `learn-stop` albo Ctrl+C praca wraca dokładnie do strony, na której przerwano. Przerwana strona jest czytana od nowa, a gotowe strony nie są czytane ponownie.

Opracowany dokument trafia też do **nauki** (`DOC_TO_LEARNING`): podsumowanie, wpisy i odczyt jako pozycja `doc:<nr>`. Z niego powstają fakty do Profilu wiedzy, Bieżących spraw i RAG.

### 8a.3. Przygotowanie (jednorazowo)

Aktualizator 2.2 proponuje te kroki sam. Ręcznie:

```bash
brew install ocrmypdf            # prostowanie, kompresja, warstwa OCR (zalecane)
brew install tesseract-lang      # polski i niemiecki dla Tesseracta (jeśli jeszcze nie ma)
ollama pull qwen2.5vl:7b         # model, który „widzi” stronę (ok. 6 GB)
python sebastian.py check        # sekcja „6. Dokumenty” powinna być zielona
```

Bez `ocrmypdf` moduł też działa: skan jest zmniejszany, a OCR robi Tesseract przy czytaniu strony. Nie ma wtedy prostowania i obracania stron. Model wizyjny wymaga Ollamy w wersji 0.7 lub nowszej. Przy błędzie pobierania zaktualizuj aplikację Ollama.

**Wybór modelu na 32 GB RAM.** `qwen2.5vl:7b` (ok. 6 GB) to bezpieczny wybór: zostaje miejsce na model nauki. Do porównania na własnym skanie można pobrać np. `qwen3-vl:8b` albo `gemma3:12b` i sprawdzić je poleceniem `doc-test` (8a.5). Większe modele wizyjne (ok. 30B) na 32 GB będą działać bardzo wolno albo wcale. Drugi model do podwójnego czytania (`DOC_VISION_MODEL_2`) daje bardziej niezależne odczyty, ale wydłuża pracę i zajmuje pamięć. Domyślnie drugi odczyt robi ten sam model z innym poleceniem.

### 8a.4. Dodanie dokumentu

Trzy sposoby, wynik jest ten sam:

- **Panel:** zakładka **Dokumenty** → wybierz plik (PDF albo zdjęcia JPG/PNG/TIFF, do `DOC_MAX_UPLOAD_MB`), nazwa, rodzaj → **Wgraj i dodaj do kolejki**.
- **Finder:** skopiuj plik do `data/dokumenty/wrzuc-tutaj/`. Po minucie od końca kopiowania Sebastian przeniesie go do kolejki. Pliki, których nie da się otworzyć, trafiają do `wrzuc-tutaj/nieudane/`.
- **Terminal:** `python sebastian.py doc-add ~/Downloads/KW.pdf --nazwa "KW Kraków, ul. Przykładowa 1" --typ kw`. Plik jest **kopiowany**, oryginał zostaje na miejscu.

Rodzaj: `auto` (rozpoznaj po treści), `kw` (księga wieczysta lub Grundbuch), `ogolny` (umowa, akt, akta sprawy).

Analizę prowadzi **usługa nauki w tle** (`learn-start`). Dokumenty są opracowywane po kolei, jeden naraz. Na czas analizy dokumentu nauka z poczty czeka (`DOC_PAUSE_LEARNING`), żeby modele nie walczyły o Ollamę. Rano, w trakcie poranka Sebastiana, czeka też dokument. Gdy usługa nauki nie działa, dokument można przetworzyć w oknie Terminala: `python sebastian.py doc-run` (Mac nie uśnie do końca, Ctrl+C przerywa, a postęp zostaje).

**Ile to trwa** (Mac Studio M1 Max, `qwen2.5vl:7b`, orientacyjnie): strona z tekstem cyfrowym — sekundy; druk lub maszynopis — ok. 0,5–1,5 min; rękopis — ok. 2–4 min (kilka pasów × 2 odczyty); porządkowanie — ok. 15–40 s na stronę. Księga na 300 stron z pismem ręcznym to typowo 12–30 godzin, czyli praca na noc albo dwie. Panel i `doc-list` pokazują szacunek pozostałego czasu, liczony z dotychczasowego tempa.

### 8a.5. Sprawdzanie i poprawki

1. Panel → Dokumenty → dokument → **Strony**. Strony z żółtą ramką są **do sprawdzenia**: mają niepewne słowa, nieczytelne fragmenty albo pewność poniżej `DOC_CHECK_BELOW`. Filtry: wszystkie, do sprawdzenia, z pismem ręcznym.
2. Kliknięcie strony otwiera porównanie: skan po lewej (kliknij obraz, by go powiększyć), odczyt po prawej. Pod spodem jest tabela „Drugi odczyt różnił się”.
3. Popraw tekst. Po sprawdzeniu usuń nawiasy `⟦ ⟧`. Zaznacz **Strona sprawdzona** i **Zapisz** (albo **Zapisz i przejdź do następnej do sprawdzenia**).
4. Po poprawkach kliknij na stronie dokumentu **Złóż PDF z poprawkami**. Ponownie porządkowane są **tylko poprawione strony**, potem powstaje nowy PDF.

**Trudne pismo.** Przycisk „pobrać je jako ZIP” (albo `doc-export NR`) pakuje obrazy stron do sprawdzenia i ich odczyt. Możesz pokazać je komuś, kto czyta dawne pismo, albo innemu narzędziu (np. Transkribus dla kurrenty). Poprawiony tekst wpisujesz potem w panelu. ZIP powstaje tylko na Twoje żądanie, a Sebastian niczego nigdzie nie wysyła.

**Test modelu na własnym skanie** (nic nie zapisuje):

```bash
python sebastian.py doc-test ~/Downloads/KW.pdf --strona 12
```

Pokazuje rodzaj strony, obserwacje, odczyt z oznaczeniami, różnice dwóch odczytów i czas. Do porównania modeli: `learn-set DOC_VISION_MODEL qwen3-vl:8b`, ponownie `doc-test`, a następnie ustawienie lepszego modelu na stałe (i `learn-start`).

### 8a.6. Pliki dokumentu

`data/dokumenty/<nr>-<nazwa>/`:

| Plik | Zawartość |
| --- | --- |
| `oryginal.pdf` | Kopia wgranego pliku (zdjęcia zamienione na PDF) |
| `skan.pdf` | Skan po przygotowaniu (wyprostowany, zmniejszony, z warstwą OCR) |
| `ocr.txt` | Tekst z Tesseracta, strony rozdzielone znakiem nowej strony |
| `…_opracowanie.pdf` | **Wynik** |
| `odczyt.md` | Pełny odczyt strona po stronie (Markdown) — „Pobierz odczyt” w panelu |
| `wpisy.json` | Wpisy, podsumowanie i lista do wyjaśnienia (dane maszynowe) |
| `do_nauki.md` | Tekst przekazany do nauki |
| `podglad/` | Miniatury dla panelu (można usunąć, odtworzą się) |
| `…_do_sprawdzenia.zip` | Tylko po kliknięciu „pobierz jako ZIP” / `doc-export` |

Baza: `data/dokumenty/dokumenty.sqlite3` (`jobs` — dokumenty i etapy; `pages` — odczyt każdej strony: rodzaj, obserwacje, tekst, inne odczytania, pewność, czas, sprawdzenie ręczne, wpisy). Blokada `data/dokumenty/.praca.lock` pilnuje, żeby jeden dokument analizował tylko jeden proces.

### 8a.7. Jakość i granice — co warto wiedzieć

- **To opracowanie robocze, nie odpis.** W sprawach prawnych rozstrzyga aktualny odpis z sądu albo oryginał. PDF ma przy każdym wpisie link do skanu właśnie po to, żeby łatwo to sprawdzić.
- **Cyfry.** Numery działek, kwoty i PESEL-e model przepisuje „znak po znaku”, ale przy słabym skanie może się pomylić. Takie miejsca są zwykle oznaczone na żółto, a mimo to warto sprawdzić je na skanie.
- **Pismo ręczne.** Współczesne, wyraźne pismo urzędnicze model czyta w większości dobrze. Stare pismo, zwłaszcza niemiecka kurrenta, wymaga sprawdzenia w panelu. Dwa odczyty pokazują, gdzie model się waha.
- **Wykreślenia.** O „stanie aktualnym” decyduje rozpoznanie przekreślenia (`~~…~~`) albo informacji o wykreśleniu. Jeśli wykreślenie jest osobnym wpisem na innej stronie, model może go nie połączyć z pierwotnym wpisem. Lista „Do wyjaśnienia” zwykle to wyłapuje, a ostatecznie warto to sprawdzić ręcznie.
- **Model nie dopisuje wpisów.** Wpis bez potwierdzającego cytatu jest wyraźnie oznaczony. Podsumowanie opiera się wyłącznie na wpisach.

### 8a.8. Najczęstsze problemy

| Objaw | Działanie |
| --- | --- |
| Dokument stoi w „czytaniu stron”, w panelu „Brak modelu wizyjnego” | `ollama pull qwen2.5vl:7b` (albo model z `DOC_VISION_MODEL`). Analiza ruszy sama |
| „Usługa nauki nie działa w tle — dokumenty czekają” | `python sebastian.py learn-start` albo `doc-run` |
| Stan „błąd” | Panel → dokument → komunikat; `tail -n 50 data/logs/learner.log`; po usunięciu przyczyny **Wznów** (`doc-resume NR`) |
| `ocrmypdf` kończy się błędem | Program sam ponawia bez prostowania, a potem pracuje bez ocrmypdf. Sprawdź `brew upgrade ocrmypdf` |
| Bardzo wolno | `learn-set DOC_DOUBLE_READ nie` (jeden odczyt pisma: ok. 2× szybciej, mniej pewności), mniejszy `DOC_MAX_STRIPS`. Potem `learn-start` |
| Drobne pismo czytane słabo | `learn-set DOC_SCAN_DPI 300` i `learn-set DOC_READ_DPI 300` (większy plik, wolniej), potem `doc-rebuild NR strony` |
| Wynikowy PDF za duży | `learn-set DOC_SCAN_DPI 150`, `DOC_JPEG_QUALITY 60`, `DOC_KEEP_COLOR nie`; zmiana obowiązuje dla nowych dokumentów |
| Źle rozpoznane działy / zły rodzaj dokumentu | `doc-rebuild NR struktura` (bez ponownego czytania stron). Rodzaj ustaw przy dodaniu (`--typ kw`) |
| Mac się nagrzewa / jest wolny przy pracy | To normalne przy długiej analizie. Można wstrzymać dokument (`doc-pause NR`) i wznowić w nocy |

---

## 8b. WhatsApp — Sebastian w telefonie (od 2.3)

Sebastian jest też kontaktem na WhatsAppie. **Rano** wysyła krótki przegląd dnia i **głosówkę** („Hej Andrzej! …”), w której opowiada szerzej, na co zwrócić uwagę. W ciągu dnia **odpowiada na Twoje wiadomości i głosówki**: komendy (zadania, pilne, kalendarz…) i zwykłe pytania o Twoje sprawy. Dostajesz też **powiadomienia** (dokument gotowy, wygasło logowanie do Dysku…), z ciszą nocną.

### 8b.1. Jak to działa

```
 Twój telefon (WhatsApp)  ⇄  WhatsApp (szyfrowanie end-to-end)  ⇄  Mac: usługa pl.sebastian.whatsapp (wa-run)
                                                                     │  „połączone urządzenie”, jak WhatsApp Web
                                                                     ├─ przegląd: dane z panelu, kalendarza, nauki, dokumentów → model (Ollama) → tekst
                                                                     ├─ głos: tekst → Piper (polski głos, lokalnie) → ffmpeg → głosówka OGG/Opus
                                                                     ├─ słuch: Twoja głosówka → mlx-whisper (lokalnie) → tekst
                                                                     └─ odpowiedź: komenda albo model z kontekstem Twoich spraw
```

- **Połączenie:** Sebastian łączy się z kontem WhatsApp jako **połączone urządzenie** (Ustawienia → Połączone urządzenia), tak jak WhatsApp Web. Robi to biblioteka `neonize` (oparta na `whatsmeow`). Wiadomości są szyfrowane end-to-end, jak w telefonie. Sesja (klucze) leży w `data/whatsapp/sesja.sqlite3`.
- **Konto Sebastiana — zalecane: osobny numer.** Np. tania karta SIM (albo drugi numer/eSIM) z aplikacją **WhatsApp Business** na zapasowym telefonie lub jako drugi numer w Twoim telefonie. Zapisz ten numer w kontaktach jako „Sebastian”. Wtedy Sebastian jest zwykłym kontaktem, a Twoje główne konto nie jest powiązane z nieoficjalną biblioteką. **Można też połączyć Twój własny numer.** Sebastian pisze wtedy w czacie „Ty” (wiadomości do siebie) i słucha tylko tego, co tam napiszesz.
- **Słucha tylko Ciebie.** Przyjmuje wyłącznie wiadomości z numeru `WA_OWNER_PHONE` (także w nowej adresacji WhatsAppa „LID”). Grupy, statusy i inni ludzie są ignorowani i nawet nie zapisywani. Wiadomości starsze niż 6 godzin (np. po wyłączeniu Maca) są zapisywane, ale bez odpowiedzi.
- **Telefon z kontem Sebastiana musi mieć od czasu do czasu Internet.** WhatsApp odłącza połączone urządzenia, gdy główny telefon jest offline przez ok. 14 dni.

### 8b.2. Poranny przegląd

1. O `WA_BRIEF_TIME` (domyślnie 07:00) usługa sprawdza, czy skończyła się poranna analiza poczty (06:30). Czeka na nią najwyżej godzinę. Jeśli Mac był uśpiony, przegląd przyjdzie po przebudzeniu, ale nie później niż `WA_BRIEF_LATEST` (11:30).
2. Zbiera dane (tylko odczyt): nowe maile z poranka według priorytetu (macierz z panelu), otwarte zadania z terminami (także po terminie), pilne i ważne sprawy, wpisy z kalendarzy zaimportowanych w panelu, liczbę maili do decyzji, stan dokumentów oraz notatkę „Bieżące sprawy” z nauki. Tylko z zakresów `WA_SCOPES`.
3. Model Sebastiana (ten od poczty; `WA_MODEL`) pisze **wiadomość** (do ok. 900 znaków, w punktach) i **tekst głosówki** (ok. 1,5–2 minuty, mową potoczną, „Hej Andrzej! …”). Model dostaje wyłącznie zebrane dane i ma zakaz wymyślania. Gdy Ollama nie działa, przychodzi **przegląd awaryjny** złożony z samych liczb i tytułów.
4. Głosówka powstaje lokalnie: **Piper** z polskim głosem `pl_PL-darkman-medium` (męski). Gdy go nie ma, używany jest głos macOS (`say`, `WA_SAY_VOICE`). `ffmpeg` zamienia nagranie na format głosówki WhatsApp (OGG/Opus).
5. Wiadomość i głosówka trafiają do kolejki i są wysyłane. Historia przeglądów z nagraniem do odsłuchania jest w panelu: zakładka **WhatsApp**.

Opcjonalnie: **wieczorne podsumowanie** (`WA_EVENING`, co zamknięte, co jutro w kalendarzu) i **tygodniowe** (`WA_WEEKLY`).

### 8b.3. Rozmowa — co możesz napisać (albo nagrać)

| Wiadomość | Co robi Sebastian |
| --- | --- |
| `pomoc` | Lista komend |
| `przegląd` / `co dziś` | Dzisiejszy przegląd od nowa (tekst + głosówka) |
| `pilne` | Pilne i ważne sprawy (z poczty i zadań) |
| `zadania` | Otwarte zadania z numerami i terminami |
| `zrobione 2` | Oznacza zadanie nr 2 (z ostatniej listy) jako wykonane — jak przycisk w panelu: wpis w dzienniku zdarzeń, można cofnąć |
| `poczta` | Nowe maile z poranka z priorytetami |
| `kalendarz` / `jutro` | Wpisy na dziś / jutro |
| `dokumenty` | Postęp opracowania skanów |
| `zapamiętaj: …` | Notatka w Pamięci bota (prywatnej). Korzystają z niej analizy i Open WebUI |
| `wieczór` / `tydzień` | Podsumowanie teraz |
| `cisza` / `cisza do 14` / `wznów` | Wyciszenie powiadomień (na pytania Sebastian dalej odpowiada) |
| `status` | Czy działa Ollama, poranek, nauka, dokumenty |
| każde inne pytanie | Odpowiedź modelu z danych: dzisiejszy kontekst, Bieżące sprawy, fakty z nauki pasujące do słów pytania, maile z ostatnich 120 dni, notatki. Jeśli czegoś nie wie — mówi to wprost |

**Głosówki od Ciebie** są zamieniane na tekst lokalnie (`mlx-whisper`, model `WA_WHISPER_MODEL`, pobierany przy pierwszym użyciu, ok. 1,5 GB). Na głosówkę Sebastian odpowiada tekstem i głosówką (`WA_REPLY_VOICE`). Podczas pisania odpowiedzi widać „pisze…”, a Twoja wiadomość dostaje niebieskie ptaszki.

Sebastian **nie wysyła maili, nie usuwa i nie zmienia niczego poza dwiema świadomymi komendami** (`zrobione N`, `zapamiętaj:`). Obie zostawiają ślad w dzienniku zdarzeń panelu. Treść maili traktuje jako dane, nie polecenia.

**Rozmowa bez WhatsAppa** (np. do wypróbowania odpowiedzi): `python sebastian.py wa-chat`. Te same komendy i odpowiedzi, w Terminalu.

### 8b.4. Uruchomienie (jednorazowo, ok. 15 minut)

Aktualizator 2.3 proponuje kroki 1–2 sam.

```bash
brew install ffmpeg libmagic                         # głosówki i biblioteka WhatsApp
python -m pip install -r requirements-whatsapp.txt   # neonize, Piper, mlx-whisper
python sebastian.py wa-setup                         # Twój numer, imię, godzina przeglądu; pobiera polski głos
python sebastian.py wa-login                         # połączenie: kod QR w Terminalu
python sebastian.py wa-test                          # sprawdzenie + próbna głosówka (odtwarza się na Macu)
```

`wa-login`: na telefonie z kontem **Sebastiana** wybierz WhatsApp → Ustawienia → **Połączone urządzenia** → **Połącz urządzenie** i zeskanuj kod z Terminala (jest też w `data/whatsapp/qr.png`). Gdy skanowanie jest niewygodne: `python sebastian.py wa-login --kod`. Wtedy w telefonie wybierz „Połącz za pomocą numeru telefonu” i wpisz pokazany kod. Na końcu `wa-login` proponuje uruchomienie usługi w tle (`wa-start`). Po starcie Sebastian wysyła powitanie z listą komend.

**Próba bez WhatsAppa:** `python sebastian.py wa-set WA_TRANSPORT plik`. Wiadomości trafiają wtedy do `data/whatsapp/wyslane/`. Podgląd przeglądu z odsłuchem: `python sebastian.py wa-brief --podglad` albo panel → WhatsApp → „Podgląd przeglądu”.

### 8b.5. Pliki i baza

`data/whatsapp/` 🔒:

| Plik | Zawartość |
| --- | --- |
| `whatsapp.json` | Ustawienia `WA_*` (12.3) |
| `whatsapp.sqlite3` | `outbox` (kolejka wysyłki: tekst/głos, cel, próby, błędy), `inbox` (Twoje wiadomości, także transkrypcje głosówek), `briefs` (historia przeglądów: tekst, tekst głosówki, nagranie, model/awaryjny), `meta` (wysłane przeglądy, wyciszenie, znak życia usługi, połączone konto, numery zadań z ostatniej listy) |
| `sesja.sqlite3` | **Klucze połączenia z WhatsAppem** — jak hasło. Kto ma ten plik, może pisać jako konto Sebastiana |
| `glosy/` | Głos Piper (`.onnx` + `.json`) |
| `nagrania/` | Głosówki (`.ogg` wysłane, `.wav` do odsłuchu w panelu) |
| `wyslane/` | Tylko w trybie próby (`WA_TRANSPORT plik`) |

Log: `data/logs/whatsapp.log` (bez treści wiadomości). Błędy programu: `data/logs/whatsapp.err`.

### 8b.6. Prywatność i ryzyko — uczciwie

- **Co wychodzi z Maca:** przegląd, głosówki i odpowiedzi przechodzą przez WhatsApp (szyfrowane end-to-end; Meta widzi metadane: kto, kiedy, ile). Na telefonie zostają treści spraw, także klientów, jeśli `WA_SCOPES` obejmuje `work`. Rozważ `python sebastian.py wa-set WA_SCOPES private`, jeśli sprawy firmowe nie powinny trafiać na telefon. Zabezpiecz telefon kodem.
- **Nieoficjalny klient:** `neonize`/`whatsmeow` nie są oficjalnym API WhatsAppa. Przy małym ruchu (kilka wiadomości dziennie do jednej osoby) ryzyko blokady jest niskie, ale realne. To główny powód, dla którego zalecany jest osobny numer dla Sebastiana. Oficjalna alternatywa (WhatsApp Business Cloud API) wymaga firmy w Meta, płatnych szablonów wiadomości i publicznego adresu internetowego dla Maca. Dlatego nie jest tu użyta (15.6).
- Sesja WhatsApp i cały `data/whatsapp/` **nigdy nie trafiają na GitHub** (`data/` w `.gitignore`).

### 8b.8. Rodzina — żona pisze do Sebastiana (od 2.4)

Do Sebastiana mogą pisać też wybrane osoby, np. żona. Każda z nich ma **dostęp tylko do spraw prywatnych**:

| Widzi | Nie widzi |
| --- | --- |
| prywatną pocztę (konta `private`), prywatne zadania, kalendarze zaimportowane w panelu, prywatne notatki Pamięci bota, fakty nauki z prywatnej poczty | pocztę firmową i klientów (`work`), Dysk, Bieżące sprawy i Profil wiedzy (mieszają sprawy firmowe), dokumenty, Twój WhatsApp (8b.9), stan systemu |

- **Komendy:** `pomoc`, `przegląd`, `kalendarz`, `jutro`, `zadania` (bez numerów), `pilne`, `poczta`, `zapamiętaj: …` (notatka trafia do Twojej Pamięci bota jako „Od Kasia: …”). Na zwykłe pytania Sebastian odpowiada z prywatnych danych, a na pytania o sprawy firmowe mówi, że nie ma do nich dostępu. **Nie może** zamykać zadań, prosić o podsumowanie wieczorne/tygodniowe ani wyciszać powiadomień (te idą tylko do Ciebie).
- **Poranny przegląd:** osobny, „Hej Kasiu!”, o tej samej godzinie co Twój, tylko z prywatnych danych (opcjonalnie z głosówką).
- **Powitanie:** po dodaniu osoby Sebastian pisze do niej, czym jest, co widzi, i że **rozmowy widzisz Ty** w panelu (zakładka WhatsApp, kolumna z imieniem).
- **Wymaga osobnego numeru Sebastiana.** Gdy Sebastian jest połączony z Twoim własnym numerem (czat „Ty”), rodzina nie może z nim pisać — `check` to pokaże.

```bash
python sebastian.py wa-user dodaj          # pyta: numer, imię, forma w powitaniu (np. Kasiu), kim jest (np. żona), przegląd, głosówka
python sebastian.py wa-user                # lista osób
python sebastian.py wa-user usun 48500111222
```

Bez pytań: `python sebastian.py wa-user dodaj 48500111222 --imie Kasia --wolacz Kasiu --kto żona --przeglad tak --glos tak`. Po zmianie usługa przeładowuje się sama.

### 8b.9. Twój WhatsApp — kto pisał, komu odpisać, do kogo oddzwonić (od 2.4)

Sebastian może **czytać Twoje własne konto WhatsApp** i co rano (oraz na żądanie) mówić: „Wczoraj pisał do Ciebie Jan w sprawie terminu — czeka na odpowiedź; Ola dzwoniła o 18:40 — oddzwoń; z Tomkiem nie rozmawiałeś od trzech tygodni”.

**Jak działa**
- Twoje konto jest połączone jako **drugie „połączone urządzenie”** (osobna sesja: `obserwacja-sesja.sqlite3`). Połączenie **tylko czyta**: Sebastian niczego z Twojego konta nie wysyła, **nie oznacza wiadomości jako przeczytanych** (rozmówcy nie widzą niebieskich ptaszków) i nie pokazuje Cię „online”.
- Zapisywane są rozmowy 1:1 (grupy — `WA_WATCH_GROUPS tak`), Twoje odpowiedzi (żeby wiedzieć, kto jeszcze czeka), połączenia przychodzące i **głosówki od innych zamienione na tekst** (lokalnie; nagranie nie jest przechowywane). Zdjęcia i dokumenty — tylko jako podpis/nazwa pliku.
- Zbieranie zaczyna się **od chwili połączenia** — wcześniejszej historii WhatsApp Sebastian nie pobiera.
- Wiadomości starsze niż `WA_WATCH_KEEP_DAYS` (90 dni) są codziennie usuwane z Maca.

**Skąd sugestie**
- **„Czeka na odpowiedź”** liczy program, nie model: ostatnia wiadomość w rozmowie jest od rozmówcy i ma ponad 2 godziny.
- **„Nieodebrane”**: połączenie przychodzące, po którym nie napisałeś do tej osoby. (Twoich połączeń wychodzących WhatsApp nie przekazuje połączonym urządzeniom — jeśli oddzwoniłeś bez pisania, sugestia może zostać.)
- **„Warto się odezwać”**: ktoś, z kim w ostatnich 60 dniach wymieniłeś ≥10 wiadomości, a od 14 dni jest cisza.
- Model (lokalny) streszcza każdą rozmowę jednym zdaniem i proponuje: *oddzwoń / odpisz / porozmawiaj / nic*. Bez modelu działają same reguły powyżej.

**Gdzie to widać**
- W **porannym przeglądzie** (tekst i głosówka wspominają najważniejsze rozmowy) oraz osobną wiadomością „📱 WhatsApp od wczoraj” z listami *Oddzwoń / Odpisz / Porozmawiaj / Warto się odezwać*.
- Na żądanie: `whatsapp` / `kto pisał` (ostatnia doba; `kto pisał 3 dni`), `do kogo` (same sugestie), `rozmowa Jan` (streszczenie rozmowy z daną osobą z 14 dni).
- W panelu: zakładka WhatsApp → „Twój WhatsApp”. W Terminalu: `python sebastian.py wa-watch podsumowanie`.
- **Tylko Ty** — rodzina (8b.8) nie ma dostępu do tych podsumowań.

**Włączenie**

```bash
python sebastian.py wa-watch login       # kod QR — skanujesz SWOIM telefonem (Połączone urządzenia → Połącz urządzenie)
python sebastian.py wa-watch login --kod # zamiast QR: kod do wpisania w telefonie
python sebastian.py wa-watch             # stan: połączenie, liczba wiadomości
python sebastian.py wa-set WA_WATCH_IGNORE "kurier, bank, 48600000000"   # kogo pomijać
python sebastian.py wa-watch off         # wstrzymaj (dane zostają) · wa-watch usun — odłącz i usuń wszystkie dane
```

**Ryzyko i prywatność — uczciwie.** To nieoficjalne połączenie (jak WhatsApp Web) na **Twoim głównym numerze**. Samo czytanie jest najmniej „podejrzanym” zachowaniem, ale ryzyko blokady przez WhatsApp nie jest zerowe. Rozmowy Twoich znajomych i klientów są zapisywane na Macu (`obserwacja.sqlite3`, FileVault!) i przetwarzane wyłącznie lokalnym modelem; nie trafiają do nauki ani do Open WebUI. Podsumowania przychodzą na czat z Sebastianem — czyli na telefon.

### 8b.7. Najczęstsze problemy

| Objaw | Działanie |
| --- | --- |
| Nie przyszedł poranny przegląd | `python sebastian.py wa-status` (ostatni przegląd, usługa, kolejka). Mac był uśpiony po `WA_BRIEF_LATEST`? Ręcznie: napisz „przegląd” albo panel → „Wyślij mi przegląd teraz” |
| „Połączenie z WhatsAppem wygasło” / baner w panelu | Usunięte z Połączonych urządzeń albo telefon Sebastiana długo offline: `python sebastian.py wa-login` |
| Sebastian nie odpowiada | `wa-status`: usługa działa i jest połączona? Piszesz z numeru `WA_OWNER_PHONE`? `tail -n 50 data/logs/whatsapp.log` |
| Przegląd bez głosówki | `python sebastian.py wa-test` (ffmpeg, głos). Brak głosu Piper: `python sebastian.py wa-voice` |
| „Nie umiem jeszcze odsłuchać” | `python -m pip install mlx-whisper` (pierwsze użycie pobiera model) |
| `brak libmagic` / `neonize` | `brew install libmagic` / `python -m pip install -r requirements-whatsapp.txt`, potem `wa-start` |
| Odpowiedzi trwają długo | Ollama jest zajęta (np. analiza dokumentu). Odpowiedź przyjdzie, gdy model się zwolni |
| Za dużo powiadomień | `cisza` na WhatsAppie albo `python sebastian.py wa-set WA_NOTICES nie` |
| Żona nie dostaje odpowiedzi | `wa-user` (czy jest na liście), `check` — Sebastian musi mieć osobny numer (8b.8) |
| Brak „📱 WhatsApp od wczoraj” | `python sebastian.py wa-watch` — połączone? Zbieranie działa od chwili połączenia; `WA_WATCH_IN_BRIEF` |
| „Straciłem wgląd w Twojego WhatsAppa” | Usunięte z Połączonych urządzeń albo telefon długo offline: `python sebastian.py wa-watch login` |
| Inny głos | `python sebastian.py wa-voice pl_PL-gosia-medium` (kobiecy) albo `wa-set WA_VOICE_ENGINE say` i `wa-set WA_SAY_VOICE Zosia`; tempo: `wa-set WA_VOICE_SPEED 1.1` (wolniej) |

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
├── learner_docs.py           Dokumenty: skany → uporządkowany PDF (od 2.2)
├── learner_docs_web.py       zakładka Dokumenty
├── whatsapp.py               WhatsApp: przegląd, głos, rozmowa, usługa (od 2.3)
├── whatsapp_link.py          WhatsApp: połączenie (neonize), filtr właściciela i rodziny
├── whatsapp_watch.py         WhatsApp: obserwacja Twojego konta — podsumowania, komu odpisać (od 2.4)
├── whatsapp_web.py           zakładka WhatsApp
├── openwebui_tool.py         narzędzie Open WebUI „moje sprawy”
├── openwebui_memory_tool.py  narzędzie Open WebUI „pamięć”
├── rollback.py               PRZESTARZAŁE (1.3) — nie używać, patrz 15.6
├── templates/  static/       panel (HTML, JS)
├── test_sebastian.py  test_learner.py  test_docs.py  test_whatsapp.py
├── requirements*.txt  install.command  start.command   (requirements-whatsapp.txt — od 2.3)
├── README.md  DOKUMENTACJA.md  ZACZNIJ_TUTAJ.txt
└── docs/
    ├── TESTY.md              co i jak przetestowano
    ├── aktualizacje/         instrukcje przejścia między wersjami (1.1 … 2.3)
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
    └── dokumenty/                  (od 2.2) skany i opracowania  🔒
        ├── dokumenty.sqlite3       postęp i odczyt każdej strony 🔒
        ├── wrzuc-tutaj/            folder do wrzucania skanów z Findera
        └── 0001-<nazwa>/           oryginal.pdf, skan.pdf, …_opracowanie.pdf, odczyt.md (rozdział 8a.6)
    └── whatsapp/                   (od 2.3) 🔒
        ├── whatsapp.json           ustawienia WA_*
        ├── whatsapp.sqlite3        kolejka, rozmowa, przeglądy 🔒
        ├── sesja.sqlite3           KLUCZE połączenia z WhatsAppem 🔒🔒
        ├── obserwacja-sesja.sqlite3  KLUCZE do TWOJEGO konta WhatsApp (2.4) 🔒🔒
        ├── obserwacja.sqlite3      Twoje rozmowy z WhatsAppa (2.4, usuwane po WA_WATCH_KEEP_DAYS) 🔒🔒
        ├── glosy/  nagrania/       głos Piper, głosówki
        └── wyslane/                tylko tryb próby (WA_TRANSPORT plik)
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
| `meta` | Znaczniki czasu i stany: ostatni skan, profil, Bieżące sprawy, logowanie Google (`login_at`), dostęp do Dysku (`drive_state`, `drive_notified`), błędy logowania do skrzynek (`mail_fail_<konto>`) |

Opracowane dokumenty są w kolejce nauki jako `files.id = doc:<nr>` (od 2.2).

**`data/dokumenty/dokumenty.sqlite3`** (od 2.2)

| Tabela | Zawartość |
| --- | --- |
| `jobs` | Dokumenty: nazwa, folder, plik źródłowy, rodzaj (`kind_hint`: auto/kw/ogolny, `profile`: kw/ogolny), `status` (`queued` → `prepare` → `pages` → `structure` → `build` → `done`; także `paused`, `error`), opis postępu, wielkości, `meta` (numer KW, sąd, podsumowanie, do wyjaśnienia, użyty OCR) |
| `pages` | Każda strona: tekst cyfrowy, OCR, rodzaj, obserwacje (JSON), odczyt końcowy, inne odczytania, pewność, czas, `verified` (sprawdzona ręcznie), `entries` (wpisy JSON; puste = do ponownego uporządkowania), dział |

**`data/whatsapp/whatsapp.sqlite3`** (od 2.3) — opis tabel: rozdział 8b.5. Polecenie `zrobione N` z WhatsAppa zapisuje w `data/sebastian.sqlite3` zdarzenie `whatsapp_done` w `events` (z wpisem w `undo_decisions`), a `zapamiętaj:` — notatkę w `knowledge_notes`.

---

## 11. Wszystkie polecenia

Każde polecenie uruchamiaj w folderze `sebastian-start` z aktywnym `.venv`: `python sebastian.py POLECENIE`.

### 11.1. Sebastian — konfiguracja

| Polecenie | Co robi |
| --- | --- |
| `init` | Tworzy `data/`, `config.json`, brakujące klucze panelu i bazę. Bezpieczne do ponownego użycia, niczego nie nadpisuje |
| `check` | **Pełne sprawdzenie systemu** (tylko odczyt): Ollama i modele, panel i poranek, nauka (praca w tle, dziennik, błędy, skrzynki), Dysk Google (scalenie, logowanie), Tesseract, git (czy dane nie są śledzone), FileVault, miejsce na dysku. Każdy problem ma podpowiedź, co zrobić |
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
| `learn-status` | Postęp: Dysk, wątki, archiwum per folder, załączniki, fakty, daty wyników, stan dostępu do Dysku |
| `learn-settings` | Wszystkie ustawienia (klucz API ukryty) |
| `learn-set KLUCZ WARTOŚĆ` | Zmiana ustawienia (`tak`/`nie`, liczby, listy po przecinku, JSON dla słowników) |
| `learn-drive` | **Dostęp do Dysku Google**: pokazuje stan i pozwala wybrać — 1) zaloguj ponownie, 2) wyłącz Dysk (wiedza z Dysku zostaje), 3) bez zmian. Bez menu: `learn-drive login` / `off` / `on` / `status` |
| `learn-login` | Samo logowanie do Dysku Google (to samo co `learn-drive login`) |
| `learn-mail-test [--account K]` | Test logowania i lista folderów do przeczytania |
| `learn-scan` | Odświeżenie listy dokumentów i wątków od razu |
| `learn-history --limit N` | Ręczne pobranie porcji archiwum |
| `learn-test ID` | Przeczytaj jedną pozycję i pokaż fakty (ID z zakładki Nauka albo z adresu pliku Google) |
| `learn-consolidate` | Odśwież Bieżące sprawy i Profil teraz |
| `learn-rag export` / `learn-rag sync [--limit N]` | Pliki faktów dla RAG / wysyłka do Open WebUI |
| `learn-retry` | Pozycje z błędem wracają do kolejki |
| `learn-import ŚCIEŻKA --merge` | **Dołącza** wiedzę dawnego Drive Learnera do działającej nauki (dokumenty, fakty, profil, teksty, logowanie). Nic z poczty nie ginie. Przed scaleniem robi kopię `data/learner/stan-przed-scaleniem-….sqlite3` |
| `learn-import ŚCIEŻKA [--force]` | Przeniesienie stanu Drive Learnera do **pustej** nauki. `--force` **zastępuje** obecny stan (utrata poczty z nauki). Nie używaj, gdy nauka już działa — użyj `--merge` |
| `learn-run` | Pętla nauki na pierwszym planie (normalnie uruchamia ją launchd) |

### 11.4. Dokumenty (od 2.2)

| Polecenie | Co robi |
| --- | --- |
| `doc-add PLIK [--nazwa N] [--typ auto\|kw\|ogolny]` | Kopiuje skan do `data/dokumenty/` i dodaje do kolejki |
| `doc-list` | Lista dokumentów: stan, postęp, szacunek czasu, wielkość wyniku |
| `doc-status NR` | Szczegóły: etap, rodzaje stron, strony do sprawdzenia, numer KW, ścieżka wyniku |
| `doc-run [NR]` | Analiza w tym oknie Terminala (gdy nauka nie działa w tle). Mac nie uśnie, Ctrl+C przerywa, a postęp zostaje |
| `doc-test PLIK [--strona N]` | Czyta jedną stronę i pokazuje wynik (do wyboru modelu). Nic nie zapisuje |
| `doc-pause NR` / `doc-resume NR` | Wstrzymanie / wznowienie (także po błędzie) |
| `doc-rebuild NR [pdf\|struktura\|strony]` | Ponownie: tylko PDF / porządkowanie wpisów / czytanie stron (strony sprawdzone ręcznie zostają) |
| `doc-export NR` | ZIP ze stronami do sprawdzenia (obrazy + odczyt) |
| `doc-remove NR [--tak]` | Usuwa dokument z folderem (pyta o potwierdzenie) |

### 11.5. WhatsApp (od 2.3)

| Polecenie | Co robi |
| --- | --- |
| `wa-setup` | Konfiguracja: Twój numer, imię, godzina przeglądu, wieczór; pobiera polski głos |
| `wa-login [--kod]` | Połączenie z WhatsAppem (kod QR albo kod do wpisania w telefonie), na końcu propozycja `wa-start` |
| `wa-start` / `wa-stop` | Usługa w tle (`pl.sebastian.whatsapp`) |
| `wa-status` | Stan: połączenie, ostatni przegląd, głos, kolejka, wyciszenie |
| `wa-test` | Sprawdzenie (biblioteki, ffmpeg, głos, słuch, model, usługa) i próbna głosówka |
| `wa-brief [--rodzaj rano\|wieczor\|tydzien] [--podglad]` | Złóż przegląd: wyślij albo tylko pokaż i odtwórz na Macu |
| `wa-send "tekst"` | Wyślij sobie wiadomość (np. do sprawdzenia połączenia) |
| `wa-chat` | Rozmowa z Sebastianem w Terminalu (bez WhatsAppa) |
| `wa-voice [NAZWA]` | Pobierz głos Piper (domyślnie `pl_PL-darkman-medium`; np. `pl_PL-gosia-medium`) |
| `wa-settings` / `wa-set KLUCZ WARTOŚĆ` | Ustawienia `WA_*` (12.3) |
| `wa-logout` | Odłącz Sebastiana od WhatsAppa i usuń sesję |
| `wa-user [lista\|dodaj\|usun] [NUMER]` | (2.4) Rodzina: kto jeszcze może pisać do Sebastiana (tylko sprawy prywatne), z osobnym przeglądem |
| `wa-watch [status\|login\|podsumowanie\|off\|on\|usun]` | (2.4) Obserwacja Twojego WhatsAppa: połączenie (QR / `--kod`), podsumowanie (`--godzin N`), wstrzymanie, usunięcie danych |
| `wa-run` | Pętla usługi na pierwszym planie (normalnie uruchamia ją launchd) |

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

**Dokumenty (od 2.2)**

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `DOC_ENABLED` | `tak` | Usługa nauki opracowuje dokumenty z kolejki |
| `DOC_VISION_MODEL` | `qwen2.5vl:7b` | Model wizyjny (musi być w `ollama list`) |
| `DOC_VISION_MODEL_2` | puste | Drugi model do podwójnego czytania pisma; puste = ten sam model, inne polecenie |
| `DOC_DOUBLE_READ` | `tak` | Pismo ręczne czytane dwa razy; różnice oznaczane jako niepewne |
| `DOC_PAUSE_LEARNING` | `tak` | Nauka z poczty czeka, gdy trwa analiza dokumentu |
| `DOC_READ_DPI` | `200` | Rozdzielczość, w jakiej model ogląda stronę |
| `DOC_READ_WIDTH` | `1600` | Do tej szerokości (px) powiększane są pasy z pismem |
| `DOC_MAX_STRIPS` | `4` | Na ile pasów najwyżej dzielona jest strona |
| `DOC_SCAN_DPI` | `200` | Rozdzielczość skanów w wyniku (mniej = mniejszy plik) |
| `DOC_JPEG_QUALITY` | `75` | Jakość JPEG skanów |
| `DOC_KEEP_COLOR` | `tak` | Kolor zostaje na stronach z kolorem (czerwone wykreślenia, pieczęcie) |
| `DOC_OPTIMIZE` | `2` | Kompresja ocrmypdf: 1 bezstratna, 2 zalecana, 3 najmocniejsza |
| `DOC_CLEAN_FINAL` | `nie` | Czyszczenie tła także w skanie wynikowym (może osłabić blade pismo) |
| `DOC_OCR_LANGS` | `pol+deu+eng` | Języki Tesseracta (używane tylko zainstalowane) |
| `DOC_NUM_CTX` | `12288` | Kontekst modelu wizyjnego |
| `DOC_KEEP_ALIVE` | `10m` | Jak długo Ollama trzyma model wizyjny w pamięci |
| `DOC_CHECK_BELOW` | `0.85` | Strony z mniejszą pewnością trafiają „do sprawdzenia” |
| `DOC_SCAN_LABELS` | `tak` | Mały podpis „Skan — strona N · « spis treści” na skanach |
| `DOC_TO_LEARNING` | `tak` | Opracowany dokument trafia do nauki |
| `DOC_SCOPE` | `private` | Zakres w nauce (wpływa na RAG: `RAG_SCOPES`) |
| `DOC_MAX_UPLOAD_MB` | `3000` | Największy plik przez panel (większe: folder `wrzuc-tutaj`) |

### 12.3. `data/whatsapp/whatsapp.json` (WhatsApp, od 2.3)

Zmiana: `python sebastian.py wa-set KLUCZ WARTOŚĆ`, potem `wa-start` (przeładowanie usługi).

| Klucz | Domyślnie | Znaczenie |
| --- | --- | --- |
| `WA_ENABLED` | `nie` → `tak` po `wa-setup` | Włącza WhatsApp |
| `WA_TRANSPORT` | `linked` | `linked` = WhatsApp (połączone urządzenie); `plik` = próba bez wysyłki (`data/whatsapp/wyslane/`) |
| `WA_OWNER_PHONE` | — | Twój numer z kierunkowym (np. `48600111222`). Jedyny, któremu Sebastian odpowiada i do którego pisze |
| `WA_OWNER_NAME` | puste | Imię w powitaniu; puste = pierwsze słowo `OWNER_NAME` nauki |
| `WA_MODEL` | puste | Model do przeglądów i rozmów; puste = model Sebastiana |
| `WA_BRIEF` / `WA_BRIEF_TIME` / `WA_BRIEF_LATEST` | `tak` / `07:00` / `11:30` | Poranny przegląd; po `LATEST` już nie przychodzi |
| `WA_BRIEF_DAYS` | `1,2,3,4,5,6,7` | Dni tygodnia (1 = poniedziałek). Np. tylko robocze: `1,2,3,4,5` |
| `WA_EVENING` / `WA_EVENING_TIME` | `nie` / `20:30` | Wieczorne podsumowanie |
| `WA_WEEKLY` / `WA_WEEKLY_DAY` / `WA_WEEKLY_TIME` | `nie` / `7` / `18:00` | Tygodniowe podsumowanie |
| `WA_VOICE` | `tak` | Głosówki w przeglądach |
| `WA_VOICE_ENGINE` | `auto` | `piper` / `say` / `auto` (Piper, gdy jest głos) |
| `WA_PIPER_VOICE` | `pl_PL-darkman-medium` | Głos Piper (pobierz: `wa-voice NAZWA`) |
| `WA_SAY_VOICE` | `Zosia` | Głos macOS przy `say` |
| `WA_VOICE_SPEED` | `1.0` | Tempo Piper (>1 wolniej) |
| `WA_VOICE_MAX_WORDS` | `260` | Długość głosówki (ok. 1,5–2 min) |
| `WA_SCOPES` | `private, work` | Z których skrzynek sprawy trafiają na WhatsApp |
| `WA_CHAT` | `tak` | Odpowiadanie na pytania (komendy działają zawsze) |
| `WA_TRANSCRIBE` / `WA_WHISPER_MODEL` | `tak` / `mlx-community/whisper-large-v3-turbo` | Rozumienie Twoich głosówek |
| `WA_REPLY_VOICE` | `tak` | Na głosówkę odpowiedź także głosówką |
| `WA_NOTICES` | `tak` | Powiadomienia systemowe na WhatsApp |
| `WA_QUIET` | `22:00-07:00` | Cisza nocna dla powiadomień (przychodzą po jej końcu) |
| `WA_USERS` | — | (2.4) Rodzina — tylko przez `wa-user` |
| `WA_WATCH` | `nie` | (2.4) Obserwacja Twojego WhatsAppa (włącza `wa-watch login`) |
| `WA_WATCH_PHONE` | — | Twój obserwowany numer (ustawia `wa-watch login`) |
| `WA_WATCH_GROUPS` | `nie` | Także grupy |
| `WA_WATCH_TRANSCRIBE` | `tak` | Głosówki od innych → tekst (lokalnie) |
| `WA_WATCH_KEEP_DAYS` | `90` | Po ilu dniach wiadomości są usuwane z Maca |
| `WA_WATCH_IGNORE` | — | Numery/nazwy do pomijania (lista po przecinku) |
| `WA_WATCH_IN_BRIEF` | `tak` | Podsumowanie WhatsAppa w porannym przeglądzie |

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
- `data/whatsapp/obserwacja-sesja.sqlite3` to klucze do **Twojego** konta WhatsApp, a `obserwacja.sqlite3` — Twoje rozmowy (od 2.4). Przy podejrzeniu wycieku: `wa-watch usun` i w telefonie usuń urządzenie.
- `data/whatsapp/sesja.sqlite3` to klucze połączenia z WhatsAppem. Kto ma ten plik, może pisać jako konto Sebastiana. Przy podejrzeniu wycieku: `wa-logout` i w telefonie usuń urządzenie z „Połączonych urządzeń”. Przegląd i odpowiedzi trafiają na telefon (rozdział 8b.6).
- `data/dokumenty/` zawiera pełne skany (np. księgi wieczyste z PESEL-ami i adresami). Traktuj je jak resztę `data/`. ZIP „do sprawdzenia” powstaje tylko na żądanie. Zastanów się, komu go przekazujesz.
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
4. `python sebastian.py morning-setup`, `python sebastian.py learn-mail-test`, `python sebastian.py learn-drive login` (jeśli Dysk ma być czytany), `python sebastian.py learn-start`, na koniec `python sebastian.py check`.
5. Panel będzie miał ten sam klucz (`panel.token` jest w `data/`).

### 14.3. Aktualizacje

Aktualizacje przychodzą jako plik `Sebastian_aktualizacja_X_Y.py` albo paczka ZIP z instrukcją w `docs/aktualizacje/`. Zasady:

- Uruchamiaj w folderze `sebastian-start` z aktywnym `.venv`.
- Aktualizator sprawdza wersję, robi kopię w `backups/aktualizacja-X.Y-…`, podmienia pliki, testuje uruchomienie i w razie błędu sam przywraca poprzednią wersję. Komunikat **STOP** oznacza: nic nie zmieniono albo przywrócono kopię. Przeczytaj go i nie kontynuuj na ślepo.
- Po aktualizacji: odśwież panel (Command + R), sprawdź wersję w nagłówku, potem `git add . && git commit -m "Sebastian X.Y" && git push`.

### 14.4. Rozwiązywanie problemów

| Objaw | Przyczyna / działanie |
| --- | --- |
| `learn-start`: `launchctl bootstrap … status 5` | macOS jeszcze zamykał poprzednią naukę. Od 2.1.2 program sam czeka. W starszej wersji: `learn-stop`, potem `learn-start` |
| Dysk w `learn-status`: 0 przeczytanych, choć Drive Learner przeczytał Dysk | `python sebastian.py learn-import ~/drive-learner --merge` (nie `--force`!) |
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
| Nauka: „Logowanie Google wygasło” / „RefreshError” | `python sebastian.py learn-drive`: zaloguj ponownie albo wyłącz Dysk. Poczta działa dalej w obu przypadkach |
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
| Dokumenty: dokument nie rusza / jest wolny / ma słaby odczyt | Rozdział 8a.8 |
| WhatsApp: brak przeglądu / brak odpowiedzi / brak głosówki | Rozdział 8b.7, `python sebastian.py wa-status`, `wa-test` |
| Komunikat aktualizatora „STOP” | Nic nie zmieniono albo przywrócono kopię. Skopiuj komunikat i skonsultuj |

**Pierwszy krok przy każdym problemie:** `python sebastian.py check`. Pokazuje, co nie działa, i podpowiada polecenie naprawcze.

Przy prośbie o pomoc podaj: wynik `check`, dokładne polecenie, komunikat błędu i ostatnie ~30 linii odpowiedniego logu. **Bez** haseł, tokenów i treści maili.

---

## 15. Dla programisty — budowa kodu i zasady zmian

### 15.1. Wzorce w kodzie

- **Migracje tylko dodające.** Każdy moduł ma `migrate(c)`, które robi `CREATE TABLE IF NOT EXISTS` i `ALTER TABLE … ADD COLUMN` po sprawdzeniu `PRAGMA table_info`. Nigdy nie usuwaj ani nie zmieniaj znaczenia istniejących kolumn: stara wersja kodu musi dalej działać na nowszej bazie.
- **Rejestracja tras.** Moduły panelu mają `register(app, s)`, gdzie `s` to moduł `sebastian` (dostęp do `db()`, `config()`, `DATA`, `now()`). Logowanie i CSRF dla wszystkich tras zapewnia `protect()` w `make_app()`. Formularze POST muszą wysyłać `csrf`.
- **Nauka** łączy się z Sebastianem przez `learner.bind(s)`. Moduł nie ma efektów ubocznych przy imporcie, bo panel też go importuje. Sygnały i logowanie konfiguruje dopiero `run()`.
- **Polecenia `learn-*` i `check`** są obsługiwane przed blokadą `job.lock`, więc nie blokują poranka. Pozostałe polecenia biorą blokadę.
- **Dostęp do Dysku** obsługuje klasa `Drive` w `learner.py`. Nie ponawia logowania przy każdym wątku: próbuje po zmianie `token.json` albo co `RETRY_HOURS`. Stan zapisuje w `meta.drive_state` (`ok` / `expired` / `off`), a powiadomienie wysyła najwyżej raz na dobę (`meta.drive_notified`).
- **Diagnostyka `check`** (`learner.cmd_check`) tylko czyta. Każdy nowy element systemu powinien dostać w niej swoją kontrolę z podpowiedzią naprawy (Dokumenty: `learner_docs.check`).
- **Dokumenty** (`learner_docs.py`) mają własną bazę `data/dokumenty/dokumenty.sqlite3` i etapy wznawialne (`process()` → `prepare` / `read_pages` / `structure` / `build`). Każdy etap zwraca `False`, gdy trzeba poczekać (brak modelu, wstrzymanie, poranek, `STOP`) — wtedy nic nie jest oznaczane jako zrobione. Wątek `worker()` działa w procesie nauki. Blokada `fcntl` na `.praca.lock` pilnuje, by `doc-run` i usługa nie pracowały jednocześnie. `busy()` mówi nauce, by poczekała. Zasada bezpieczeństwa: model wizyjny tylko przepisuje, model tekstowy tylko porządkuje, a każdy wpis musi mieć cytat sprawdzany funkcją `quote_found()`. Numer KW i sąd są wyszukiwane wyrażeniami regularnymi, nie przez model.
- **WhatsApp** (`whatsapp.py`) jest niezależny od transportu: `FileTransport` (próba) i `whatsapp_link.LinkedTransport` (neonize) mają te same metody (`start`, `stop`, `send_text`, `send_voice`, `typing`, `connected`). Biblioteka WhatsApp wywołuje `on_message` z własnego wątku, więc tam jest tylko `queue.put`, a całą pracę robi pętla `tick()`. Wszystko, co wychodzi, przechodzi przez tabelę `outbox`, dzięki czemu panel i inne procesy (np. `learner.notify` → `whatsapp.notice`) mogą bezpiecznie zlecać wysyłkę. Filtr „tylko właściciel i rodzina z listy” jest w `LinkedTransport.parse()` i ma testy na prawdziwych strukturach neonize. **Rozmówca** (2.4) jest w `contextvars` (`as_user()`): od niego zależą zakresy danych (`allowed_scopes()`), wybór komend, adresat w `outbox.to_phone` i treść promptów (`who_line()`) — każda nowa funkcja rozmowy musi to respektować. **Obserwacja** (`whatsapp_watch.Watcher`) to osobna sesja tylko do odbioru: nigdy nie wołaj na niej `send_*`, `mark_read` ani presence; flagi „czeka”/„nieodebrane” liczy `chats()` z kolejności wiadomości, model tylko streszcza. Zmiany danych z WhatsAppa to tylko `zrobione N` (jak szybki przycisk: `events` + `undo_decisions`) i `zapamiętaj:`.
- **Duże pliki w panelu:** ogólny limit żądania to 6 MB. Tylko trasa `docs_upload` podnosi go w `protect()` (`request.max_content_length`) przed odczytem formularza (CSRF).
- **IMAP:** zawsze `select(…, readonly=True)` i `BODY.PEEK`. Testy to sprawdzają.
- **AI:** Sebastian używa `format` ze schematem JSON i walidacji (`validate_result`, terminy muszą mieć cytat z treści). Nauka używa `format: json` i odrzuca nieczytelne odpowiedzi. Dla modeli „myślących” (qwen3, deepseek-r1…) wysyłane jest `think: false`.
- **Podpis wątku (`files.sig`)** decyduje o ponownym czytaniu. Zmiana sposobu liczenia podpisu powoduje ponowne czytanie **wszystkich** wątków. Zmieniaj go tak, jak 2.1: tylko dla wątków, których zmiana dotyczy.
- **Kod jest w języku angielskim, komunikaty dla użytkownika po polsku.**

### 15.2. Testy

```bash
python -m pip install -r requirements-test.txt
python -m unittest test_sebastian.py test_learner.py test_docs.py test_whatsapp.py -v
```

Testy używają tymczasowego katalogu danych, symulowanego IMAP i symulowanej Ollamy. Nie dotykają prawdziwych skrzynek. Testy załączników i dokumentów wymagają `requirements-learner.txt` (testy dokumentów generują własny „skan” i nie potrzebują ocrmypdf ani modelu wizyjnego). Testy WhatsApp nie łączą się z WhatsAppem. Filtr nadawcy sprawdzają na strukturach neonize, gdy biblioteka jest zainstalowana, a konwersję głosu, gdy jest ffmpeg; w przeciwnym razie te testy są pomijane. Każda zmiana powinna dodać test do odpowiedniego pliku. Opis zakresu testów jest w `docs/TESTY.md`.

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

Wzorzec aktualizatora (zob. 1.4, 2.1, 2.1.1–2.1.3, 2.2, 2.3):

- jeden plik `Sebastian_aktualizacja_X_Y.py` z zawartością nowych plików,
- sprawdzenie skrótów SHA-256 plików poprzedniej wersji (odmowa przy ręcznych zmianach, `--force` świadomie),
- zatrzymanie nauki **z odczekaniem, aż launchd ją naprawdę zwolni** (inaczej `bootstrap` zwraca kod 5), kopia plików i bazy w `backups/`, atomowa podmiana (`os.replace`),
- test importu i `learn-status`, przywrócenie kopii przy błędzie,
- przeładowanie panelu (`launchctl kickstart -k`) i wznowienie nauki,
- (od 2.2) doinstalowanie brakujących bibliotek z `requirements-learner.txt` **przed** podmianą plików oraz — za zgodą użytkownika — narzędzi zewnętrznych (`brew install ocrmypdf`, `ollama pull …`) **po** udanej aktualizacji, tak żeby ich błąd nie cofał aktualizacji.

### 15.5. Git

- Gałąź `main`. Commity opisowe po polsku, np. „Sebastian 2.1 – załączniki”.
- **Przed `git add`:** `git status`, czy nie ma danych (13.1).
- Nie dodawaj plików `*.bak-*`, kopii folderów ani paczek ZIP.

### 15.6. Znane ograniczenia i dług techniczny

- `rollback.py` (z 1.3) jest przestarzały i ma błąd (`stat().mtime` zamiast `st_mtime`). **Nie używać.** Do przywracania służą kopie z `backups/` i instrukcje w `docs/aktualizacje/`. Do usunięcia w kolejnej wersji.
- Gmail bez OAuth: wymaga hasła aplikacji (dostępnego tylko przy 2FA).
- Dysk Google: aplikacja w trybie „Testowanie”, logowanie co 7 dni. Obsługę wygaśnięcia opisuje rozdział 8.9. Alternatywa na przyszłość: publikacja aplikacji w Google Cloud (wymaga strony WWW i polityki prywatności).
- Panel analizuje tylko treść maila do 12 000 znaków. Załączniki czyta wyłącznie nauka.
- Narzędzie pamięci w Open WebUI szuka słów (BM25), nie znaczeń. Wyszukiwanie wektorowe zapewniają bazy Knowledge (9.3).
- Ta sama wiadomość w dwóch folderach może być w panelu dwoma rekordami (nauka deduplikuje po `Message-ID`).
- Brak CC/BCC i „odpowiedz wszystkim”. Kalendarz bez synchronizacji na żywo i bez API map.
- Nauka czyta wątek ponownie po każdej nowej odpowiedzi. Przy bardzo długich wątkach to koszt czasu.
- Akta spraw i osób (zestawienia per osoba lub sprawa z faktów i tekstów) to kolejny planowany etap. Dane są już zbierane (`teksty/`, `facts` ze źródłem i datą).
- WhatsApp: połączenie przez nieoficjalną bibliotekę (`neonize==0.5.2`, przypięta wersja — przed zmianą wersji sprawdź testy `LinkFilterTests` i parowanie na Macu). Oficjalne WhatsApp Business Cloud API odrzucono świadomie: wiadomości inicjowane przez firmę wymagają płatnych, zatwierdzanych szablonów, odbiór wymaga publicznego adresu (tunelu) do Maca, a treść przechodzi przez serwery Meta bez szyfrowania end-to-end do Maca. Telefonów (połączeń głosowych) Sebastian nie wykonuje.
- Dokumenty: model wizyjny był testowany w kodzie na symulowanych odpowiedziach. Jakość odczytu konkretnych skanów zależy od modelu, więc przed dużym dokumentem warto zrobić `doc-test` na kilku trudnych stronach. Wykreślenie zapisane jako osobny wpis na innej stronie nie zawsze jest łączone z pierwotnym wpisem (8a.7). Niewidoczna warstwa tekstu na skanach pisma ręcznego nie jest dopasowana do położenia słów (wyszukiwanie znajdzie stronę, ale nie podświetli dokładnego miejsca).

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
| 2.1.2 | 15.10.2026 | Polecenie `check` (pełna diagnostyka), `learn-import --merge` (scalenie Drive Learnera z działającą nauką), niezawodne `learn-start`/`learn-stop` (czekanie na macOS) |
| 2.1.3 | 19.10.2026 | Wygaśnięcie logowania do Dysku: jeden komunikat zamiast wpisu przy każdym wątku, baner w panelu, polecenie `learn-drive` z wyborem (zaloguj ponownie / wyłącz Dysk) |
| 2.2 | 19.10.2026 | **Dokumenty**: duże skany (druk, maszynopis, pismo ręczne, Grundbuch) → mały PDF ze spisem treści i linkami; model wizyjny z podwójnym czytaniem pisma, wpisy KW wg działów z weryfikacją cytatów, sprawdzanie i poprawki stron w panelu, praca wznawialna w tle (1–2 dni), przekazanie do nauki; polecenia `doc-*`, sekcja „6. Dokumenty” w `check` |
| 2.3 | 20.10.2026 | **WhatsApp**: poranny przegląd z głosówką („Hej Andrzej!”, polski głos Piper, lokalnie), rozmowa i komendy (zadania, zrobione N, pilne, poczta, kalendarz, dokumenty, zapamiętaj, cisza), rozumienie głosówek (mlx-whisper), powiadomienia z ciszą nocną, opcjonalnie wieczór i tydzień; zakładka WhatsApp, polecenia `wa-*`, sekcja „7. WhatsApp” w `check` |
| 2.4 | 20.10.2026 | **WhatsApp — rodzina i Twoje konto**: żona (i inne osoby z `wa-user`) pisze do Sebastiana i dostaje własny przegląd — tylko sprawy prywatne; obserwacja Twojego WhatsAppa (tylko odczyt): kto pisał, o czym, komu odpisać, do kogo oddzwonić, z kim dawno nie rozmawiałeś — w przeglądzie i na żądanie (`whatsapp`, `do kogo`, `rozmowa Jan`) |

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
| **Model wizyjny** | Model, który dostaje obraz strony (nie tylko tekst) i „widzi” układ, pismo ręczne, przekreślenia, pieczęcie |
| **OCR** | Rozpoznawanie tekstu ze skanu (Tesseract). Dobre dla druku, słabe dla pisma ręcznego |
| **Opracowanie (Dokumenty)** | Wynikowy PDF: spis treści, wpisy, odczyt i skany z linkami |
| **Do sprawdzenia** | Strona z niepewnym odczytem — do porównania ze skanem w panelu |
| **Połączone urządzenie** | Komputer połączony z kontem WhatsApp (jak WhatsApp Web). Tak łączy się Sebastian |
| **Głosówka (PTT)** | Wiadomość głosowa WhatsApp. Sebastian nagrywa ją lokalnie (Piper) w formacie OGG/Opus |
| **Przegląd** | Poranna (albo wieczorna/tygodniowa) wiadomość Sebastiana: tekst + głosówka |
| **Embedding / bge-m3** | Zamiana tekstu na wektor do wyszukiwania po znaczeniu; bge-m3 dobrze rozumie polski |
| **Zakres (scope)** | `private` (Gmail, Murena) albo `work` (Partners); `drive` dla Dysku w nauce |
| **LaunchAgent** | Zadanie macOS uruchamiane po zalogowaniu użytkownika |
| **Pęk kluczy** | Systemowy sejf haseł macOS (Keychain) |
| **Ollama** | Program uruchamiający modele AI lokalnie na Macu |
| **Open WebUI** | Aplikacja do czatu z lokalnymi modelami (w Dockerze) |
| **OCR** | Rozpoznawanie tekstu ze skanów i zdjęć (Tesseract) |
