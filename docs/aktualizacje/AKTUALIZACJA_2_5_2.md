# Sebastian 2.5.2 — poprawka nauki z rozmów WhatsApp

## Co było nie tak

W logu nauki co 2 minuty pojawiało się:

```
→ WhatsApp/<osoba>/2026-10
Błąd w pętli nauki: AttributeError: 'NoneType' object has no attribute 'TZ'
```

Proces nauki działa osobno od WhatsAppa i nie „podłączał” modułu WhatsAppa przed czytaniem rozmów. Każda próba kończyła się błędem, a ponieważ rozmowy z ostatnich 60 dni mają w kolejce pierwszeństwo, nauka utknęła na nich — poczta i Dysk czekały.

Nic nie zostało utracone ani uszkodzone: rozmowy są zapisane, fakty z poczty też, kolejka po prostu stała.

## Co poprawia 2.5.2

- Nauka sama podłącza moduł WhatsAppa — rozmowy są czytane normalnie.
- Bezpiecznik: pozycja, która 3 razy z rzędu kończy się błędem, dostaje status „błąd”, a nauka idzie dalej. Przywrócisz ją: `python sebastian.py learn-retry`.
- Zawiera też zmiany z 2.5.1 (diagnostyka „kto pisze do Sebastiana”), więc działa na 2.5 i na 2.5.1.

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_5_2.py
```

Aktualizator sam zatrzyma i uruchomi ponownie naukę. Po kilku minutach sprawdź:

```bash
tail -n 20 data/logs/learner.log      # zamiast błędów: „→ WhatsApp/… ✓ faktów: N”
python sebastian.py learn-status       # linia WhatsApp: rośnie liczba przeczytanych
```
