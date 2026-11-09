# Sebastian 2.6 — asystent na WhatsAppie

## Co nowego

**Nowa rola: `asystent`.** Osoba, która pomaga Ci w sprawach firmowych (np. Jan Kisiel). Widzi Twoje **firmowe**
zadania, kalendarz i pocztę firmową. Spraw prywatnych, Twojego WhatsAppa, akt osób i dokumentów nie widzi.

Co asystent może napisać do Sebastiana:

| Komenda | Co się dzieje |
| --- | --- |
| `zadania` | lista otwartych zadań firmowych z numerami |
| `szczegóły 3` | skąd jest zadanie nr 3: mail, nadawca, o co chodzi, termin |
| `dodaj zadanie: wysłać ofertę do piątku` | zadanie od razu trafia na listę w panelu; Ty dostajesz wiadomość |
| `zrobione 3` | zamyka zadanie; Ty dostajesz wiadomość |
| `pytanie: czy klientka ma dostać PDF?` | Sebastian przekazuje pytanie Tobie z numerem |
| `pomysł: przypominanie o urodzinach klientów` | zgłoszenie nowej funkcji; trafia do Ciebie i do panelu |
| `pilne`, `poczta`, `kalendarz`, `jutro`, `przegląd`, `zapamiętaj: …` | jak dotąd, ale tylko sprawy firmowe |

**Dla Ciebie:**
- `pytania` — otwarte pytania; `odpowiedz 3: tak, PDF i link do podpisu` — Sebastian odsyła odpowiedź pytającemu
  (gdy pytanie jest jedno, wystarczy `odp: …`),
- `dodaj zadanie: …` — możesz też dodawać zadania sam (`dodaj zadanie: prywatne: …` — prywatne),
- `pomysły` — lista pomysłów; w Terminalu `python sebastian.py wa-pomysly` (całość do skopiowania),
- panel → zakładka WhatsApp → „Pytania do Ciebie i pomysły”.

## Instalacja

Wymaga wersji 2.5.2.

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_6.py
```

## Dodanie asystenta

```bash
python sebastian.py wa-user dodaj 48XXXXXXXXX --imie "Jan Kisiel" --wolacz Janie --kto asystent --dostep asystent --przeglad nie --glos nie
python sebastian.py wa-user
```

Sebastian sam przywita się z Janem i wyśle mu listę komend. Jan pisze na **numer Sebastiana** (ten sam co Aga).
Poranny przegląd dla asystenta (tylko sprawy firmowe) włączysz, podając `--przeglad tak`.

## Uczciwie

- Zadania dodane przez asystenta pojawiają się od razu (bez Twojej akceptacji) — tak ustaliłeś. Każde dostajesz na WhatsAppie.
- Asystent widzi treść firmowych maili (w odpowiedziach i w `szczegóły`), w tym dane klientów.
- Pytania i odpowiedzi przechodzą przez WhatsApp (szyfrowane), kopie zostają na Macu (`data/whatsapp/whatsapp.sqlite3`).
