# Sebastian — lokalne centrum spraw, które uczy się o Tobie

Sebastian działa na Macu właściciela. Codziennie pobiera pocztę z trzech skrzynek (tylko odczyt), lokalny model AI (Ollama) ją streszcza i porządkuje, a Ty w panelu decydujesz, co pominąć, co zrobić i na co odpowiedzieć. Moduł **Nauka** czyta w tle Dysk Google, całą pocztę i załączniki, a potem buduje **Bieżące sprawy** i **Profil wiedzy**. Wiedza trafia też do Open WebUI, żeby czat z lokalnym modelem znał kontekst. Moduł **Dokumenty** zamienia duże skany (także pisane ręcznie, np. księgi wieczyste) w mały PDF ze spisem treści i klikalnymi odnośnikami.

**Wersja: 2.2**

## Od czego zacząć

| Potrzebujesz… | Przeczytaj |
| --- | --- |
| zrozumieć cały system, zainstalować go od zera, coś naprawić albo zmienić | **[DOKUMENTACJA.md](DOKUMENTACJA.md)** |
| przejść ze starszej wersji | [docs/aktualizacje/](docs/aktualizacje/) |
| wiedzieć, co zostało przetestowane | [docs/TESTY.md](docs/TESTY.md) |

## Najczęstsze polecenia

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python sebastian.py check           # pełne sprawdzenie: Ollama, panel, poranek, nauka, Dysk, bezpieczeństwo, dokumenty
python sebastian.py doctor          # czy Ollama i model działają
python sebastian.py learn-status    # postęp nauki
python sebastian.py learn-drive     # Dysk Google: zaloguj ponownie albo wyłącz
python sebastian.py doc-add ~/Downloads/KW.pdf   # skan do opracowania (albo panel → Dokumenty)
python sebastian.py doc-list        # postęp opracowania dokumentów
python sebastian.py backup          # kopia bazy panelu
```

Panel: **http://127.0.0.1:8765** (tylko na tym Macu).

## Zasady

- Wszystko lokalnie. Skrzynki tylko do odczytu, poza świadomą wysyłką odpowiedzi z panelu.
- AI proponuje, decyzja należy do człowieka.
- Hasła wyłącznie w Pęku kluczy macOS.
- **Folder `data/` (maile, bazy, klucze) nigdy nie trafia do repozytorium.** Przed każdym `git push` sprawdź `git status`. Szczegóły: DOKUMENTACJA.md, rozdział 13.
