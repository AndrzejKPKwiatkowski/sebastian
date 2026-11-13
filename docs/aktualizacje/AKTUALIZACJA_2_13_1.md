# Sebastian 2.13.1 — Rekrutacja: Gemini bez zacinania się

Wymaga wersji 2.12.1 albo 2.13 (zawiera całą 2.13 — rozmowę z Agą).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_13_1.py
python sebastian.py dodatek rekrutacja przepisz
```

## Co było nie tak

W 2.12.1 `przepisz` czekał coraz dłużej (aż do godziny) i nie przepisał nic. Panel Google AI Studio pokazał dlaczego:
- większość błędów to **503 ServiceUnavailable** — przeciążony serwer Google, nie Wasz limit;
- reszta to **429** — na darmowym poziomie najnowsze modele „flash” mają bardzo mały dzienny przydział zapytań;
- w tym samym czasie praca w tle też pytała Gemini, więc dwa procesy dzieliły ten sam mały limit;
- po każdej nieudanej próbie list pisał jeszcze Bielik (minuty pracy), choć i tak nie był zapisywany.

## Co się zmienia

| Sytuacja | Teraz |
| --- | --- |
| Model wyczerpał dzienny limit | Odpoczywa do północy czasu kalifornijskiego (ok. 9:00 u nas); piszę następnym: starszy „flash”, potem „flash-lite” (osobne, większe limity). |
| Limit na minutę | Czekam tyle, ile każe Google (zwykle kilkadziesiąt sekund). Po trzech razach z rzędu model odpoczywa kwadrans. |
| 503 / brak odpowiedzi | Ten model odpoczywa 5–10 minut, od razu próbuję innym. |
| Wszystkie modele odpoczywają | Przerwa do najbliższego odblokowania; `przepisz` kończy się komunikatem, a resztę dokańczam w tle. |
| Tempo | Najwyżej 4–5 zapytań na minutę. |
| `przepisz` | Praca w tle nie przepisuje w tym czasie listów (nie dzieli limitu); przy błędzie Gemini nie pisze listu Bielikiem „na próżno”; na ekranie widać powód czekania. |
| Ustawienia | W statusie Gemini: aktualny model, powód przerwy i modele, które odpoczywają. |

Jeśli darmowy poziom nadal nie wystarcza: w AI Studio → Billing włącz płatności (przedpłata). Przepisanie ok. 45 listów kosztuje grosze, a limity rosną wielokrotnie.
