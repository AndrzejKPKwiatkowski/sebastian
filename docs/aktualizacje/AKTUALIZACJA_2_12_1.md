# Sebastian 2.12.1 — Rekrutacja: przepisanie listów przez Gemini od razu

Wymaga wersji 2.12 (albo 2.11).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_12_1.py
```

## Przepisanie aktualnych listów

```bash
python sebastian.py dodatek rekrutacja przepisz
```

Przepisuje przez Gemini listy wszystkich aplikacji czekających na Agę (do zatwierdzenia, do sprawdzenia, formularz), z nowym PDF, i pokazuje postęp. Listy zatwierdzone, a jeszcze niewysłane — tylko z `--takze-zatwierdzone`. Wysłanych nie rusza. Można przerwać Ctrl+C i uruchomić ponownie — zaczyna od tych, których jeszcze nie przepisał.

| Obszar | Zmiana |
| --- | --- |
| Tempo | Najwyżej ok. 10 zapytań na minutę (darmowy poziom Google), więc limit rzadko się włącza. |
| Przerwy | Po błędzie limitu (429): 1 min, potem 2, 4, 8… (najwyżej godzina); po pierwszej udanej odpowiedzi licznik się zeruje. |
| Oznaczanie | List jest oznaczony jako „napisany przez Gemini” tylko wtedy, gdy rzeczywiście odpowiedziało Gemini — gdy Google nie odpowie, aplikacja czeka na kolejną próbę zamiast dostać tekst z modelu lokalnego. |
| W tle | Bez polecenia działa jak w 2.12: po jednym liście na obrót. |
