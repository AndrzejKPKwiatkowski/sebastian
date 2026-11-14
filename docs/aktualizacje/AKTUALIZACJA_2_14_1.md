# Sebastian 2.14.1 — Gwaranci z cal.com

## Co nowego
- **Gwarant z cal.com** w onboardingu wkleja tylko link do swojego wydarzenia (np. `https://cal.com/nazwa/spotkanie-gwaranckie`). Nie podaje linku iCal ani godzin — dostępność, podłączone kalendarze, bufory i limity liczy jego cal.com. W Sebastianie ustawia tylko, ile spotkań gwaranckich w tygodniu daje.
- Wolne terminy z cal.com czytam co 5 minut (publiczne API cal.com, `GET /v2/slots`) dla każdej długości spotkania (30, 60, 75 min). Adept widzi też godziny spoza siatki co 30 min (np. 10:15).
- **Rezerwacja trafia od razu do cal.com gwaranta** (`POST /v2/bookings`, jak zwykły formularz rezerwacji): adept jest uczestnikiem, w notatce jest typ spotkania, miejsce i wiadomość od adepta. Prośbę, przypomnienia i zaproszenia wysyła cal.com; Sebastian dokłada mail dla adepta (z prośbą o feedback po usłudze) i powiadomienie na WhatsAppie.
- Gdy cal.com odmówi (termin zajęty w międzyczasie), Sebastian bierze następnego gwaranta w kolejności przydziału.
- Akceptacja, odrzucenie i odwołanie w cal.com wracają do Sebastiana (`GET /v2/bookings/{uid}`). Gdy cal.com wymaga do tego klucza API: `python sebastian.py dodatek gwaranci calcom klucz` (opcjonalne).
- Odwołanie przez adepta w panelu odwołuje też rezerwację w cal.com.
- **Domyślnie podpięty cal.com**: osoba z polem `"calcom"` w `data/dodatki/gwaranci/struktura.json` jest od razu gotowym gwarantem z tym wydarzeniem (jednorazowo — jeśli sama przełączy się na iCal, zostaje przy iCal).

## Polecenia
- `python sebastian.py dodatek gwaranci calcom` — kto ma cal.com i kiedy był odczyt
- `python sebastian.py dodatek gwaranci calcom "Imię Nazwisko" https://cal.com/nazwa/wydarzenie` — podpięcie za kogoś
- WhatsApp: `gwaranci calcom Imię Nazwisko https://cal.com/nazwa/wydarzenie`
