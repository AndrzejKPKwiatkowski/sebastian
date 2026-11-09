# Sebastian 2.7 — dodatki i Przypominacz

## Co nowego

**Gniazdo na dodatki.** Od teraz nowe funkcje mogą powstawać jako osobne **dodatki**, a nie dopisywane do głównego kodu.
Dodatek to folder z dwoma plikami (`dodatek.json` + `__init__.py`), ten sam układ co w Sebastianie 3. Dzięki temu
dodatki da się później przenieść do „trójki”. Wbudowane dodatki są w `dodatki/`, Twoje własne w `data/dodatki/`.
Błąd w dodatku nie psuje WhatsAppa: trafia do logu, a po 3 błędach z rzędu dodatek pauzuje na 10 minut.

**Pierwszy dodatek: Przypominacz.** Jest dla chwil, gdy w trakcie spotkania albo innej pracy coś wpada Ci do głowy:

1. **Nagrywasz głosówkę**, np. „przypomnij mi zadzwonić do Kowalskiego w sprawie umowy”. Sebastian rozumie też
   głosówki bez słowa „przypomnij”, np. „aha, i tonery się kończą, wróćmy do tego wieczorem”. Wtedy rozstrzyga model.
2. **Potwierdzenie** przychodzi od razu: „✓ Przyjąłem — przypomnę dziś o 17:45 (po spotkaniu „Klient Nowak”, do 17:30)”.
3. **W tle** Sebastian szuka kontekstu w poczcie, notatkach, wiedzy z nauki, w Twoich rozmowach na WhatsAppie
   i w kalendarzu na najbliższy tydzień. Zapisuje 1–2 zdania ze źródłem.
4. **Wieczorem, po ostatnim spotkaniu z kalendarza** (+15 minut), dostajesz wiadomość z listą i kontekstem
   oraz „telefon”, czyli głos Sebastiana: „Hej Andrzeju! Tu Sebastian. Masz dwie sprawy, które odłożyłeś na później.
   Pierwsza: … Druga: … Teraz spójrz na WhatsAppa i odpowiedz, co z nimi zrobisz.”
5. **Odpowiadasz** krótko albo swobodnie, pisząc lub nagrywając, np. „z Kowalskim pogadam po kolacji, a tonery już
   ktoś kupił”.
6. **Bez odpowiedzi** → po godzinie drugi „telefon”: „Andrzej, przypominam…”. Dalej cisza → po 15 minutach:
   **„I co? Olewasz mnie :'(”**. Sprawy bez decyzji wracają następnego wieczoru z dopiskiem „czeka od wczoraj”.

Nic nie znika: każda sprawa i każda decyzja zostaje w historii (`… przypominacz historia`).

### Odpowiedzi, które Sebastian rozumie

| Napiszesz (albo powiesz) | Co się dzieje |
| --- | --- |
| `1 zrobione` · `zrobione 1 i 3` · `1 i 2 zrobione` | załatwione |
| `2 jutro` · `2 w piątek` · `wszystko jutro` | wróci tego dnia wieczorem |
| `1 o 21` · `3 za godzinę` | wróci dziś o tej godzinie |
| `3 do zadań` | trafia na listę zadań w panelu |
| `4 usuń` · `4 nieaktualne` | skreślone (zostaje w historii) |
| `ok` · `widzę` · `zaraz` | koniec „dzwonienia”; sprawy czekają na decyzję, a bez niej wrócą jutro |
| zwykłe zdanie | model dopasowuje je do spraw. Jeśli to pytanie niezwiązane z przypomnieniem, Sebastian odpowie normalnie |

Inne komendy: `przypomnienia` (co czeka i kiedy), `przypomnij teraz` (przypomnij od razu), `przypomnij mi jutro …`,
`przypomnij mi o 16 …`, `przypomnij mi za 2 godziny …`.

## Uczciwie o „dzwonieniu”

**Przez WhatsAppa Sebastian nie może zadzwonić.** Połączone urządzenie (tak jest podłączony, jak WhatsApp Web)
nie obsługuje rozmów głosowych. Dlatego:

- **domyślnie** „telefon” jest **głosówką**: telefon zadzwoni dźwiękiem wiadomości, a Ty odsłuchasz Sebastiana;
- **opcjonalnie** możesz włączyć **prawdziwe połączenie** przez Twilio. Twój telefon zadzwoni zwykłym połączeniem,
  a Sebastian przeczyta wszystko polskim głosem (dwa razy). Przy drugim telefonie Sebastian wie, czy odebrałeś:
  jeśli nie (albo odebrała poczta głosowa) — od razu minka.
  Koszt: numer w Twilio (kilka dolarów miesięcznie) plus kilkanaście groszy za połączenie. Konto próbne dzwoni tylko na
  zweryfikowany numer i dodaje na początku angielski komunikat.
  ```bash
  python sebastian.py dodatek przypominacz telefon         # SID, numer Twilio, token → token do pęku kluczy macOS
  python sebastian.py dodatek przypominacz telefon test    # próbne połączenie
  python sebastian.py dodatek przypominacz telefon wylacz  # z powrotem głosówki
  ```
  Gdy połączenie się nie uda, Sebastian i tak wyśle głosówkę.

