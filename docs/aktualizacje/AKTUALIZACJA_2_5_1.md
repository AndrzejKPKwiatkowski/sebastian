# Sebastian 2.5.1 — dlaczego Sebastian nie odpowiada żonie?

Mała poprawka diagnostyczna. Gdy ktoś pisze do Sebastiana, a nie dostaje odpowiedzi, teraz widać dlaczego.

## Co nowego

- `python sebastian.py wa-status` pokazuje:
  - **„Może pisać”** — osoby z listy, ich dostęp (pełny / prywatny) i czy Sebastian już się z nimi przywitał,
  - **„⚠ UWAGA”** — gdy Sebastian jest połączony z Twoim własnym numerem (wtedy nikt poza Tobą nie może z nim pisać),
  - **„Odrzucone”** — ostatnie wiadomości z numerów spoza listy: nazwa z profilu WhatsApp (np. „Aga”) i zamaskowany numer, **bez treści**.
- To samo trafia do logu `data/logs/whatsapp.log` („pominięto wiadomość od …”), najwyżej raz na godzinę na osobę.

## Instalacja

Wymaga wersji 2.5.

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_5_1.py
```

## Jak tego użyć

1. Niech żona napisze do Sebastiana „pomoc”.
2. `python sebastian.py wa-status`
3. Odczyt:
   - jest w „Odrzucone” jako „Aga” → numer na liście jest inny niż ten, z którego pisze. Usuń i dodaj właściwy (`wa-user usun …`, `wa-user dodaj …`), potem `wa-start`;
   - „numer ukryty przez WhatsApp (LID)” → dodaj ją (jeśli trzeba) i uruchom `wa-start` — Sebastian napisze do niej pierwszy, a wtedy WhatsApp zwykle zaczyna podawać numer;
   - „⚠ UWAGA … połączony z Twoim numerem” → potrzebny osobny numer Sebastiana (`wa-login`);
   - nigdzie jej nie ma → wiadomość nie dotarła do Maca: czy usługa działa i jest połączona (ta sama komenda, linia „Usługa w tle”), czy pisze na właściwy numer (linia „Połączenie … konto”).
