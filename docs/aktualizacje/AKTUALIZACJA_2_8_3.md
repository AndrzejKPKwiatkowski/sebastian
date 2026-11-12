# Sebastian 2.8.3 — Rekrutacja: oficjalny list motywacyjny, szczegóły oferty, mniej błędów

Wymaga wersji 2.8.1 albo 2.8.2 (zawiera wszystko z 2.8.2 — patrz `AKTUALIZACJA_2_8_2.md`).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_8_3.py
```

## Co się zmienia

| Obszar | Zmiana |
| --- | --- |
| Nazwa | Wszędzie „list motywacyjny” (pliki `…_List_motywacyjny_…pdf`). |
| Układ listu | Jak oficjalne pismo: po lewej imię i nazwisko, Kraków, e-mail, telefon z +48; po prawej data; niżej po prawej adresat (firma i adres z ogłoszenia); „Dotyczy: …”; treść; „Z poważaniem”, podpis (zdjęcie podpisu z Ustawień, jeśli jest) i imię i nazwisko; na dole klauzula RODO. |
| Mail | Składany z faktów bez modelu — zawsze poprawny: stanowisko, link (gdy adres pochodzi ze strony firmy), najlepiej pasujące doświadczenie z dwoma punktami, dostępność. |
| Jakość listu | Model pisze tylko treść; Sebastian sprawdza formy męskie („potrafiłbym”, „jestem gotowy”), przesadne obietnice („bez nauki”, „od pierwszego dnia”), powtórzenia, zdania bez sensu i liczby spoza faktów. Przy błędzie: korekta językowa, potem druga próba ze wskazaniem błędów, a na końcu poprawny list złożony z faktów. Do pisania używany jest Bielik (polski model), jeśli jest zainstalowany (`model_pisania: auto`). |
| Klauzula RODO | Luka „na stanowisko ____” uzupełniana nazwą stanowiska; dwie zgody (obecna i przyszłe rekrutacje) łączone w jedno zdanie. |
| Oferta w panelu | Karta „Oferta”: wynagrodzenie (tylko kwota z ogłoszenia), dojazd (ok. km od Krakowa i link do trasy komunikacją z adresu z Ustawień), co się zgadza z ofertą (✓ masz / ◐ częściowo / ✗ brakuje — z uzasadnieniem), obowiązki, co oferują, pełna treść ogłoszenia. |
| Pobieranie | Przyciski „Pobierz CV” i „Pobierz list motywacyjny” przy każdej aplikacji (także formularzowej). |
| Testy a pęk kluczy | Poprawka błędu z 2.8–2.8.2: testy uruchamiane przez aktualizator zapisywały próbne hasła do prawdziwego pęku kluczy macOS (skrzynki Agi i Sebastiana) i czytały prawdziwe klucze API. Teraz testy działają z `SEBASTIAN_TESTY=1` i pęku kluczy nie dotykają. Aktualizator usuwa pozostałe próbne hasła i prosi o ponowne podłączenie skrzynek; do tego czasu zatwierdzone aplikacje czekają w kolejce. |
| Po instalacji | Czekające aplikacje (do zatwierdzenia, do sprawdzenia, formularz) są przygotowywane od nowa; zatwierdzone dostają tylko nowy układ PDF. |

## Nowe ustawienia

| Ustawienie | Domyślnie | Znaczenie |
| --- | --- | --- |
| `dojazd_skad` | Kraków | skąd liczyć trasę dojazdu (nie trafia do CV) |
| `model_pisania` | auto | model do listów; `auto` = Bielik, jeśli jest w Ollamie, inaczej główny model |

Bielik (ok. 6,7 GB): `ollama pull hf.co/speakleash/Bielik-11B-v2.3-Instruct-GGUF:Q4_K_M`
