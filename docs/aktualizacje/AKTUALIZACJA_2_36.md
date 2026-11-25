# Sebastian 2.36 — linki, Edytuj CV, dobór pod ofertę

Wgranie: Centrum → „Aktualizuj Sebastiana”. Działa od 2.16.1 do 2.35.

- **Linki do ogłoszeń**: strona otwierana jak w zwykłej przeglądarce; Sebastian czyta też dane ogłoszenia zapisane w stronie dla wyszukiwarek
  (firma, stanowisko, miasto, wynagrodzenie, opis) — działa na portalach, które treść pokazują dopiero skryptem. Gdy model nie poda firmy,
  bierze ją z tytułu strony. Błędy mówią po ludzku, co się stało (portal blokuje, ogłoszenie wygasło…).
  Diagnoza na Macu: `python sebastian.py dodatek rekrutacja sprawdz-linki 20`.
- **Edytuj CV**: odznaczone stanowisko (np. kwalifikacja wojskowa) nie wraca przy kolejnej edycji; przycisk „Zapisz i ułóż CV” także pod profilem.
- **Dobór pod ofertę**: punkty, cechy i narzędzia według słów z ogłoszenia (wymagania i obowiązki liczą się podwójnie) — różne oferty, różne punkty.
- **Gastronomia, kasa, żłobek**: Sebastian wybiera najwyżej 2 punkty (ręcznie możesz dodać więcej).
