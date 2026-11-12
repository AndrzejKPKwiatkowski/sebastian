# Sebastian 2.9 — Owca Sebastian 🐑

Wymaga wersji 2.8.4 albo 2.8.5 (zawiera wszystko z 2.8.5).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_9.py
```

Owca Sebastian to maskotka i motywatorka Agi. Pisze ładne maile (styl Apple, owca w trzech minach) ze skrzynki Sebastiana.

## Cel dnia

| Kiedy | Co |
| --- | --- |
| Rano (`owca_rano`, 7:45, dni robocze) | „Dzień dobry! Jaki cel na dziś?” — przyciski 10/20/30/40/50 (jedno kliknięcie ustawia cel), wynik z wczoraj, seria dni, ile czeka do przejrzenia. Bez wyboru zostaje ostatni cel. |
| W ciągu dnia (`owca_przypomnienia`, 11:00, 13:30, 15:30) | Postęp z paskiem i przyciskiem „Przejrzyj N aplikacji”. Przez pierwszy tydzień w każdym okienku, potem tylko wtedy, gdy postęp jest poniżej 80% tempa. Najwyżej 3 dziennie; bez przypomnień, gdy nie ma czego zatwierdzać. |
| Po osiągnięciu celu | Gratulacje i seria dni; potem cisza do jutra. |
| Wieczorem | Linia owcy w raporcie: cel, wynik, seria. |

„Zrobione” = wysłane dziś + zatwierdzone dziś (czekają na wysyłkę). Karta owcy jest też na stronie „Dziś” (cel do zmiany jednym kliknięciem).

## Etapy aż do umowy

| Etap | Mail owcy |
| --- | --- |
| Zaproszenie na rozmowę | Przygotowanie pod tę ofertę: mocne strony (z dopasowania), braki i jak o nich mówić, obowiązki, typowe pytania, pytania do pracodawcy, co zabrać. |
| Dzień rozmowy (gdy termin da się odczytać, np. „20.11”, „17 listopada”, „jutro”) | Krótkie „powodzenia” z przypomnieniem przykładów z liczbami. |
| Dzień po rozmowie | „Jak poszło?” — przyciski: czekam na decyzję / dostałam ofertę / to nie to / rozmowa jeszcze przed mną; gotowe podziękowanie do skopiowania. |
| Zadanie rekrutacyjne | Wskazówki, jak do niego podejść. |
| Oferta pracy | Co sprawdzić (umowa, netto vs oczekiwania, okres próbny, start vs wypowiedzenie, godziny, benefity) i jakie dokumenty przygotować; przycisk „Przyjmuję ofertę”. |
| Przyjęta oferta (po potwierdzeniu) | Status „przyjęta oferta 🎉”, szukanie i wysyłka wstrzymane, gratulacje. Odpowiedzi nadal są czytane. |

Przyciski w mailach działają w sieci Tailscale (link z tajnym tokenem, cel tylko z dnia maila). Wyłączenie: Ustawienia → Jak pracuję → Owca Sebastian.
