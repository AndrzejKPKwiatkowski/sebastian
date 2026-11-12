# Sebastian 2.10 — Rekrutacja: więcej ofert

Wymaga wersji 2.9 (albo 2.8.5 — zawiera wszystko z 2.9).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_10.py
```

| Obszar | Zmiana |
| --- | --- |
| Alerty z portali | Maile z alertami Pracuj.pl, OLX, Indeed, LinkedIn, justjoin.it, RocketJobs, Aplikuj.pl, GoWork, Praca.pl i innych (w skrzynce Agi) zamieniane na oferty w kolejce: stanowisko, firma, miejsce i opis z maila, link. Te same filtry co zawsze (czego Aga nie chce, dojazd, duplikaty). Strony portali nie są otwierane automatycznie; oferta z formularzem portalu trafia do „przez formularz” z gotowym zestawem, a gdy firma ma adres na swojej stronie — może pójść mailem. Alert nie wywołuje powiadomień; działa też przed pierwszą wysyłką. Starsze niż 5 dni — pomijane. Przełącznik: Ustawienia → Klucze. |
| CBOP (urzędy pracy) | Oficjalna usługa ePraca/CBOP: raz na dobę wieczorem, województwo małopolskie (kod 12), pełna treść ofert z adresem e-mail do aplikowania, gdy urząd go podaje. Wymaga nazwy partnera nadanej przez MRPiPS (Ustawienia → Klucze → CBOP). Wynik ostatniego pobrania widać w Ustawieniach i na stronie „Więcej ofert”. |
| Zakładka „Wyślij do Sebastiana” | Na stronie „Więcej ofert”: przycisk do przeciągnięcia na pasek zakładek. Kliknięty na stronie ogłoszenia otwiera panel z linkiem i treścią do dodania (Aga potwierdza jednym przyciskiem). |
| Strona „Więcej ofert” | Lista 8 kroków (alerty na portalach, widoczne CV, agencje pracy, zakładka) z odhaczaniem, frazy do alertów, statystyka ofert z alertów z ostatniego tygodnia. Link na stronie „Dziś”. |
| Owca: „Mam pomysł!” | Jednorazowy mail w najbliższy dzień roboczy rano po instalacji: jak zapisać się na alerty, lista kroków, frazy i przycisk do strony „Więcej ofert”. |
