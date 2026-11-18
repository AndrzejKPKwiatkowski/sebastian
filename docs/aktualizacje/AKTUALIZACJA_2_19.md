# Sebastian 2.19 — Rekrutacja: dojazd, jawny procent, ogłoszenie jak na portalu

Działa od 2.16.1, 2.16.2, 2.16.3, 2.17 i 2.18 (zawiera wszystkie te zmiany).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_19.py
```

| Element | Teraz |
| --- | --- |
| Czas dojazdu | na stronie oferty: samochód, komunikacja, rower, pieszo — z adresu domu (Ustawienia → Skąd dojeżdżasz) do adresu z ogłoszenia. Komunikacja: przyjazd na 8:00 w najbliższy dzień roboczy (Transitous, rozkłady MPK). Samochód bez korków (OpenStreetMap/OSRM). Czekające oferty dostają czasy w tle, po jednej na obrót |
| Odkładanie ofert | oferty znalezione automatycznie odpadają, gdy jedzie się ponad 60 min komunikacją **i** ponad 50 min samochodem, chyba że pensja na rękę przekracza 6500 zł (brutto × 0,72). Progi w Ustawieniach. Przy ofertach dodanych ręcznie — tylko ostrzeżenie |
| Procent dopasowania | 60% wymagania z ogłoszenia (✓ = całe, ◐ = pół) + 40% zgodność z tym, czego Aga szuka (rodzaj pracy, warunki). Na stronie oferty dwa paski ze składnikami. Stare oferty przeliczone |
| Pełna treść ogłoszenia | zwijana jak dotąd, w środku ułożona jak na portalu: nagłówki sekcji ze złotym paskiem, punkty, akapity; bez menu strony i „podobnych ofert” |
| Edge bez pytania | Ustawienia → „Pobierz plik dla Windows”: zasada Chrome AutoLaunchProtocolsFromOrigins dla adresu panelu; po dwukliku i restarcie Chrome przestaje pytać |
| Opis profilu | 1. zdanie o specjalistce („Specjalistka z blisko trzyletnim doświadczeniem…”), każde kolejne w 1. osobie; staż wyliczony z dat przy stanowisku; nowy, 7. wzór Agi |

Usługi map dostają tylko adres miejsca pracy i współrzędne — bez imienia i danych Agi. Adres domu jest w danych na Macu, nie w repozytorium.
