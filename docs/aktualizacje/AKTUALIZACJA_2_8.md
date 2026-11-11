# Sebastian 2.8 — dodatek Rekrutacja (dla Agi)

## Co nowego

**Rekrutacja** to nowy dodatek: osobny panel dla Agi, dostępny z jej laptopa przez Tailscale. Sebastian szuka ofert,
przygotowuje do każdej dopasowane CV i list przewodni, wysyła aplikacje z jej skrzynki, czyta odpowiedzi pracodawców
i daje Adze znać tylko o tych ważnych. Wszystko działa lokalnie na Macu, na modelu z Ollamy.

| Część | Co robi |
| --- | --- |
| A — fundament | Panel w stylistyce Apple z hasłem Agi, pierwsze uruchomienie krok po kroku (8 ekranów), baza faktów z CV, CV w dotychczasowym wyglądzie (zdjęcie, dwie kolumny, klauzula RODO), list przewodni i mail pisane przez model z kontrolą prawdy, wysyłka z Gmaila Agi w godzinach 8–16 w nieregularnych odstępach, raport wieczorny o 20:00 ze skrzynki Sebastiana |
| B — automat | Źródła ofert (strony z ogłoszeniami, RSS, tablice Recruitee) przeglądane co 6 godzin, odrzucanie słabo pasujących i dalekich ofert, aplikacje bez ogłoszenia do firm z listy, cel do 70 dziennie, czytanie odpowiedzi co 10 minut, podziękowanie po odmowie, jedno przypomnienie po 10 dniach ciszy, zaproszenia od razu na WhatsAppie i mailem |
| C — formularze | Wysyłka przez publiczny formularz Recruitee, „zestaw jednego kliknięcia” dla pozostałych formularzy (pliki i pola do skopiowania), autopilot dla ofert z wysokim dopasowaniem, paczka dla Claude'a przy trudnych przypadkach |

### Zasada prawdy

CV nie jest pisane przez model. Model wybiera tylko numery faktów z bazy, którą Aga potwierdza przy pierwszym
uruchomieniu (co wyeksponować i w jakiej kolejności), a tekst pochodzi wprost z bazy. List i mail pisze model, ale
zanim pójdą, sprawdza je **kontroler prawdy**: reguły (liczby, narzędzia, języki, certyfikaty, długość doświadczenia
spoza bazy) i drugi przebieg modelu. Wszystko podejrzane trafia do Agi jako „do sprawdzenia”, a autopilot takiej
aplikacji nie wyśle.

### Bezpieczniki wysyłki

- Aplikacja jest „zajmowana” przed wysyłką, więc nie wyjdzie dwa razy — także po restarcie Maca albo panelu.
- Gdy połączenie z Gmailem padnie, zanim wiadomość wyszła, aplikacja wraca do kolejki. Gdy padnie w trakcie, Sebastian
  nie ponawia sam: aplikacja czeka w „Do zrobienia” z prośbą o sprawdzenie folderu Wysłane.
- Adresy inspektora danych (IOD, RODO) i podobne z ogłoszeń nigdy nie są adresatem aplikacji.
- Własnych powiadomień i raportów Sebastian nie czyta jako odpowiedzi pracodawców.
- Podziękowanie po odmowie wychodzi tylko w godzinach wysyłki i tylko wtedy, gdy model i reguły zgodnie widzą odmowę;
  przy wątpliwości (np. „niestety termin odpadł, zapraszamy…”) wiadomość trafia do Agi.

### Czego Sebastian celowo nie robi

- **Nie loguje się na konta Agi na portalach.** Pracuj.pl, OLX, LinkedIn i Indeed zabraniają automatów w regulaminach
  i blokują konta. Oferty z nich Aga wkleja linkami (pojedynczo albo kilka naraz), a Sebastian otwiera każdą stronę raz,
  tak jak przeglądarka. Jeśli strona wymaga przeglądarki, Aga wkleja treść ogłoszenia.
- **Nie wypełnia formularzy z logowaniem ani z CAPTCHA.** Dostają zestaw jednego kliknięcia: link, pobranie CV i listu,
  pola do skopiowania i przycisk „Wysłałam sama”.
- **Nie odpowiada rekruterom sam**, poza podziękowaniem po odmowie i przypomnieniem. Na zaproszenia i pytania
  przygotowuje szkic, a Aga go zatwierdza. Gdy czegoś nie wie (termin, dokument), pyta Agę i zapamiętuje odpowiedź.
