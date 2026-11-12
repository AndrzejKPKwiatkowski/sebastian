# Sebastian 2.8.5 — Rekrutacja: czytelne „co się zgadza z ofertą”

Wymaga wersji 2.8.3 albo 2.8.4 (zawiera wszystko z 2.8.4).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_8_5.py
```

| Obszar | Zmiana |
| --- | --- |
| Wyjaśnienia dopasowania | Krótkie zdanie do Agi w drugiej osobie (np. „Angielski masz na poziomie zaawansowanym.”, „Nie pracowałaś przy przetargach.”) — bez powtarzania wymagania, bez „FAKTY potwierdzają”, „kandydatka” i cudzysłowów. Pisze je model do tekstów (Bielik, jeśli jest), a stare opisy są dodatkowo porządkowane przy wyświetlaniu. |
| Wymagania | Przepisywane dosłownie z ogłoszenia; punkt, którego słów nie ma w ogłoszeniu (przekręcony przez model), jest pomijany. |
| Stare aplikacje | Czekające aplikacje dostają nowe wyjaśnienia w wolnych chwilach pracy w tle (po jednej). |
