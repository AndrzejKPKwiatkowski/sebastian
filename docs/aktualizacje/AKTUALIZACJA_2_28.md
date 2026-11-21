# Sebastian 2.28 — Gwaranci: jeden wspólny link dla wszystkich

Wgranie: Centrum dowodzenia → „Aktualizuj Sebastiana”. Działa od 2.16.1 do 2.27.

- Jeden link dla całego zespołu: `<publiczny adres gwarantów>/witaj`. Wypiszesz go z gotową wiadomością:
  `python sebastian.py dodatek gwaranci wspolny` (albo na WhatsAppie: „gwaranci wspólny link”). Jest też w panelu → Admin.
- Osoba wpisuje mail służbowy `imie.nazwisko@inpartners.pl`. Sebastian rozpoznaje ją w strukturze (stanowisko, przełożony,
  gwarant/adept) i wysyła **na ten mail** jednorazowy link „Ustaw konto” (ważny 48 h). Po ustawieniu hasła gwarant od razu
  przechodzi do podłączenia kalendarza, adept do rezerwacji. Później logowanie mailem i hasłem; „nie pamiętam hasła” = ten sam formularz.
- Mail służbowy, który nie pasuje do nikogo: osoba podaje imię, nazwisko i przełożonego, a Ty w panelu (Admin → Prośby o dostęp)
  klikasz „Przypisz do: …” albo „Dodaj i wyślij link”. Maile spoza wzoru: `python sebastian.py dodatek gwaranci maile "Imię Nazwisko" adres@inpartners.pl`.
- Bezpieczeństwo: nikt nie wejdzie na cudze konto, wpisując cudzy mail — link przychodzi tylko na ten mail. Link najwyżej raz na 2 minuty
  i 6 razy na dobę; po 8 złych hasłach 15 minut przerwy dla tego maila. Hasła zapisane wyłącznie jako skrót (hash).
- Osobiste linki `/l/…` działają jak dotąd. Mail służbowy staje się adresem do zaproszeń, jeśli ktoś nie miał jeszcze żadnego.
