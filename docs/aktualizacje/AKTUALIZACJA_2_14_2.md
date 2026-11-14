# Sebastian 2.14.2 — WhatsApp: odpowiedzi w ten sam czat

## Problem
Sebastian odbierał wiadomości właściciela i wysyłał odpowiedzi (status `sent`, serwer WhatsAppa je przyjmował), ale nie docierały one do telefonu.
WhatsApp przenosi rozmowy na nową adresację („LID”). Wiadomość wysłana na sam numer telefonu (`…@s.whatsapp.net`) bywa przyjęta przez serwer,
a mimo to nie pojawia się w czacie, w którym właściciel pisze.

## Zmiana
- Odpowiedź idzie dokładnie w czat, z którego przyszła ostatnia wiadomość danej osoby (także czat o adresie LID).
  Dopóki po starcie nikt nie napisał, Sebastian pisze jak dotąd, na numer telefonu.
- Dziennik (`data/logs/whatsapp.log`) pokazuje: z jakiego czatu pisze właściciel, każdą wysyłkę (adres) i potwierdzenie
  „doręczona” / „przeczytana” od WhatsAppa. Brak potwierdzenia = wiadomość nie dotarła do telefonu.
