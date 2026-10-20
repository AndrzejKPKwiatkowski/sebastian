# Sebastian 2.4 — WhatsApp: rodzina i podsumowania Twojego WhatsAppa

## Co nowego

**1. Żona (i inne bliskie osoby) może pisać do Sebastiana.** Widzi tylko **sprawy prywatne**: prywatną pocztę, prywatne zadania, kalendarz i prywatne notatki. Poczty firmowej, klientów, dokumentów, Bieżących spraw i Twojego WhatsAppa nie zobaczy. Dostaje własny poranny przegląd z głosówką („Hej Kasiu!”). Może pytać (`kalendarz`, `jutro`, `zadania`, `pilne`, `poczta`) i zostawiać notatki (`zapamiętaj: …` → trafia do Twojej Pamięci bota jako „Od Kasia: …”). Nie może zamykać zadań. Jej rozmowy z Sebastianem widzisz w panelu, o czym Sebastian sam ją uprzedza w powitaniu.

**2. Sebastian czyta Twojego WhatsAppa i podpowiada.** Co rano (w przeglądzie i osobną wiadomością „📱 WhatsApp od wczoraj”):
- kto pisał i w jakiej sprawie,
- **📞 Oddzwoń** — kto dzwonił, a Ty się potem nie odezwałeś,
- **✉️ Odpisz** — kto czeka na Twoją odpowiedź,
- **🗣 Porozmawiaj** — sprawy na rozmowę, nie na wiadomość,
- **💬 Warto się odezwać** — z kim często piszesz, a od dwóch tygodni cisza.

Na żądanie: `whatsapp` / `kto pisał`, `do kogo`, `rozmowa Jan`.

Połączenie **tylko czyta**: Sebastian nic nie wysyła z Twojego konta, nie oznacza wiadomości jako przeczytanych i nie pokazuje Cię „online”. Rozmowy zostają na Macu (90 dni) i analizuje je tylko lokalny model. Zbieranie zaczyna się od chwili połączenia.

## Instalacja

Wymaga wersji 2.3.

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_4.py
```

Na końcu aktualizator zaproponuje oba kroki poniżej (możesz je zrobić później).

## Żona

```bash
python sebastian.py wa-user dodaj
```

Program zapyta o numer, imię, formę w powitaniu (np. „Kasiu”), kim jest (np. „żona”), przegląd i głosówkę. Sebastian sam się z nią przywita.

⚠ Działa tylko wtedy, gdy Sebastian ma **osobny numer**. Jeśli połączyłeś go z własnym numerem (czat „Ty”), żona nie może z nim pisać.

## Twój WhatsApp

```bash
python sebastian.py wa-watch login
```

Zeskanuj kod QR **swoim** telefonem (ten z Twoim numerem): WhatsApp → Ustawienia → Połączone urządzenia → Połącz urządzenie. Następnego ranka przyjdzie pierwsze podsumowanie.

Przydatne:

```bash
python sebastian.py wa-watch                                    # stan
python sebastian.py wa-watch podsumowanie                       # podsumowanie teraz (w Terminalu)
python sebastian.py wa-set WA_WATCH_IGNORE "kurier, bank"       # kogo pomijać
python sebastian.py wa-set WA_WATCH_GROUPS tak                  # także grupy
python sebastian.py wa-watch off                                # wstrzymaj · wa-watch usun — odłącz i usuń dane
```

## Uczciwie o ryzyku

To nieoficjalne połączenie (jak WhatsApp Web) na **Twoim głównym numerze**. Samo czytanie to najbezpieczniejszy sposób korzystania, ale ryzyko blokady przez WhatsApp nie jest zerowe. W bazie na Macu są rozmowy Twoich znajomych i klientów, więc włącz FileVault. Nic nie trafia do nauki ani do Open WebUI.

Szczegóły: DOKUMENTACJA.md, rozdziały 8b.8 i 8b.9.
