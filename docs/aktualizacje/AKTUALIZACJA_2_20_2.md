# Sebastian 2.20.2 — Rekrutacja: dojazd liczy się od razu

Działa od 2.16.1 do 2.20.1.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_20_2.py
```

Przyczyna: czasy dojazdu i nowy procent dla starszych ofert liczyły się tylko wtedy, gdy Sebastian nie miał nic innego do roboty —
a przy kolejce nowych linków i przepisywaniu listów ta chwila nie nadchodziła.

Teraz:
- w każdym obrocie pracy w tle (co ok. minutę) Sebastian przelicza procenty i liczy dojazd dla kilku ofert (najpierw tych z gwiazdką, potem najnowszych);
- po otwarciu oferty bez dojazdu liczy go od razu — strona odświeża się sama po kilku sekundach;
- gdy usługa map nie odpowie, na stronie oferty pojawia się powód zamiast „Liczę…”, a próba wraca po 15 minutach.
