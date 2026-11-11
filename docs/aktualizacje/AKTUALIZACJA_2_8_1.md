# Sebastian 2.8.1 — Rekrutacja: poprawki i więcej ofert

Wymaga wersji 2.8. Instalacja jak zwykle:

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_8_1.py
```

## Co się zmienia

| Obszar | Zmiana |
| --- | --- |
| Klauzula RODO | Klauzula z ogłoszenia trafia do CV tylko wtedy, gdy naprawdę jest zgodą („wyrażam zgodę” + „przetwarzanie danych osobowych”). W każdym innym przypadku: szeroka klauzula domyślna (obecna i przyszłe rekrutacje, z nazwą firmy). Czekające aplikacje są przeliczane przy starcie. |
| CV | Doświadczenie zawsze od najnowszego. Pod ofertę model wybiera najważniejsze stanowiska: trzy najlepiej pasujące mają wszystkie punkty, pozostałe po dwa. Stanowiska „opcjonalne” (praktyki pedagogiczne) pojawiają się tylko przy pasujących ofertach. Tekst w obu kolumnach ma osobno dobierany, największy mieszczący się rozmiar, więc strona jest wypełniona. W kontakcie tylko „Kraków”. |
| Kryteria | Sprzedaż i obsługa klienta są mile widziane. Wykluczone: praca w mediach społecznościowych, wynagrodzenie wyłącznie prowizyjne, praca w niedziele i wieczorami (przełączniki w Ustawieniach). Dojazd do 20 km. |
| Szukanie adresu e-mail | Gdy ogłoszenie nie podaje adresu, Sebastian szuka go na stronie firmy (link z ogłoszenia, Brave Search, typowe domeny). Strona musi zawierać nazwę firmy, a adres musi być w jej domenie. Adresy IOD i RODO są pomijane. Mail zaczyna się od „w nawiązaniu do ogłoszenia Państwa firmy na stanowisko … (link)”. Adres zgadnięty z domeny zawsze czeka na zatwierdzenie Agi. |
| Źródła ofert | Agregatory z oficjalnym API: **Jooble** (4 zapytania dziennie — limit klucza to 500 łącznie) i **Adzuna** (co 12 godzin; bez płatnego planu tylko 25 zapytań próbnych). Oferty z Pracuj.pl, OLX i innych portali przychodzą przez agregatory; ich stron Sebastian nie otwiera automatycznie (używa opisu z agregatora). |
| Import wiedzy | Ekran „Import wiedzy o mnie”: wklejone podsumowanie z ChatGPT albo eksport danych ChatGPT. Z eksportu czytane są wyłącznie wiadomości Agi. Do bazy trafiają tylko zaznaczone fakty; zarobki i stawki nigdy. |
| Dane Agi | Aktualizator dopisuje do bazy faktów uzupełnienia z jej podsumowania ChatGPT (obowiązki w ZZOZ i Mevlanie, praktyki pedagogiczne jako opcjonalne, kursy z poprawionymi latami, poziomy Word/Excel, Eskulap), bez danych dotyczących Andrzeja, bez zarobków i bez szkolenia z LinkedIna. Dopisuje też wcześniejsze aplikacje (homfi, NEWMEDICAL, MDT, MOW, Ascomp, drEryk), żeby nie wysyłać do nich drugi raz. |

## Klucze

Wpisz je w panelu: **Ustawienia → Klucze do wyszukiwarek ofert** (zapisują się w pęku kluczy na Macu):

- Jooble — klucz z maila od Jooble,
- Brave Search — klucz z api-dashboard.search.brave.com,
- Adzuna — `app_id` i `app_key` (po wybraniu planu API Access; bez planu tylko 25 zapytań).

## Nowe ustawienia

| Ustawienie | Domyślnie | Znaczenie |
| --- | --- | --- |
| `szukaj_maila` | tak | szukanie adresu firmy w sieci, gdy ogłoszenie go nie ma |
| `frazy` | asystentka, sekretarka, … | czego szukać w agregatorach |
| `agregatory_co_godzin` / `jooble_co_godzin` | 12 / 24 | jak często pytać Adzunę i Jooble |
| `bez_niedziel_wieczorow` / `bez_prowizji` | tak / tak (dla Agi) | pomijanie takich ofert |

Polecenie `python sebastian.py dodatek rekrutacja uzupelnij PLIK.json` scala zatwierdzone uzupełnienia z bazą faktów (używa go aktualizator).
