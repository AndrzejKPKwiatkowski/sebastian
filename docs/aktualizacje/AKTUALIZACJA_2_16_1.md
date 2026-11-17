# Sebastian 2.16.1 — Gwaranci: wspólna pula menedżera

Wymaga wersji 2.16.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_16_1.py
python sebastian.py dodatek gwaranci usluga instaluj
```

## Zasada

Adept może rezerwować spotkania gwaranckie dopiero wtedy, gdy **jego bezpośredni menedżer udostępni swoje spotkania do wspólnej puli**
(przejdzie onboarding gwaranta i ustawi limit większy od zera; urlop / „Wstrzymaj” się liczy — menedżer już się zaangażował).
Ma to motywować obie strony: planera, żeby poprosił, i menedżera, żeby się zapisał.

## Co widzi adept, gdy menedżer jeszcze się nie zapisał

- Złotą ramkę „Rezerwacja czeka na Twojego menedżera” z nazwiskiem menedżera i prośbą o kontakt.
- Liczbę dni z wolnymi terminami, które czekają na niego w puli.
- Pełny kalendarz i godziny — **widoczne, ale zablokowane** (nie da się ich kliknąć; serwer też odmawia rezerwacji).
- Przycisk **„Poproś menedżera o udostępnienie”**: mail do menedżera w stylu Sebastiana z jego osobistym linkiem i trzema krokami
  (raz na 24 h), a Agi dostaje krótką wiadomość na WhatsAppie. Gdy menedżer nie ma maila w systemie — tylko WhatsApp do Agi.

Gdy menedżer udostępni spotkania (onboarding w panelu, `calcom` albo cokolwiek, co ustawi go jako gotowego), Sebastian w ciągu minuty
wysyła adeptom, którzy prosili, mail „Możesz już rezerwować spotkania gwaranckie”.

Osoby bez menedżera nad sobą (np. dyrektor) nie są blokowane.

## Wyłączenie

```bash
python sebastian.py dodatek gwaranci ustaw pula_menedzera nie
```
