# Sebastian 2.19.2 — Rekrutacja: najpierw lepiej płatne oferty, pensja na rękę

Działa od 2.16.1 do 2.19.1 (zawiera wszystkie zmiany po drodze).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_19_2.py
```

| Element | Teraz |
| --- | --- |
| Kolejność przygotowania | gdy czeka kilka ofert, Sebastian najpierw sprawdza pensję w każdej (bez modelu), potem przygotowuje: 1) umowa o pracę (albo umowa niepodana) z co najmniej 5000 zł na rękę — od najwyższej, 2) pozostałe z podaną pensją — od najwyższej, 3) bez pensji — w kolejności dodania. Oferty dodane przez Agę nadal przed znalezionymi automatycznie. Próg w Ustawieniach |
| Pensja na rękę | przy wynagrodzeniu: „na rękę ok. … zł miesięcznie” — umowa o pracę 2026: ZUS 13,71%, zdrowotna 9%, KUP 250 zł, PIT 12% z PIT-2, bez ulgi dla młodych, statusu studenta i PPK (7000 zł brutto → 5101,67 zł). Stawki godzinowe × 168 h. B2B: kwota na fakturę bez przeliczania |
