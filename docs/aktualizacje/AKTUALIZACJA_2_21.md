# Sebastian 2.21 — Centrum dowodzenia Agi i aktualizacje jednym plikiem

Działa od 2.16.1 do 2.20.2. To ostatnia aktualizacja, którą trzeba wgrać w terminalu:

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_21.py
git add -A && git commit -m "Sebastian 2.21: Centrum dowodzenia Agi" && git push
```

## Dla Agi

- Adres: panel Rekrutacji + `/centrum` (np. `http://mac-studio-ai…:8790/centrum`); logo „Sebastian · Centrum” w panelu też tam prowadzi.
- „⤓ Skrót na pulpit” pobiera plik `Centrum_dowodzenia_Agi.url` — położony na pulpicie otwiera Centrum dwuklikiem.
- Kafelki: Rekrutacja, Sebastian, Gwaranci Feniks, Terminal (adresy z `data/centrum.json`, jak w Centrum Andrzeja).
- Wyróżniona (bordo ze złotym) aplikacja **Aktualizuj Sebastiana**:
  1. w czacie z Claude'em opisz, co poprawić, i pobierz plik `Sebastian_aktualizacja_….py`;
  2. upuść go w polu albo wybierz z Pobranych, wpisz hasło do panelu, kliknij „Aktualizuj Sebastiana”;
  3. na żywo widać kroki: kopia zapasowa → pliki → testy → dane → restart → zapis na GitHubie;
  4. na końcu „Brawo, Aga!” z numerem nowej wersji.
- Gdy plik jest dla innej wersji, Centrum mówi wprost, co napisać w czacie (np. „Sebastian ma wersję 2.21”).
- Gdy testy nie przejdą, aktualizacja sama wraca do poprzedniej wersji, a Centrum pokazuje komunikat do wklejenia w czacie.

## Dla Andrzeja

- `aktualizator.py` — sprawdza plik (znaczniki aktualizatora, zgodność wersji), uruchamia go jako osobny proces (przeżywa restart panelu),
  zapisuje postęp w `data/aktualizacje/stan.json` i historię w `historia.json`, potem wykonuje polecenie git z końca aktualizacji
  (`git add … && git commit … && git push`). Pliki aktualizacji zostają w `data/aktualizacje/`.
- Ręcznie: `python aktualizator.py uruchom data/aktualizacje/<plik>.py` albo samo wysłanie na GitHuba: `python aktualizator.py github`.
- `git push` idzie bez pytania o hasło (`GIT_TERMINAL_PROMPT=0`). Jeśli GitHub nie przyjmie (np. brak zapisanego logowania dla usługi),
  Sebastian jest i tak zaktualizowany, a w Centrum jest przycisk „Spróbuj jeszcze raz wysłać na GitHuba”.
- W Centrum Andrzeja (`centrum.py`) doszedł wyróżniony kafelek „Aktualizuj Sebastiana” prowadzący do tego samego miejsca.
- Bezpieczeństwo: wgrać aktualizację może tylko zalogowana osoba, po ponownym wpisaniu hasła panelu, z tokenem CSRF i tylko przez Tailscale.
  Aktualizacja to kod uruchamiany na Macu — wgrywajcie wyłącznie pliki z własnego czatu.
