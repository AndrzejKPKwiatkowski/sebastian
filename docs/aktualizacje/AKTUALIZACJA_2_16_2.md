# Sebastian 2.16.2 — Rekrutacja: wymagania wracają, ogłoszenia w Edge

Wymaga wersji 2.16.1.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_16_2.py
```

## Wymagania, obowiązki i ✓ dopasowania

Przyczyna: analizę oferty robi lokalny model, a jego odpowiedź była ograniczona (ok. 1100 tokenów). Przy dłuższych ogłoszeniach
dosłownie przepisane wymagania i obowiązki się nie mieściły, odpowiedź była ucinana i Sebastian zostawał z pustymi listami — a bez
wymagań nie było też ✓/◐/✗ przy dopasowaniu.

| Zmiana | |
| --- | --- |
| Dłuższa odpowiedź modelu | do ok. 2400 tokenów |
| Druga próba | gdy model lokalny nie poda wymagań ani obowiązków, a ogłoszenie jest dłuższe — Gemini (jeśli dostępne) |
| Zawsze coś | punkty wycinane wprost z ogłoszenia po nagłówkach („Wymagania”, „Oczekujemy”, „Twoje zadania”, „Zakres obowiązków”, „Oferujemy”…) |
| Starsze oferty | czekające oferty bez wymagań Sebastian uzupełnia sam w tle (po jednej na obrót) i od razu liczy dopasowanie — w historii: „uzupełnione wymagania i obowiązki z ogłoszenia” |

## Microsoft Edge

Na komputerze z Windows przyciski „Otwórz ogłoszenie ↗” (i linki z wiadomości od pracodawców) otwierają **Microsoft Edge** zamiast domyślnej
przeglądarki. Za pierwszym razem przeglądarka zapyta „Otworzyć Microsoft Edge?” — warto zaznaczyć „Zawsze zezwalaj”.
Na Macu nic się nie zmienia. Wyłączenie: Ustawienia → Jak pracuję → „Na komputerze z Windows otwieraj ogłoszenia w Microsoft Edge”.

Linki w mailach (Gmail) otwierają się w domyślnej przeglądarce — żeby i one szły do Edge, ustaw Edge jako domyślną w Windows
(Ustawienia → Aplikacje → Aplikacje domyślne → Microsoft Edge → Ustaw jako domyślną).
