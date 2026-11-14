# Sebastian 2.14.4 — eleganckie maile Sebastiana i dokładniejsza diagnoza cal.com

Wymaga wersji 2.14.3.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_14_4.py
python sebastian.py dodatek gwaranci calcom test
```

## `calcom test` — co pokazuje

Dla każdego gwaranta z podpiętym cal.com:
- ostatni odczyt wolnych terminów i ewentualny błąd,
- listę publicznych wydarzeń konta i ostrzeżenie, gdy podpiętego wydarzenia na niej nie ma (ukryte albo inny adres),
- ustawienia wydarzenia: długość, ukryte, potwierdzanie, lokalizacje, dodatkowe pola obowiązkowe (tych Sebastian nie wypełnia), minimalne wyprzedzenie, limity,
- liczbę wolnych terminów na 14 dni i cztery najbliższe.

Na końcu: ostatnia odmowa rezerwacji — co Sebastian wysłał (bez danych adepta) i pełna odpowiedź cal.com.

## Skrzynka

`poczta --zmien`: Enter = sebastian.k.kwiatkowski@gmail.com; Sebastian nie przyjmie tekstu, który nie jest adresem e-mail, ani hasła innego niż 16 liter. Zapisany wcześniej błędny adres jest pomijany.

## Wygląd maili Sebastiana

Wszystkie maile, które Sebastian wysyła **od siebie**, mają teraz jeden, spokojny i elegancki wygląd (nowy plik `mail_szablon.py`):
jasne tło, jedna biała karta, mała sygnatura „SEBASTIAN” u góry, wyraźny tytuł, krótki tekst, szczegóły w cienkich wierszach
(etykieta nad wartością), jeden czarny przycisk główny i ewentualnie drugi z obrysem, cicha stopka. Bez emoji w tytułach.

| Maile | Co się zmienia |
| --- | --- |
| Gwaranci (prośby, potwierdzenia, odmowy, przypomnienia) | Nowy wygląd. |
| Owca (rano, motywacja, wieczór, etapy rekrutacji, „Mam pomysł”, raport) | Ten sam wygląd, z małą ilustracją owcy. |
| Powiadomienia Rekrutacji (dotąd zwykły tekst) | Nowy wygląd. |
| Odpowiedzi Sebastiana w rozmowie z Agą i umówione przypomnienia | Jak list: sam tekst w karcie i podpis. |
| Aplikacje, podziękowania i przypomnienia **w imieniu Agi do pracodawców** | Bez zmian — rekruterzy dostają zwykły, osobisty tekst. |

Zasada na przyszłość (w `mail_szablon.py` i DOKUMENTACJA.md): każdy nowy mail Sebastiana składamy przez `mail_szablon.render(...)` albo `mail_szablon.letter(...)`.
