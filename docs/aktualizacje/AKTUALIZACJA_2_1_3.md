# Sebastian 2.1.3 — spokojna obsługa wygaśnięcia logowania do Dysku

Logowanie do Dysku Google wygasa co 7 dni (tryb „Testowanie” aplikacji Google). Wcześniej nauka próbowała wtedy połączyć się z Dyskiem przed każdym wątkiem i za każdym razem wpisywała `Nie udało się odświeżyć logowania Google: RefreshError`.

Teraz:

- **Jeden komunikat** w dzienniku i powiadomienie na Macu, najwyżej raz na dobę.
- **Baner w zakładce Nauka**, a `check` pokazuje to jako „do sprawdzenia”.
- **Poczta uczy się dalej,** a wiedza z Dysku zostaje.
- Ponowna próba połączenia następuje dopiero po nowym logowaniu (nauka zauważa je sama, bez restartu) albo co 12 godzin.
- **Nowe polecenie `learn-drive`** z wyborem:

```
python sebastian.py learn-drive

Dysk Google: logowanie wygasło — poczta uczy się dalej …

Co zrobić?
  1 — Zaloguj się ponownie (ok. 1 minuta, otworzy się przeglądarka). Logowanie działa 7 dni.
  2 — Wyłącz Dysk. Nauka czyta tylko pocztę; wiedza już zebrana z Dysku zostaje.
  3 — Nic nie zmieniaj
```

Bez menu: `learn-drive login`, `learn-drive off`, `learn-drive on`, `learn-drive status`.

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_1_3.py
python sebastian.py learn-drive
```
