# Sebastian 2.5 — WhatsApp: pamięć rozmów, załączniki, akta osób, dostęp pełny

## Co nowego

**1. Rozmowy zostają na stałe.** Sebastian niczego już nie usuwa z obserwowanego WhatsAppa (wcześniej 90 dni). Zapisuje też część **wcześniejszej historii**, którą WhatsApp przesyła przy połączeniu (ile — decyduje telefon).

**2. Czyta załączniki.** PDF-y, Word, Excel, PowerPoint i teksty przesyłane w rozmowach — w obie strony — są czytane tak jak załączniki poczty. Ze zdjęć dokumentów (faktura, pismo) wyciąga tekst. Zapisywany jest tekst, nie plik.

**3. Akta osób.** Dla każdej osoby Sebastian prowadzi notatkę: kim jest, jakie są sprawy i ustalenia, co jest otwarte, co warto pamiętać, kiedy był ostatni kontakt. Zapytaj na WhatsAppie: `kto to Jan` / `co wiem o Jan`. W panelu: „Twój WhatsApp” → lista osób.

**4. Nauka z rozmów.** Rozmowy trafiają do modułu Nauka (każdy miesiąc rozmowy osobno) i zasilają Bieżące sprawy oraz Profil wiedzy. Nie trafiają do Open WebUI.

**5. Lista dozwolonych numerów z poziomem dostępu.** Jak dotąd Sebastian odpowiada **tylko** Twojemu numerowi i numerom dodanym przez `wa-user` — inne ignoruje (nie odpowiada, nie zapisuje, nie daje niebieskich ptaszków). Nowość: osoba może mieć dostęp **`pelny`** — taki sam jak Ty (sprawy firmowe, dokumenty, Twój WhatsApp, akta osób, zamykanie zadań) — albo jak dotąd **`prywatny`**.

## Instalacja

Wymaga wersji 2.4.

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_5.py
```

## Żona z takim samym dostępem jak Ty

Jeśli żona jest już na liście (dostęp prywatny), usuń ją i dodaj ponownie:

```bash
python sebastian.py wa-user                          # lista: kto może pisać i z jakim dostępem
python sebastian.py wa-user usun 48XXXXXXXXX
python sebastian.py wa-user dodaj 48XXXXXXXXX --imie Aga --wolacz Ago --kto żona --dostep pelny --przeglad tak --glos tak
```

Albo samo `python sebastian.py wa-user dodaj` — program zapyta o wszystko, także o dostęp. Sebastian przywita się i napisze, że ma ona pełny dostęp.

⚠ Dostęp `pelny` oznacza, że na jej telefon trafią także sprawy klientów i akta osób z Twojego WhatsAppa.

## Przydatne

```bash
python sebastian.py wa-watch                       # stan: akta osób, odczytane załączniki
python sebastian.py wa-watch ludzie                # odśwież akta teraz
python sebastian.py wa-set WA_WATCH_KEEP_DAYS 365  # gdybyś jednak chciał limit (0 = na stałe)
python sebastian.py wa-set WA_WATCH_PEOPLE nie     # bez akt osób
python sebastian.py wa-set WA_WATCH_TO_LEARNING nie   # bez nauki z rozmów
```

Jeśli wcześniej sam ustawiłeś `WA_WATCH_KEEP_DAYS` (np. 90), to ustawienie zostaje — zmień je na `0`, żeby przechowywać na stałe.

## Uczciwie o prywatności

Na Macu leżą teraz na stałe rozmowy Twoich znajomych i klientów, treść przesłanych plików i akta osób (`data/whatsapp/`). Włącz FileVault. Tego folderu nigdy nie wysyłaj na GitHub. Przetwarza to wyłącznie lokalny model. Wyjątek: odpowiedzi trafiają na telefon (Twój i osób z dostępem pełnym).
