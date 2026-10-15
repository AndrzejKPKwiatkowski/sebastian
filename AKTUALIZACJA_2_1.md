# Sebastian 2.1 — nauka czyta załączniki

Od wersji 2.1 nauka czyta także **załączniki z maili**: PDF (również skany, przez OCR), Word, Excel, PowerPoint, pliki tekstowe oraz zdjęcia i skany dokumentów. Treść załącznika trafia do wątku jako „📎 Załącznik: nazwa_pliku”, więc model rozumie, z jaką sprawą, osobą i datą jest związany. Pełny tekst zapisuje się w `data/learner/teksty/` razem z wątkiem.

**Jak to działa**

- Załącznik jest pobierany z serwera dopiero wtedy, gdy model czyta dany wątek. Pobieranie jest tylko do odczytu, a mail nie zostaje oznaczony jako przeczytany.
- Plik trafia na chwilę do `data/learner/tmp` i jest od razu usuwany. Zostaje sam tekst.
- Ten sam plik, np. umowa przesyłana w kolejnych odpowiedziach, jest czytany tylko raz.
- Logo ze stopek, małe obrazki, obrazki wklejone w treść, archiwa ZIP i maile powyżej 25 MB są pomijane.
- Wątki, które nauka już przeczytała, a które mają załączniki, wracają do kolejki, od najnowszych. Wątki bez załączników nie są czytane ponownie.
- Dla maili z archiwum pobranych w wersji 2.0 nauka sprawdza w tle sam nagłówek wiadomości (kilkadziesiąt bajtów), żeby wiedzieć, które mają załączniki.

## Instalacja (2 minuty)

1. Pobierz `Sebastian_aktualizacja_2_1.py` do Pobranych.
2. Terminal:

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_1.py
```

Aktualizator robi kopię zmienianych plików i bazy nauki w `backups/aktualizacja-2.1-…`, podmienia pliki i sprawdza, czy wszystko się uruchamia. W razie problemu sam przywraca poprzednią wersję. Jeśli nauka działała w tle, zatrzymuje ją na czas aktualizacji i włącza ponownie.

Po komunikacie **OK** odśwież panel (Command + R). W nagłówku będzie **SEBASTIAN 2.1**, a w zakładce *Nauka* licznik załączników.

## Ustawienia

| Polecenie | Co robi |
| --- | --- |
| `python sebastian.py learn-set ATTACHMENTS_ENABLED nie` | Wyłącza czytanie załączników |
| `python sebastian.py learn-set ATTACHMENTS_SINCE 2023-01-01` | Czyta załączniki tylko z maili od tej daty |
| `python sebastian.py learn-set ATTACHMENTS_SCOPES private` | Tylko poczta prywatna (`work` = tylko firmowa) |
| `python sebastian.py learn-set ATTACH_MAX_MB 40` | Limit wielkości maila z załącznikami |

Po zmianie ustawień: `python sebastian.py learn-start`.

## Warto wiedzieć

- Nauka będzie wolniejsza. Załączniki to dużo tekstu, a skany przez OCR wymagają czasu (Tesseract: `brew install tesseract tesseract-lang`).
- W załącznikach są dokumenty klientów: polisy, umowy, wnioski. Do faktów i profilu nie trafiają numery PESEL, kont ani dane o zdrowiu innych osób. Pełne teksty leżą jednak w `data/learner/teksty/` na Macu. Włącz FileVault i nie wysyłaj folderu `data/` nigdzie.
- Postęp zobaczysz w `python sebastian.py learn-status` (wiersz „Załączniki”) oraz w zakładce *Nauka*.

## Cofnięcie

```bash
python sebastian.py learn-stop
cp -R backups/aktualizacja-2.1-*/files/. .
rm -f learner_attach.py
python sebastian.py learn-start
```

Baza nauki 2.1 działa także z kodem 2.0: nowe tabele są po prostu ignorowane.
