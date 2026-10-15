# Sebastian 2.0 — Sebastian + Drive Learner + nauka z całej poczty

Wersja 2.0 łączy dwa dotychczasowe programy w jeden:

- **Sebastian** (panel, decyzje, zadania, odpowiedzi, kalendarz, pamięć dla Open WebUI) działa bez zmian.
- **Nauka** (dawny Drive Learner) jest teraz częścią Sebastiana i czyta trzy źródła:
  1. **Dysk Google** — tak jak dotąd; cały dotychczasowy postęp przechodzi do Sebastiana.
  2. **Pocztę z Sebastiana** — nowe maile, Twoje decyzje i komentarze z panelu, notatki, eksporty WhatsApp, zapisy narad.
  3. **Całe archiwum skrzynek**. Sebastian sam dociąga w tle starsze maile ze wszystkich folderów, także **Wysłane**. Działa tylko do odczytu: nic nie zmienia się na serwerze, a maile nie są oznaczane jako przeczytane. Archiwum trafia wyłącznie do bazy nauki, nie do kolejki decyzji w panelu.

Wyniki znajdziesz w nowej zakładce **Nauka** w panelu oraz w folderze `data/learner/wyniki/`:

| Plik | Co zawiera |
| --- | --- |
| `Biezace_sprawy.md` | Co się teraz dzieje: sprawy z ostatnich 30 dni, stan, następny krok, terminy, z kim, plus otwarte zadania z panelu |
| `Profil_wiedzy.md` | Trwała wiedza: kim jesteś, praca, ludzie, cele, styl pracy i **styl komunikacji** (na podstawie Twoich wysłanych maili). Bieżące sprawy są na górze. |

**Jak to działa.** Maile są składane w **wątki**. Wątek jest czytany w całości: Twoje odpowiedzi są oznaczone „WYSŁANE PRZEZE MNIE”, a decyzje z panelu dołączone. Gdy w wątku pojawi się nowa wiadomość, wątek zostaje przeczytany ponownie. Najpierw idą wątki z ostatnich 60 dni, potem coraz starsze. Newslettery, adresy „no-reply”, maile oznaczone w panelu jako *Pomiń* oraz kategoria *newsletter/podejrzane* są pomijane.

Model nie jest trenowany. Buduje notatki, które dostaje przy rozmowie. Wszystko zostaje na Macu.

---

## 1. Kopia bezpieczeństwa (2 minuty)

