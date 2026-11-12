# Sebastian 2.8.4 — Rekrutacja: poprawki po pierwszych prawdziwych odpowiedziach

Wymaga wersji 2.8.2 albo 2.8.3 (zawiera wszystko z 2.8.3).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_8_4.py
```

| Obszar | Zmiana |
| --- | --- |
| List motywacyjny | Kontrola odrzuca list pisany DO kandydatki („Droga Agnieszko”, „przygotowywałaś”, „Twoje”), głosem pracodawcy („szukamy”, „oferujemy”), z jej imieniem w treści albo bez pierwszej osoby. Taki list jest pisany od nowa ze wskazaniem błędu, a po drugiej nieudanej próbie — list z faktów. Prompt jednoznacznie: „jesteś kandydatką i piszesz swój list”. |
| Rozpoznawanie odpowiedzi | Nowe rodzaje: „potwierdź aplikację” (np. eRecruiter „Czy to Twoja aplikacja?”) i „reklama portalu”. Zaproszenie tylko przy wyraźnym zaproszeniu (słowo „Teams” czy „Zoom” już nie wystarcza); model nie zrobi zaproszenia z potwierdzenia ani reklamy. Odmowa tylko przy wyraźnym zdaniu o odrzuceniu („skontaktujemy się wyłącznie z wybranymi” to potwierdzenie) — podziękowanie po odmowie wychodzi tylko wtedy. |
| Powiadomienia | Potwierdzenia, reklamy i „inne” bez WhatsAppa, bez maila i bez pozycji w raporcie; „potwierdź aplikację” — w panelu i w raporcie. |
| Wiadomość w panelu | Czysta treść (bez „&nbsp;” i pustych linii), przyciski z wiadomości (np. „Tak, to moja aplikacja”) z widoczną domeną, „Otwórz w Gmailu”, streszczenia do Agi w drugiej osobie. Lista odpowiedzi domyślnie bez potwierdzeń i reklam. |
| Oferta | Uzasadnienie dopasowania bez ucinania; warunki Agi (np. „do 20 km albo zdalnie”) nie trafiają do pól oferty. |
| Po instalacji | Zapisane wiadomości rozpoznane na nowo (statusy aplikacji i zaplanowane podziękowania poprawione); czekające i zatwierdzone listy z takimi błędami przygotowane od nowa. |
