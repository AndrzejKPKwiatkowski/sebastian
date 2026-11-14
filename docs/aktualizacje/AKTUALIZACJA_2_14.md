# Sebastian 2.14 — dodatek Gwaranci (spotkania gwaranckie Feniksów)

Wymaga wersji 2.13 albo 2.13.1.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_14.py
python sebastian.py dodatek gwaranci usluga instaluj
python sebastian.py dodatek gwaranci internet wlacz
python sebastian.py dodatek gwaranci linki
```

## Co to jest

Gwarant w minutę, bez szukania po WhatsAppie. Każda osoba z zespołu dostaje **osobisty link** (bez haseł):

| Kto | Co robi |
| --- | --- |
| **Gwarant** (raz, ok. 1 minuty) | podaje maila → wkleja „Tajny adres w formacie iCal” swojego Kalendarza Google (Sebastian widzi tylko godziny zajętości, bez tytułów) → zaznacza na siatce, kiedy może, i ile spotkań w tygodniu daje. Potem dostaje tylko zaproszenia z przyciskami **Akceptuję / Nie mogę** (albo Tak / Nie w Google Calendar). |
| **Adept** | wybiera typ (usługa 30 min, serwis 1 h, analiza i doradztwo 1 h 15 min), online albo na miejscu (wpisuje gdzie), dzień i godzinę. Gwaranta dobiera system. |
| **Ty** | dostajesz krótkie powiadomienia na WhatsAppie; piszesz `gwaranci`, `gwaranci link Imię Nazwisko`, `gwaranci awans Imię Nazwisko na Senior Planner`, `gwaranci dodaj Imię Nazwisko od Imię Nazwisko`. W panelu: zakładka **Administrator**. |

## Zasady

- **Kolejność przydziału:** bezpośredni menedżer adepta → pośredni menedżer → gwarant z tej samej struktury → gwarant z innej struktury; w każdej grupie ten, kto w tym tygodniu pomagał najkrócej.
- **Kto jest gwarantem i ile spotkań:** od pierwszego awansu; każdy awans = jedno spotkanie w tygodniu więcej (Consultant 1, Consultant II 2, Planner 3, Senior Planner 4, VIP Planner 5, VIP Planner II 6). Menedżerowie: 8 (pełny etat) albo 5. Trainee i asystenci nie są gwarantami. Gwarant sam wybiera limit w tych granicach.
- **Bez kolizji:** zajętość z kalendarza odświeżana co 5 minut i jeszcze raz tuż przed rezerwacją; 15 minut buforu wokół spotkań; wydarzenia „Dostępny” nie blokują.
- Rezerwacja najwcześniej 24 h naprzód, okno 5 tygodni. Brak odpowiedzi gwaranta: przypomnienie po 20 h, wygaśnięcie 2 h przed spotkaniem (adept dostaje prośbę o inny termin).
- Zaproszenia wychodzą ze skrzynki Sebastiana (ta sama co w Rekrutacji) jako **„Sebastian · Asystent Krakowa inPartners”**.

## Prywatność

- Struktura zespołu leży tylko na Macu: `data/dodatki/gwaranci/struktura.json` (aktualizator zapisuje ją przy pierwszej instalacji). Zmiany: panel Administrator, WhatsApp albo plik + `python sebastian.py dodatek gwaranci struktura`.
- Linki do kalendarzy, maile i rezerwacje: `data/dodatki/gwaranci/gwaranci.sqlite3` — nigdy w repozytorium.

## Internet (Tailscale Funnel)

Zespół jest poza Tailscale, więc panel wystawiam pod publicznym adresem `https://<mac>.<sieć>.ts.net` (tylko ten jeden port; bez otwierania portów w routerze). Za pierwszym razem Tailscale może poprosić o zgodę na Funnel — polecenie pokaże link. `internet wylacz` zamyka dostęp z zewnątrz.

## Następne kroki (kolejne wersje)

Bilans przysług między strukturami, piątkowy raport z sekretariatu, pytanie Sebastiana na grupie Feniksy o nowe osoby, synchronizacja stanowisk z MojeIN/Prometeusa, logowanie przez Google zamiast linku iCal.