Terminal, w folderze Sebastiana:

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python sebastian.py backup
cp -R ~/SebastianSystem/sebastian-start ~/SebastianSystem/sebastian-start-kopia-1.4
```

Druga linia to pełna kopia folderu. Jeśli coś pójdzie nie tak, wrócisz do niej jednym poleceniem (punkt 11).

## 2. Wgranie wersji 2.0

Pobierz `Sebastian_2_0.zip` do Pobranych, potem:

```bash
unzip -o ~/Downloads/Sebastian_2_0.zip -d ~/SebastianSystem
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python -m pip install -r requirements-learner.txt
launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel
```

Paczka zawiera wyłącznie kod. Folder `data/` z Twoimi mailami, decyzjami i ustawieniami **nie jest ruszany**. Ostatnia linia przeładowuje panel. Odśwież http://127.0.0.1:8765, w nagłówku powinno być **SEBASTIAN 2.0** i nowa zakładka **Nauka**.

Do OCR (tekst ze zdjęć i skanów) potrzebny jest Tesseract. Jeśli działał w Drive Learnerze, już go masz. Jeśli nie: `brew install tesseract tesseract-lang`.

## 3. Przeniesienie Drive Learnera

```bash
python sebastian.py learn-import ~/drive-learner
```

Polecenie:

- zatrzymuje dawną usługę Drive Learnera,
- kopiuje jej stan (przeczytane pliki, fakty, profil, pełne teksty, bazę RAG, logowanie Google i `credentials.json`) do `data/learner/`,
- przenosi ustawienia z `config.py`.

Dawny folder `~/drive-learner` zostaje nietknięty. Usuń go dopiero, gdy sprawdzisz, że wszystko działa.

## 4. Sprawdź, o kim zbierana jest wiedza

```bash
python sebastian.py learn-settings
```

Najważniejsze są `OWNER_NAME` i `OWNER_CONTEXT`. Muszą opisywać osobę, **do której należą skrzynki i Dysk**, dokładnie tak, jak występuje w dokumentach. Inaczej profil pomiesza dwie osoby. Zmiana:

```bash
python sebastian.py learn-set OWNER_NAME "Andrzej Kwiatkowski"
python sebastian.py learn-set OWNER_CONTEXT "Planer finansowy w inPartners (Kraków), szef struktury. Sprawy prywatne i rodzinne. Pisze po polsku."
```

Sprawdź też `MODEL`. Musi być dokładną nazwą z `ollama list`. Przeniesione foldery pomijane na Dysku (`EXCLUDE_PATHS`) obowiązują też dla poczty, jeśli pasują do ścieżki wątku, np. `Poczta firmowa`.

## 5. Test skrzynek

```bash
python sebastian.py learn-mail-test
```

Dla każdego konta zobaczysz foldery, które nauka przeczyta, i liczbę wiadomości. Kosz, spam i szkice są pomijane. W Gmailu czytany jest tylko folder „Wszystkie”, bo zawiera całą pocztę bez dublowania.

Jeśli macOS zapyta o dostęp do Pęku kluczy, kliknij **Zawsze pozwalaj**. Dzięki temu nauka w tle zaloguje się bez Ciebie. Hasła są te same, które Sebastian już ma, niczego nie wpisujesz drugi raz.

## 6. Start pracy w tle

```bash
python sebastian.py learn-start
```

Od tej chwili nauka pracuje sama: nie usypia Maca, startuje po zalogowaniu, wraca w to samo miejsce po restarcie. Gdy rano trwa poranna analiza Sebastiana, nauka czeka, żeby nie zajmować Ollamy.

Podgląd postępu:

- w panelu: zakładka **Nauka**,
- w Terminalu: `python sebastian.py learn-status`,
- dziennik na żywo: `tail -f data/logs/learner.log`.

## 7. Czego się spodziewać

- **Pierwsze godziny:** wątki z ostatnich 60 dni, potem pierwsza wersja **Bieżących spraw**, która odświeża się co ~3 godziny, gdy przybywa faktów.
- **Kolejne dni:** archiwum, od najnowszych do najstarszych. Jeden wątek to od kilkudziesięciu sekund do kilku minut. Kilka tysięcy wątków to kilka dni do dwóch tygodni pracy.
- **Profil wiedzy** odświeża się co 6 godzin.
- **Nowe maile:** Sebastian pobiera je rano, a nauka czyta je w ciągu kwadransa. Nowe wiadomości w folderach, których Sebastian nie obserwuje, nauka dociąga sama co kilka godzin.

Jeśli wolisz zacząć od nowszej historii, ustaw np. `python sebastian.py learn-set MAIL_HISTORY_SINCE 2022-01-01` (puste = całe archiwum).

## 8. Open WebUI (opcjonalnie)

Jak w Drive Learnerze, tylko ustawienia wpisujesz poleceniem zamiast w `config.py`. ID baz wiedzy to końcówka adresu bazy w Open WebUI.

```bash
python sebastian.py learn-set OPENWEBUI_URL "http://localhost:3000"
python sebastian.py learn-set OPENWEBUI_API_KEY "sk-…"
python sebastian.py learn-set OPENWEBUI_KNOWLEDGE_ID "…"      # Profil wiedzy + Bieżące sprawy
python sebastian.py learn-set RAG_FACTS_KNOWLEDGE_ID "…"      # fakty
python sebastian.py learn-set RAG_TEXTS_KNOWLEDGE_ID "…"      # pełne teksty
python sebastian.py learn-start                               # przeładowanie
```

Domyślnie do RAG trafiają fakty i teksty z Dysku, poczty prywatnej i firmowej. Aby np. nie wysyłać poczty firmowej: `python sebastian.py learn-set RAG_SCOPES "drive, private"`. Narzędzia Sebastiana dla Open WebUI (`moje_sprawy`, pamięć) działają jak dotąd.

## 9. Raz w tygodniu: logowanie do Dysku Google

Aplikacja Google jest w trybie „Testowanie”, więc logowanie wygasa po 7 dniach. Dzień wcześniej Mac pokaże powiadomienie. Wtedy:

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python sebastian.py learn-login
```

