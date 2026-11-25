# Sebastian 2.36.3 — oferty zatrzymane na blokadzie wracają

- Oferty, które w czasie blokady pracuj.pl dostały „brakuje danych” (błąd 429), wracają do kolejki „czeka na przygotowanie”.
- Gdy portal ma przerwę, jego oferty czekają w kolejce zamiast kończyć się błędem; inne oferty idą dalej.
  Po przerwie Sebastian otwiera je po jednej co pół minuty (ok. 2 na minutę — 80 ofert ≈ 40 minut).
- Strona „Dziś” pokazuje, że portal chwilowo blokuje i do której godziny.
