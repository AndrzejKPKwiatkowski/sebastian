# Sebastian 2.30 — Pamięć: Sebastian uczy się o Tobie

Wgranie: Centrum dowodzenia → „Aktualizuj Sebastiana” (albo z Terminala: `python aktualizator.py uruchom data/aktualizacje/Sebastian_aktualizacja_2_30.py`). Działa od 2.16.1 do 2.29.

## Co robi
- Każdy użytkownik Sebastiana (Andrzej, Aga, asystent…) ma **własną pamięć** — nikt nie widzi cudzej.
- Sebastian uczy się z:
  - **rozmów na WhatsAppie** — z dłuższych wiadomości i głosówek do niego (komendy pomija),
  - **eksportów ChatGPT, Claude i Gemini** — bierze tylko to, co pisała osoba (nie odpowiedzi modeli),
  - **plików** (PDF, Word, Excel, PowerPoint, tekst, zdjęcia z tekstem, zip z plikami) i **wklejonego tekstu**,
  - na start: z dotychczasowego **Profilu wiedzy** (nauka z poczty i Dysku).
- W tle lokalny model przerabia wszystko kawałek po kawałku na **fakty** (powtórki się łączą i wzmacniają),
  a z nich składa **profil**: kim jest, praca i firma, ludzie wokół, bieżące sprawy, preferencje i styl, cele, codzienność.
- **Pytania „Zrozumiałem, że… — dobrze rozumiem?”** — codziennie o 19:00 (najwyżej 3) na WhatsAppie; odpowiedź
  *1 tak, 2 nie — jak jest naprawdę, 3 tak* albo *wszystko się zgadza*. Poprawki trafiają do **księgi poprawek**
  i mają pierwszeństwo przy składaniu profilu. Nic nie jest kasowane.
- Odpowiedzi Sebastiana na WhatsAppie korzystają z pamięci osoby, która pyta. Inne dodatki: `ctx.memory()`.

## Gdzie
- Zakładka **„Uczy się o Tobie”** — w panelu głównym (wszystkie osoby) i w panelu Agi (tylko jej pamięć; kafelek 🐑 w Centrum).
  Tam: pytania do Ciebie, wgrywanie plików i eksportów, wklejanie tekstu, profil, fakty (✓ / ✗ / popraw), źródła i postęp.
- Na WhatsAppie: *co o mnie wiesz* · *pytaj mnie*.
- Bardzo duże eksporty: folder `data/dodatki/pamiec/wrzuc-tutaj/<imię>/` albo
  `python sebastian.py dodatek pamiec wgraj ~/Downloads/eksport.zip "Aga"`.
- Stan: `python sebastian.py dodatek pamiec status` · ustawienia: `… dodatek pamiec ustawienia` (np. `ustaw pytania_godzina 20:00`).

## Jak zdobyć eksporty
- ChatGPT: Ustawienia → Kontrola danych → Eksportuj dane (link do zipa przychodzi mailem).
- Claude: Ustawienia → Prywatność → Eksportuj dane.
- Gemini: takeout.google.com → „Moja aktywność” → Aplikacje Gemini.

Duży eksport (tysiące rozmów) model przerabia przez kilka godzin albo dni — postęp widać w zakładce.
Gdy ktoś rozmawia z Sebastianem, nauka robi przerwę, żeby odpowiedzi były szybkie.