Gdy logowanie wygaśnie, **poczta pracuje dalej**, czeka tylko Dysk.

## 10. Wszystkie polecenia nauki

| Polecenie | Co robi |
| --- | --- |
| `learn-start` / `learn-stop` | Włącza / wyłącza naukę w tle (po zmianie ustawień: `learn-start`) |
| `learn-status` | Postęp: Dysk, wątki, archiwum per folder, fakty |
| `learn-settings` / `learn-set KLUCZ WARTOŚĆ` | Pokazuje / zmienia ustawienia (`tak/nie`, liczby, listy po przecinku) |
| `learn-mail-test [--account partners]` | Sprawdza logowanie i foldery skrzynek |
| `learn-history --limit 50` | Ręcznie dociąga porcję archiwum (na próbę) |
| `learn-scan` | Odświeża listę dokumentów i wątków od razu |
| `learn-test ID` | Czyta jedną pozycję i pokazuje fakty (ID z zakładki Nauka) |
| `learn-consolidate` | Odświeża Bieżące sprawy i Profil wiedzy teraz |
| `learn-rag export` / `learn-rag sync` | Pliki RAG / wysyłka do Open WebUI |
| `learn-retry` | Ponawia pozycje z błędem |
| `learn-login` | Logowanie do Dysku Google |
| `learn-import ŚCIEŻKA` | Przeniesienie dawnego Drive Learnera |

## 11. Gdyby coś poszło nie tak

```bash
python sebastian.py learn-stop
cd ~/SebastianSystem
mv sebastian-start sebastian-start-2.0-nieudane
mv sebastian-start-kopia-1.4 sebastian-start
launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel
```

Wracasz wtedy do 1.4 ze stanem sprzed aktualizacji. Dawny Drive Learner można włączyć ponownie jego własnym `./usluga.sh start`.

## 12. Prywatność

- Archiwum maili, pełne teksty i fakty leżą w `data/learner/` na Macu. Nie wysyłamy ich nigdzie poza Twój lokalny Open WebUI (jeśli go skonfigurujesz).
- Model ma zakaz zapisywania numerów PESEL, kont, haseł, adresów, kwot majątku i informacji o zdrowiu innych osób. W `teksty/` są jednak pełne treści, także maili klientów. Włącz FileVault.
- `data/`, `backups/`, klucze i `credentials.json` są w `.gitignore`. **Nigdy nie wysyłaj ich na GitHub**, nawet do prywatnego repozytorium.

## 13. Czyste repozytorium na GitHub

Poprzednie repozytorium zawierało w historii folder `data/` z mailami. Najczyściej będzie zacząć od nowa: nowe repo, jeden commit bez danych.

1. Na GitHubie utwórz **nowe, prywatne** repozytorium, np. `sebastian`, bez README.
2. W Terminalu:

```bash
cd ~/SebastianSystem/sebastian-start
rm -rf .git
git init -b main
git add .
git status
```

3. Sprawdź listę z `git status`. **Nie może** być na niej `data/`, `backups/`, `demo-data/`, `.venv/` ani plików `.sqlite3`. Jeśli są, zatrzymaj się i podeślij wynik.
4. Wyślij:

```bash
git commit -m "Sebastian 2.0"
git remote add origin https://github.com/AndrzejKPKwiatkowski/sebastian.git
git push -u origin main
```

5. Stare repozytorium `sebastian-private-ai` usuń: GitHub → repo → Settings → na dole **Delete this repository**.

`rm -rf .git` usuwa tylko historię wersji. Twoje pliki i dane w folderze zostają.
