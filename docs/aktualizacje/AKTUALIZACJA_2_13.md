# Sebastian 2.13 — Rekrutacja: rozmowa z Agą

Wymaga wersji 2.12.1 (albo 2.12).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_13.py
```

Po aktualizacji uruchom ponownie WhatsAppa Sebastiana (instalator robi to sam, jeśli działa jako usługa).

## Co się zmienia dla Agi

Aga może po prostu odpisać Sebastianowi:
- **mailem** — „Odpowiedz” na dowolny mail owcy albo nowy mail na skrzynkę Sebastiana,
- **na WhatsAppie** — jeśli jej numer jest na liście Sebastiana (`python sebastian.py wa-user`); wiadomość zaczynająca się od „/” trafia do zwykłego Sebastiana,
- **w panelu** — nowa zakładka **Rozmowa**.

Sebastian odpisuje po kilku minutach (mail) albo od razu (WhatsApp, panel): życzliwie i krótko, najpierw przyjmuje to, co napisała, potem delikatnie, ale konsekwentnie proponuje mały krok albo pyta o termin.

| Aga pisze | Sebastian |
| --- | --- |
| „Nie mam dziś czasu” | „Jasne, rozumiem. Dziś już nie przypominam. Kiedy będziesz mogła usiąść do ofert?” — i do końca dnia owca milczy. |
| „W czwartek o 10” | Potwierdza i w czwartek o 10:00 przypomina się (WhatsApp albo mail — tam, gdzie rozmawiali). |
| „Od jutra wyjeżdżam do niedzieli” | Życzy udanego wyjazdu, wstrzymuje codzienne maile owcy do niedzieli, pyta albo potwierdza, kiedy się odezwać. Dni przerwy nie przerywają serii. |
| „Wróciłam, działamy” | Kończy przerwę, owca wraca do codziennego rytmu. |
| „Dziś zrobię 15” | Ustawia cel dnia na 15. |
| Zmęczenie, stres | Najpierw empatia, bez pchania; proponuje odpoczynek i najmniejszy krok na później. |

## Pamięć

- **Dziennik rozmowy**: wiadomości Agi i Sebastiana, także maile owcy, powiadomienia na WhatsAppie i raporty — dzięki temu Sebastian wie, do czego Aga odpisuje i co już ustalili.
- **Pamięć faktów**: krótkie, trwałe fakty z rozmów (dostępność, plany, preferencje co do ofert, co ją motywuje). Bez spraw zdrowotnych i prywatnych. Aga widzi je w zakładce Rozmowa i może usunąć każdy przyciskiem „Zapomnij”.
- Wszystko leży lokalnie w bazie dodatku (`data/`), nie w repozytorium.

## Kto pisze i co trafia do Google

Ten sam łańcuch co listy: Gemini → Bielik → model Sebastiana; gdy żaden nie odpowie — proste odpowiedzi z reguł. Do Gemini idzie treść rozmowy, sytuacja (liczby z panelu) i pamięć — bez imienia i nazwiska, e-maila, telefonu i adresu. Kto woli rozmowę tylko na Macu: Ustawienia → Klucze → pisanie „lokalnie”.

Odpowiedzi są sprawdzane (rodzaj żeński do Agi, męski o Sebastianie, bez znaczników, długość); źle napisana idzie raz do poprawki, potem — reguły.

## Wyłączanie

Ustawienia → Jak pracuję → „💬 Sebastian odpisuje na Twoje maile i WhatsAppy”.

## Dla programisty

- `dodatki/rekrutacja/rozmowa.py`: `reply_to`, `check_mail` (skrzynka Sebastiana co 2 min), `on_whatsapp`, `tick` (przypomnienia), przerwy owcy w meta `owca_przerwy`.
- Tabele: `rozmowa`, `rozmowa_pamiec`, `rozmowa_przypomnienia`.
- `dodatki_host.on_message`: wiadomość od właściciela → `on_message`, od innej osoby z listy → `on_user_message` (odpowiedź wraca do tej osoby). `whatsapp.py` przekazuje dodatkom wiadomości wszystkich osób z listy; dodatki bez `on_user_message` niczego nie zauważą.
