# Sebastian 2.32 — obserwacja numeru dla klientów

Wgranie: Centrum → „Aktualizuj Sebastiana” albo z Terminala: `python aktualizator.py uruchom data/aktualizacje/Sebastian_aktualizacja_2_32.py`. Działa od 2.16.1 do 2.31.

- Sebastian może obserwować **kilka numerów WhatsApp** (tylko odczyt). Drugi numer łączysz:
  `python sebastian.py wa-watch login --numer 661285780` — na telefonie z tym numerem: WhatsApp → Ustawienia → Połączone urządzenia → Połącz urządzenie
  (albo `--kod`, żeby dostać kod do wpisania zamiast QR). Stan: `wa-watch status`. Wyłączenie: `wa-watch off --numer 661285780`.
- Głosówki od klientów na tym numerze są przepisywane i — gdy razem ponad 2 minuty — podsumowywane jak dotąd; w podsumowaniu widać numer.
- Po połączeniu telefon przesyła historię: głosówki z ostatnich 3 dni zostaną pobrane i przepisane (o ile WhatsApp jeszcze je trzyma).
- Głosówki znikające i „do jednorazowego odsłuchania” są teraz czytane. Nieudane przepisanie widać w logu.
- Pamięć: koniec chwilowych blokad bazy przy składaniu profilu.
