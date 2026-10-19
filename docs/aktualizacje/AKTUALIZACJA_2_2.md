# Sebastian 2.2 — Dokumenty: duże skany → uporządkowany PDF

Nowa zakładka **Dokumenty**. Wrzucasz opasły skan, np. księgę wieczystą (drukowaną, maszynową, pisaną ręcznie, także niemiecki Grundbuch). Sebastian na Macu:

1. **prostuje i zmniejsza skan** i dodaje warstwę tekstu (ocrmypdf + Tesseract),
2. **czyta każdą stronę lokalnym modelem wizyjnym**, który „widzi” stronę: druk poprawia, pismo ręczne czyta w powiększonych pasach **dwa razy** i zaznacza miejsca, w których odczyty się różnią,
3. **porządkuje wpisy** (działy I-O, I-Sp, II, III, IV, wzmianki). Każdy wpis musi mieć cytat z odczytu, więc model nie może dopisać wpisu, którego nie ma,
4. **składa mały PDF**: na 1. stronie spis treści z linkami (stan aktualny, wszystkie wpisy, do wyjaśnienia, odczyt, skany), przy każdym wpisie link „skan s. N”, a w bocznym panelu zakładki do każdej strony.

Duży dokument może się analizować 1–2 dni. Postęp jest zapisywany po każdej stronie, więc restart Maca nie szkodzi. W tym czasie nauka z poczty czeka. W panelu możesz porównać odczyt ze skanem, poprawić go i jednym kliknięciem złożyć PDF z poprawkami.

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_2.py
```

Aktualizator:

- sprawdza wersję 2.1.3 i doinstalowuje biblioteki (`reportlab`, `numpy`, `fonttools`),
- zatrzymuje naukę, robi kopię w `backups/aktualizacja-2.2-…`, podmienia pliki, sprawdza uruchomienie (w razie błędu przywraca kopię), przeładowuje panel i naukę,
- **na końcu pyta** (możesz odmówić i zrobić to później):
  - `brew install ocrmypdf` — prostowanie, kompresja i OCR skanów (kilka minut),
  - `ollama pull qwen2.5vl:7b` — model wizyjny (ok. 6 GB).

Nie zmienia maili, haseł, ustawień ani decyzji.

## Pierwsze użycie

1. **Sprawdzenie:** `python sebastian.py check` → sekcja „6. Dokumenty”.
2. **Test na 2–3 trudnych stronach** (nic nie zapisuje, pokazuje odczyt):
   ```bash
   python sebastian.py doc-test ~/Downloads/KW.pdf --strona 5
   ```
3. **Dodanie całego dokumentu:** panel → **Dokumenty** → wybierz plik → **Wgraj**. Bardzo duże pliki możesz też skopiować do `data/dokumenty/wrzuc-tutaj/` albo dodać w Terminalu:
   ```bash
   python sebastian.py doc-add ~/Downloads/KW.pdf --nazwa "KW Kraków, ul. Przykładowa 1" --typ kw
   ```
4. **Postęp:** panel → Dokumenty albo `python sebastian.py doc-list` (z szacunkiem pozostałego czasu).
5. **Po opracowaniu:** **Otwórz PDF**. Przejrzyj strony „do sprawdzenia” (żółta ramka), popraw odczyt, zaznacz „Strona sprawdzona”, a na koniec kliknij **Złóż PDF z poprawkami**.

## Nowe polecenia

| Polecenie | Co robi |
| --- | --- |
| `doc-add PLIK [--nazwa N] [--typ auto\|kw\|ogolny]` | Dodaje skan do kolejki (kopiuje go) |
| `doc-list` / `doc-status NR` | Postęp / szczegóły |
| `doc-test PLIK --strona N` | Próbny odczyt jednej strony |
| `doc-run [NR]` | Analiza w oknie Terminala, gdy nauka nie działa w tle |
| `doc-pause NR` / `doc-resume NR` | Wstrzymanie / wznowienie |
| `doc-rebuild NR [pdf\|struktura\|strony]` | Ponowne złożenie PDF / uporządkowanie / czytanie stron |
| `doc-export NR` | ZIP ze stronami do sprawdzenia |
| `doc-remove NR` | Usunięcie dokumentu |

Ustawienia `DOC_*` (model, podwójne czytanie, rozdzielczość, kompresja…): DOKUMENTACJA.md, rozdział 12.2. Szczegóły działania i rozwiązywanie problemów: rozdział 8a.

## Uczciwie o granicach

- To **opracowanie robocze**. W sprawach prawnych rozstrzyga odpis z sądu. Dlatego każdy wpis ma link do strony skanu.
- Pismo ręczne, zwłaszcza stare i niemieckie (kurrenta), model czyta z błędami. Miejsca niepewne są zaznaczone na żółto i trafiają „do sprawdzenia”.
- Cyfry (działki, kwoty) zawsze warto sprawdzić na skanie.

## Gdyby coś poszło nie tak

Aktualizator sam przywraca kopię, gdy test po podmianie nie przejdzie. Ręczny powrót do 2.1.3:

```bash
python sebastian.py learn-stop
cp -R backups/aktualizacja-2.2-*/files/* .
rm learner_docs.py learner_docs_web.py test_docs.py templates/docs.html templates/doc.html templates/doc_page.html
launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel
python sebastian.py learn-start
```

Folder `data/dokumenty/` możesz zostawić. Wersja 2.1.3 go nie używa.
