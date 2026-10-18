# Sebastian 2.1.2 — sprawdzenie systemu i scalenie wiedzy z Dysku

## Nowe: `python sebastian.py check`

Jedno polecenie sprawdza cały system i przy każdym problemie podpowiada, co wpisać. Niczego nie zmienia, tylko czyta.

Sprawdza:
- Ollamę i oba modele (analizy poczty i nauki),
- panel w tle i odpowiedź pod 127.0.0.1:8765,
- poranek 06:30 i ostatni przebieg,
- naukę: czy działa, kiedy ostatnio coś zapisała, błędy, problemy z logowaniem do skrzynek, Bieżące sprawy,
- Dysk Google: czy wiedza z Drive Learnera jest dołączona i czy logowanie jest ważne,
- Tesseracta (OCR),
- czy git nie śledzi folderu `data/`,
- FileVault i wolne miejsce na dysku.

Wynik: ✓ działa, ⚠ do sprawdzenia, ✗ do poprawy (ze wskazówką).

## Nowe: `learn-import ~/drive-learner --merge`

Dołącza wiedzę z dawnego Drive Learnera do **działającej** nauki: dokumenty, fakty, profil z Dysku, pełne teksty i logowanie Google. Nic z poczty nie ginie. Przed scaleniem zapisuje kopię stanu nauki w `data/learner/stan-przed-scaleniem-….sqlite3`. Profil wiedzy startuje od wiedzy z Dysku, a fakty z poczty dołączają do niego przy najbliższym odświeżeniu.

Zwykłe `learn-import` bez `--merge` działa tylko dla pustej nauki. `--force` zastąpiłby obecny stan, więc nie używaj go, gdy nauka już działa.

## Poprawka: `learn-start` / `learn-stop`

Program czeka, aż macOS naprawdę zamknie poprzednią naukę, zanim uruchomi nową. Błąd `launchctl bootstrap … status 5` już się nie pojawia.

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_1_2.py
python sebastian.py learn-import ~/drive-learner --merge
python sebastian.py check
```
