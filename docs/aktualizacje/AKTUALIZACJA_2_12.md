# Sebastian 2.12 — Rekrutacja: listy pisane przez Google Gemini

Wymaga wersji 2.11 (albo 2.10 — zawiera wszystko z 2.11).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_12.py
```

## Włączenie (2 minuty)

1. aistudio.google.com → zaloguj się kontem Google → **Get API key** → **Create API key** → skopiuj.
2. Panel → Ustawienia → Klucze → **Google Gemini — klucz API** → wklej → Zapisz.

Bez klucza wszystko działa jak dotąd (Bielik / model Sebastiana).

| Obszar | Zmiana |
| --- | --- |
| Pisanie | List motywacyjny, opis w CV, wyjaśnienia dopasowania i korekta językowa idą najpierw do Gemini; gdy Gemini nie odpowie, ma przerwę albo wyczerpany limit — Bielik, a potem model Sebastiana. Kontrola prawdy i języka zostaje na Macu (to samo sito). |
| Dane | Z zapytań usuwane są imię, nazwisko, e-mail, telefon, LinkedIn i adres; podpis i dane kontaktowe są dopisywane lokalnie. Zarobków nie ma w faktach. Uwaga: na darmowym poziomie Google może używać treści zapytań do ulepszania swoich produktów; po podpięciu płatności (przedpłata od 5 USD) — nie. |
| Styl | W poleceniu wskazówki Agi (naturalnie, ciepło, profesjonalnie, bez frazesów i myślników, zmiana pracy jako świadoma decyzja) i dwa wzorcowe listy oparte na jej prawdziwych faktach (tylko jako wzór tonu). |
| Model | Wybierany automatycznie: najnowszy stabilny „flash” dostępny dla klucza (bez lite/obrazów); można wpisać własny w Ustawieniach. |
| Limity | Dzienny limit zapytań (domyślnie 300). Po błędzie limitu Google (429) — godzina przerwy, po innych błędach 10–30 minut; w tym czasie pisze model lokalny. Stan widać w Ustawieniach. |
| Czekające listy | Aplikacje czekające na Agę (do zatwierdzenia, do sprawdzenia, formularz) dostają nowy list od Gemini w tle, po jednym na obrót, z nowym PDF. Zatwierdzonych i wysłanych nie ruszam. |
