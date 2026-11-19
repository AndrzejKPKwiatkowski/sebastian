# Sebastian 2.20 — Rekrutacja: ważne oferty z gwiazdką

Działa od 2.16.1 do 2.19.2 (zawiera wszystkie zmiany po drodze).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_20.py
```

- Na stronie każdej oferty, obok nazwy firmy: „☆ Oznacz jako ważną”. Kliknięcie zmienia na „★ Ważna”; drugie kliknięcie zdejmuje gwiazdkę.
- Nowa zakładka „★ Ważne” obok „Do zrobienia” — wszystkie oznaczone oferty (najnowsze oznaczenia na górze), z licznikiem.
- Na listach („Aplikacje”, „Do zrobienia”) oznaczone oferty mają ★ przed nazwą firmy.
- Baza: nowa kolumna `gwiazdka` (data oznaczenia) dodaje się sama przy starcie.
