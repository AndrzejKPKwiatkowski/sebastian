# Sebastian 2.14.3 — Gwaranci: rezerwacja przez cal.com i maile do gwarantów

Wymaga wersji 2.14.2.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_14_3.py
python sebastian.py dodatek gwaranci poczta test        # próbny mail z zaproszeniem ze skrzynki Sebastiana
python sebastian.py dodatek gwaranci calcom test        # co cal.com mówi o wydarzeniu gwaranta i ostatni błąd rezerwacji
```

## Co było nie tak

1. **„Termin zajęty” u gwaranta z cal.com.** Gdy cal.com odrzucał rezerwację z jakiegokolwiek powodu (np. obowiązkowe pole w formularzu wydarzenia, brak maila adepta), Sebastian traktował to jak zajęty termin i pokazywał „Termin zajęty”, bez śladu prawdziwego powodu.
2. **„Connection unexpectedly closed” przy gwarancie z Google.** Gmail zerwał połączenie przy wysyłce zaproszenia; Sebastian próbował raz, mail do gwaranta przepadł.

## Co się zmienia

| Sytuacja | Teraz |
| --- | --- |
| cal.com: termin naprawdę zajęty | Jak dotąd: następny gwarant albo „Termin zajęty”. |
| cal.com odrzuca z innego powodu | Druga, najprostsza próba (bez notatki i długości). Gdy dalej nie — **prośba idzie do tego samego gwaranta mailem z zaproszeniem** (Akceptuję / Nie mogę), adept widzi „Prośba wysłana”. W WhatsAppie dostajesz prawdziwy błąd cal.com. |
| Adept bez adresu e-mail | Od razu droga mailowa (cal.com wymaga maila uczestnika). |
| Gmail zrywa połączenie | Jeszcze raz za 3 s, potem przez port 465. Gdy dalej nie — mail trafia do kolejki i wychodzi sam przy kolejnych obrotach (do 12 prób, coraz rzadziej). WhatsApp: „wyszedł za 2. razem” albo — gdy przepadnie — dlaczego. |
| Złe hasło aplikacji | Jasny komunikat i polecenie `poczta --zmien` (bez kolejki — powtarzanie nic nie da). |
| Skrzynka | Domyślnie **sebastian.k.kwiatkowski@gmail.com**; hasło z ustawienia dodatku albo — w parze z adresem — z dodatku Rekrutacja (poprawione odczytywanie). |

## Sprawdzenie po aktualizacji

1. `poczta test` — ma wyjść „✅ Wyszedł”. Jeśli „❌ …” — wklej wynik.
2. Zarezerwuj testowo termin u gwaranta z cal.com. Jeśli cal.com dalej odmawia, `calcom test` pokaże dlaczego (np. obowiązkowe pole „location”) — wtedy w cal.com → wydarzenie → Advanced/Booking questions ustaw to pole jako nieobowiązkowe albo daj jedną lokalizację.
