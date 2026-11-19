# Sebastian 2.27 — Rekrutacja: naprawa błędu przy otwieraniu oferty

Wgranie: Centrum dowodzenia → „Aktualizuj Sebastiana”. Działa od 2.16.1 do 2.26.

- Przyczyna „Internal Server Error”: przy liczeniu dojazdu jedna z usług map (np. trasa rowerem) nie odpowiedziała, a strona oferty
  nie umiała pokazać brakującego czasu. Teraz w tym miejscu jest „—”, reszta działa.
- Strona oferty jest odporna na niepełne albo nietypowe dane (dojazd, dopasowanie, składniki procentu, treść ogłoszenia, pensja).
- Gdyby kiedyś coś jednak nie zadziałało: zamiast gołego „Internal Server Error” pojawia się strona „Ups — ta strona się nie otworzyła”
  z krótkim fragmentem do wklejenia w czacie; pełny zapis trafia do `data/dodatki/rekrutacja/bledy.log`.