- **Nie zapisuje zwykłej poczty Agi.** Czyta skrzynkę w trybie podglądu (nic nie oznacza jako przeczytane) i zapisuje
  wyłącznie wiadomości dopasowane do wysłanych aplikacji albo wyraźnie rekrutacyjne.

### Ile aplikacji dziennie, uczciwie

70 to górna granica, nie obietnica. Sebastian sam znajdzie tyle, ile dadzą źródła, a resztę uzupełnia aplikacjami bez
ogłoszenia do firm z listy. W pierwszych dniach najwięcej da wklejanie linków z dużych portali i dodanie źródeł
(strony karier firm z Krakowa, uczelnie, urzędy, kanały RSS) w Ustawieniach. Przy każdym źródle panel pokazuje, czy
działa i ile ofert dało. Trzy startowe źródła (nabory KPRM, praca na UJ, BIP Kraków) są wpisane wstępnie, ale nie
mogłem ich sprawdzić z zewnątrz — panel po pierwszym przejściu pokaże, czy działają.

Jedno przygotowanie (ogłoszenie, wybór faktów, list, kontrola) to kilka wywołań modelu, czyli zwykle 1–4 minuty.
Sebastian pracuje nad tym przez całą dobę, więc 70 kompletów jest realne, jeśli Mac nie śpi.

## Instalacja

