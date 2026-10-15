# Sebastian 2.1.1 — odporność na „zapętlenie” modelu

Poprawka do modułu Nauka. Wcześniej, gdy lokalny model zaciął się na jednym fragmencie tekstu (w logu: `token repeat limit reached`), cały dokument lub wątek był oznaczany jako błąd. Dzieje się to zwykle przy tabelach z PDF-ów i powtarzalnych załącznikach.

Teraz:

- model dostaje karę za powtórzenia (`repeat_penalty`), więc rzadziej się zacina,
- zacięty fragment jest ponawiany raz z inną temperaturą,
- jeśli dalej się nie da, pomijany jest **tylko ten fragment**, a fakty z reszty dokumentu zostają.

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_1_1.py
python sebastian.py learn-retry
```

Ostatnie polecenie przywraca do kolejki wątki, które wcześniej skończyły się błędem. Aktualizator robi kopię, sprawdza działanie i w razie problemu sam wraca do 2.1.
