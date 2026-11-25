# Sebastian 2.36.2 — pracuj.pl blokował Maca

Diagnoza (25.11.2026): pracuj.pl odpowiadał błędem 429 / Cloudflare 1015 („You are being rate limited”) — także dla ogłoszeń,
które w przeglądarce Agi działają. Seria otwarć (lista linków, szacowanie pensji, przygotowanie, test) wyglądała dla portalu jak robot.
Wcześniej taka strona blokady albo pusta „skorupa” była brana za ogłoszenie → „Firma do ustalenia”, kawałek adresu jako stanowisko, 8%.

- Strony z pracuj.pl otwierane najwyżej co 30 s; po blokadzie 45 minut przerwy — Sebastian nie puka wtedy do portalu.
- Strona blokady / pusta strona nie jest brana za ogłoszenie; oferta czeka „do uzupełnienia” z jasnym komunikatem
  i podpowiedzią: otwórz u siebie → zakładka „Wyślij do Sebastiana” albo wklej treść. Po przerwie Sebastian sam próbuje jeszcze raz (do 4 razy).
- Treść pobrana przy szacowaniu pensji jest zapisywana — jedno otwarcie strony na ofertę zamiast dwóch.
- Stare śmieci z pracuj.pl są czyszczone i pobierane jeszcze raz (pominięte zostają pominięte).
- `sprawdz-linki` domyślnie tylko wypisuje dane z bazy; strony otwiera dopiero z `--pobierz`.