Wymaga wersji 2.7. Mac z Sebastianem musi mieć włączony Tailscale.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_8.py
```

Aktualizator robi kopię w `backups/`, podmienia pliki, uruchamia testy (przy błędzie wszystko przywraca), zakłada
bazę faktów Agi ze zdjęciem z jej CV, instaluje usługę `pl.sebastian.rekrutacja` (start po zalogowaniu do Maca) i na
końcu pokazuje **dwa adresy**: panel oraz jednorazowy link pierwszego wejścia dla Agi.

Gdy macOS zapyta „Czy pozwolić aplikacji Python na przyjmowanie połączeń przychodzących?”, kliknij **Pozwól**.
Bez tego laptop Agi nie połączy się z panelem.

## Pierwsze uruchomienie z Agą (ok. 15 minut)

1. **Na Macu:** usuń Adze poranny przegląd (komendy `wa-user` z naszej rozmowy), jeśli jeszcze tego nie zrobiłeś.
2. **Hasła aplikacji Google** dla obu skrzynek: `pf.agnieszka.dolna@gmail.com` i `sebastian.k.kwiatkowski@gmail.com`.
   Konto → Bezpieczeństwo → weryfikacja dwuetapowa (musi być włączona) → https://myaccount.google.com/apppasswords →
   nazwa „Sebastian” → 16 liter. Hasło Sebastiana wpisuje Aga w kroku 3 (albo pomija krok, wtedy raport przyjdzie
   z jej skrzynki).
3. **Na laptopie Agi:** Tailscale włączony, link pierwszego wejścia otwarty w Safari lub Chrome. Aga ustawia własne
   hasło (link działa raz).
4. **Powitanie** prowadzi przez: skrzynkę Agi, skrzynkę Sebastiana, dane z CV (do przejrzenia i poprawy), narzędzia
   i umiejętności (Office, ChatGPT, Canva i inne, z poziomem), czego szuka, jak Sebastian ma pracować, podgląd CV.
5. **Pierwsza próba:** na stronie „Dziś” wklej link do jednej oferty → po 1–3 minutach dokumenty są gotowe →
   przeczytaj list → „Zatwierdź i wyślij”. W „Ustawieniach” kliknij „Wyślij mi raport teraz”, żeby sprawdzić skrzynkę
   Sebastiana.
6. Dodaj w **Ustawieniach → Firmy** kilka firm do aplikacji bez ogłoszenia i w **Źródłach** strony z ofertami.
7. Po kilku dniach, gdy listy są dobre, włącz **autopilota**.

Dodaj panel do Docka Agi: w Safari Plik → Dodaj do Docka. Działa wtedy jak aplikacja.

## Polecenia na Macu

```bash
python sebastian.py dodatek rekrutacja adres          # adres panelu i link pierwszego wejścia
python sebastian.py dodatek rekrutacja status         # skrzynki, liczby aplikacji, wysyłka
python sebastian.py dodatek rekrutacja haslo          # nowy jednorazowy link, gdy Aga zapomni hasła
python sebastian.py dodatek rekrutacja szukaj         # przejrzyj źródła teraz i pokaż ich stan
python sebastian.py dodatek rekrutacja skrzynka       # sprawdź odpowiedzi pracodawców teraz
python sebastian.py dodatek rekrutacja raport         # wyślij raport wieczorny teraz
python sebastian.py dodatek rekrutacja usluga status|instaluj|usun
python sebastian.py dodatek rekrutacja ustawienia     # ustaw KLUCZ WARTOŚĆ, np. ustaw limit_dzienny 40
```

## Ustawienia

| Ustawienie | Domyślnie | Znaczenie |
| --- | --- | --- |
| `limit_dzienny` | 70 | najwięcej wysyłek dziennie (maile i Recruitee) |
| `godziny` / `tylko_dni_robocze` | 08:00-16:00 / tak | okno wysyłki |
| `odstep_min` / `odstep_max` | 4 / 9 | losowy odstęp między wysyłkami w minutach (ochrona przed filtrem spamu Gmaila) |
| `raport` | 20:00 | raport wieczorny |
| `autopilot` / `prog_autopilota` | nie / 75 | sam wysyłam aplikacje z dopasowaniem od progu, gdy kontrola prawdy nic nie znalazła |
| `prog_dopasowania` | 55 | automatycznie znalezione oferty poniżej progu są pomijane |
| `szukanie` / `zrodla_co_godzin` | tak / 6 | przeglądanie źródeł |
| `spontaniczne` | tak | aplikacje do firm z listy, gdy ofert jest za mało |
| `skrzynka_co_minut` | 10 | jak często czytam odpowiedzi |
| `podziekowania` | tak | podziękowanie po odmowie |
| `przypomnienia` / `przypomnienie_po_dniach` | tak / 10 | jedno przypomnienie po ciszy |
| `whatsapp` / `whatsapp_numer` | tak / numer z CV | pilne sprawy na WhatsAppie; numer musi być na liście `wa-user` |
| `port` / `nasluch` / `dodatkowy_host` | 8790 / tailscale / — | gdzie słucha panel (`tailscale` = tylko adres Tailscale i ten Mac) |

## Dane i bezpieczeństwo

Wszystko jest w `data/dodatki/rekrutacja/` (nigdy w repozytorium): `fakty.json` (baza faktów), `zdjecie.jpg`,
`stan.sqlite3` (aplikacje, historia, źródła, firmy, wiadomości, pytania), `aplikacje/<nr>/` (dokładnie te pliki PDF,
które poszły), `sesja.key`. Hasła do Gmaila są w pęku kluczy macOS (`sebastian-rekrutacja`). Panel słucha tylko na
adresie Tailscale i na tym Macu, sprawdza nagłówek hosta, ma hasło Agi (5 błędnych prób = 5 minut przerwy) i ochronę
CSRF. Pobieranie ogłoszeń nie otworzy adresów lokalnych ani z sieci domowej.

## Najczęstsze problemy

| Objaw | Działanie |
| --- | --- |
| Laptop Agi nie otwiera panelu | Tailscale włączony na obu komputerach? `… rekrutacja adres` — czy jest adres 100.x? Zapora macOS: Ustawienia → Sieć → Zapora → Python: zezwól. Potem `… rekrutacja usluga instaluj` |
| „Google odrzucił logowanie” | To musi być hasło aplikacji (16 liter), a konto musi mieć weryfikację dwuetapową |
| Dokumenty się nie przygotowują | Ollama działa? `ollama ps`. Log: `data/logs/rekrutacja.err` |
| Strona ogłoszenia się nie otwiera | Wklej treść ogłoszenia w polu „Strona się nie otwiera?” |
| Raport nie przychodzi | `… rekrutacja raport`; bez hasła skrzynki Sebastiana raport idzie ze skrzynki Agi |
| WhatsApp nie przychodzi | numer Agi musi być na liście `python sebastian.py wa-user`; usługa WhatsApp musi działać (`wa-status`) |
| Źródło „nie działa” | strona zmieniła adres albo wymaga przeglądarki; wyłącz je w Ustawieniach i dodaj inne |

## Przywracanie

Kopia jest w `backups/aktualizacja-2.8-…/`. Usługę wyłączysz: `python sebastian.py dodatek rekrutacja usluga usun`.
Dodatek wyłączysz: `python sebastian.py dodatki wylacz rekrutacja`.
