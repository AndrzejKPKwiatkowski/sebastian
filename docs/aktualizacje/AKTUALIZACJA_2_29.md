# Sebastian 2.29 — Głosówki: podsumowania długich nagrań

Wgranie: Centrum dowodzenia → „Aktualizuj Sebastiana” (albo z Terminala: `python aktualizator.py uruchom data/aktualizacje/Sebastian_aktualizacja_2_29.py`). Działa od 2.16.1 do 2.28.

- Ktoś nagra do Ciebie naraz głosówki (odstępy do 5 minut) o łącznej długości ponad 2 minut → po 5 minutach od ostatniej
  Sebastian wysyła na WhatsAppie podsumowanie: **o czym**, **o co pyta**, **do zrobienia** (✅), a zaraz potem pytanie,
  czy przysłać całą treść.
- Odpowiedzi: *tak* — cała treść (długa w częściach) · *nie* — nic · *treść 3* — dowolna wcześniejsza paczka · *głosówki* — lista.
- Przepisywanie i podsumowanie dzieją się lokalnie na Macu (mlx-whisper + lokalny model). Nagrania nie są zapisywane.
- W godzinach ciszy podsumowanie czeka do rana.
- Jedyne działanie wstecz: wszystkie głosówki od Witolda Michno z 22.11.2026 — jedno podsumowanie zaraz po wgraniu.
  Jeśli ich nie znajdzie, napisze o tym. Ręcznie: `python sebastian.py dodatek glosowki wstecz "Witek" 2026-11-22`.
- Ustawienia: `python sebastian.py dodatek glosowki ustawienia` (próg 120 s, przerwa 5 min, grupy wyłączone).
