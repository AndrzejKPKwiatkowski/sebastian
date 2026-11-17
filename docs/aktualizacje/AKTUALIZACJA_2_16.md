# Sebastian 2.16 — Rekrutacja: uwagi do ofert i nauka, czego szukać

Wymaga wersji 2.15.2 (albo 2.15.1).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_16.py
```

## Uwaga do każdej oferty

Na stronie każdej oferty (pod „Oferta”) jest karta **„Twoja uwaga do tej oferty”**:
- gotowe powody do zaznaczenia: *Po angielsku — wolę rekrutację po polsku*, *Wymaga programów lub uprawnień, których nie mam*, *Nie moja branża*,
  *Za daleko albo zły dojazd*, *Za niska pensja*, *Za dużo sprzedaży lub obsługi klienta*, *Świetna — szukaj więcej takich*;
- pole na własne słowa, np. „wymagają znajomości programów geodezyjnych, których nie znam”;
- przyciski **Zapisz uwagę** albo **Zapisz i pomiń tę ofertę**.

Po zapisaniu Sebastian mówi, czego się nauczył (np. „pomijam oferty wymagające: AutoCAD, C-Geo”), i oznacza czekające oferty, które tej zasady nie spełniają.

## Jak Sebastian z tego korzysta

| Zasada | Działanie przy kolejnych ofertach |
| --- | --- |
| Angielski | Ogłoszenie po angielsku albo wymagające biegłego angielskiego → oferta znaleziona automatycznie jest pomijana; dodana ręcznie dostaje ostrzeżenie. |
| Pomijam oferty, które wymagają… | Hasło (np. nazwa programu, uprawnień, branży) w ogłoszeniu → jak wyżej. |
| Szukam więcej ofert z… | Ocena dopasowania +8 i dopisek „Lubisz takie oferty”. |
| Twoje uwagi | Trafiają do oceny każdej nowej oferty przez model. |

Zasada prawdy: hasło trafia na listę tylko wtedy, gdy występuje w tej ofercie albo w słowach Agi; podstawowe narzędzia (Excel, Word, pakiet Office) nigdy.

Wszystko widać w **Ustawienia → Czego szukam — nauka z Twoich uwag**: przełącznik „angielski”, hasła do pominięcia (z ×, można dopisać własne), hasła lubiane i lista uwag.