## Instalacja

Wymaga wersji 2.6.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_7.py
```

## Pierwsza próba (5 minut)

```bash
python sebastian.py dodatki                                # Przypominacz: ✓ włączony
python sebastian.py dodatek przypominacz dzis              # Twój kalendarz na dziś i godzina przypomnienia
python sebastian.py dodatek przypominacz sprawdz "aha, tonery się kończą, wróćmy do tego wieczorem"
```

Potem nagraj Sebastianowi na WhatsAppie głosówkę „przypomnij mi kupić tonery” → przyjdzie potwierdzenie.
Napisz `przypomnij teraz` → za około pół minuty przyjdzie wieczorne przypomnienie z głosem. Odpisz `1 zrobione`.

## Ustawienia

`python sebastian.py dodatek przypominacz ustawienia` · zmiana: `… przypominacz ustaw KLUCZ WARTOŚĆ`

| Ustawienie | Domyślnie | Znaczenie |
| --- | --- | --- |
| `po_spotkaniu_minut` | 15 | ile minut po końcu ostatniego spotkania |
| `najwczesniej` | 17:00 | nie wcześniej niż (gdy ostatnie spotkanie kończy się np. o 12) |
| `bez_spotkan` | 18:00 | godzina, gdy w kalendarzu nic nie ma (np. w weekend) |
| `najpozniej` | 21:30 | nie później (i zawsze 15 minut przed ciszą nocną `WA_QUIET`) |
| `odstep_minut` | 60 | sprawa nagrana już po spotkaniach wraca najwcześniej po tylu minutach; za późno → jutro |
| `drugi_raz_po_minutach` | 60 | kiedy drugi „telefon” |
| `minka_po_minutach` | 15 | kiedy minka po drugim „telefonie” |
| `minka` | I co? Olewasz mnie :'( | treść minki |
| `dzwonek` | glosowka | `glosowka` albo `telefon` (Twilio) |
| `rozpoznawanie_modelem` | tak | głosówki bez słowa „przypomnij” sprawdza model; `nie` = tylko słowa-klucze (szybciej) |
| `kontekst_dni` | 45 | jak daleko wstecz szukać w rozmowach WhatsApp |
| `wolacz` | (puste) | jak Sebastian zwraca się w głosie; puste = „Andrzeju” z imienia |

Godziny liczą się z kalendarzy zaimportowanych w panelu (zakładka Kalendarze). Jeśli kalendarz w panelu jest stary,
Sebastian nie wie o nowych spotkaniach. Wtedy przypomni o `bez_spotkan` albo po ostatnim znanym spotkaniu.

## Dla piszących dodatki

Szkielet i zasady są w DOKUMENTACJA.md, rozdział 8c. Najkrócej: `dodatek.json` (id, nazwa, wersja, opis, uprawnienia,
ustawienia, pomoc, polecenia) + `__init__.py` z `on_message(ctx, msg)`, `tick(ctx)` i `COMMANDS`. Wszystko przez
`ctx`: wysyłanie, model, kalendarz, wiedza, obserwowany WhatsApp, zadania, własna baza, pęk kluczy. Działa tylko to, na co
pozwalają uprawnienia. Twój dodatek wrzucasz do `data/dodatki/<id>/`; domyślnie jest wyłączony:
`python sebastian.py dodatki wlacz <id>` i `wa-start`.

## Uczciwie

- Na czas rozpoznawania głosówki bez słowa „przypomnij” odpowiedź Sebastiana przychodzi o kilka–kilkanaście sekund
  później (dodatkowe pytanie do modelu). Nie chcesz tego: `ustaw rozpoznawanie_modelem nie`.
- Szukanie kontekstu zajmuje model w tle (zwykle kilkanaście sekund na sprawę), w tym czasie odpowiedź na WhatsAppie
  może chwilę poczekać.
- Gdy przypomnienie jest otwarte, `zrobione 2` dotyczy sprawy nr 2 z przypomnienia, nie zadania nr 2 z listy zadań.
- Przypominacz rozmawia tylko z Tobą (właścicielem). Aga i Jan go nie widzą.
- Mac musi działać wieczorem (jak przy porannym przeglądzie). Jeśli spał, sprawy przyjdą tego samego wieczoru po
  obudzeniu albo — po północy — następnego.
