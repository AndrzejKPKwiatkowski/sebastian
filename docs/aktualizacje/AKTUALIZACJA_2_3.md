# Sebastian 2.3 — Sebastian na WhatsAppie

Od tej wersji Sebastian jest kontaktem na WhatsAppie:

- **Co rano** (domyślnie 07:00, po porannej analizie poczty) wysyła **krótki przegląd dnia** i **głosówkę**: „Hej Andrzej! …”. W głosówce opowiada szerzej, co dziś najważniejsze, na co uważać i od czego zacząć. Głos powstaje lokalnie na Macu (polski głos Piper).
- **W ciągu dnia odpowiada** na Twoje wiadomości i głosówki: `zadania`, `zrobione 2`, `pilne`, `poczta`, `kalendarz`, `jutro`, `dokumenty`, `zapamiętaj: …`, `cisza`, `status`, `pomoc` — i na zwykłe pytania o Twoje sprawy (z poczty, zadań, Bieżących spraw, faktów z nauki, dokumentów).
- **Powiadomienia** (dokument gotowy, wygasło logowanie do Dysku, brak modelu) przychodzą na WhatsApp, z ciszą nocną 22–7.
- Opcjonalnie: **wieczorne** i **tygodniowe** podsumowanie.

Słucha **tylko Ciebie** (Twój numer). Nie wysyła maili i nie usuwa niczego. Zmienia dane tylko dwiema świadomymi komendami: `zrobione N` (jak przycisk w panelu, z możliwością cofnięcia) i `zapamiętaj:` (notatka w Pamięci bota).

## Zanim zaczniesz: jakie konto dla Sebastiana?

**Zalecane: osobny numer**, np. tania karta SIM albo eSIM z aplikacją **WhatsApp Business** na zapasowym telefonie lub jako drugi numer w Twoim. Zapisz go w kontaktach jako „Sebastian”. Dlaczego:
- Sebastian jest wtedy zwykłym kontaktem, z którym rozmawiasz jak z człowiekiem,
- łączy się przez nieoficjalną bibliotekę (jak WhatsApp Web). Przy kilku wiadomościach dziennie ryzyko blokady jest niskie, ale gdyby się zdarzyła, dotknie numer Sebastiana, a nie Twój.

Można też użyć **własnego numeru**. Sebastian pisze wtedy w czacie „Ty” (wiadomości do siebie) i słucha tylko tego, co tam napiszesz.

Telefon z kontem Sebastiana musi co jakiś czas mieć Internet (WhatsApp odłącza połączone urządzenia po ok. 14 dniach offline).

## Instalacja

```bash
cd ~/SebastianSystem/sebastian-start
source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_3.py
```

Aktualizator robi kopię, podmienia pliki, sprawdza uruchomienie (w razie błędu przywraca 2.2), przeładowuje panel i naukę. Potem **pyta po kolei** (każdy krok możesz pominąć i zrobić później):

1. `brew install ffmpeg libmagic` — głosówki i biblioteka WhatsApp,
2. biblioteki Pythona z `requirements-whatsapp.txt` (połączenie, polski głos, rozumienie głosówek),
3. `wa-setup` — Twój numer, imię, godzina przeglądu; pobiera polski głos,
4. `wa-login` — połączenie z WhatsAppem: kod QR w Terminalu.

## Połączenie z WhatsAppem (`wa-login`)

Na telefonie z kontem **Sebastiana**: WhatsApp → Ustawienia → **Połączone urządzenia** → **Połącz urządzenie** → zeskanuj kod QR z Terminala. Gdy skanowanie jest niewygodne: `python sebastian.py wa-login --kod` i w telefonie „Połącz za pomocą numeru telefonu”.

Po połączeniu `wa-login` uruchomi usługę w tle, a Sebastian przyśle powitanie z listą komend.

## Sprawdzenie

```bash
python sebastian.py wa-test                  # wszystko po kolei + próbna głosówka (słychać ją z Maca)
python sebastian.py wa-brief --podglad       # dzisiejszy przegląd: tekst i głosówka, bez wysyłania
python sebastian.py wa-chat                  # rozmowa z Sebastianem w Terminalu
python sebastian.py check                    # sekcja „7. WhatsApp”
```

W panelu: nowa zakładka **WhatsApp** (stan, podgląd i odsłuch przeglądu, „Wyślij mi przegląd teraz”, historia rozmowy).

## Przydatne ustawienia

```bash
python sebastian.py wa-set WA_BRIEF_TIME 07:30          # godzina przeglądu
python sebastian.py wa-set WA_BRIEF_DAYS 1,2,3,4,5      # tylko dni robocze
python sebastian.py wa-set WA_EVENING tak               # wieczorne podsumowanie (20:30)
python sebastian.py wa-set WA_SCOPES private            # bez spraw firmowych na telefonie
python sebastian.py wa-voice pl_PL-gosia-medium          # głos kobiecy zamiast męskiego
python sebastian.py wa-start                            # przeładowanie po zmianach
```

Wszystkie ustawienia: `python sebastian.py wa-settings`; opis: DOKUMENTACJA.md, rozdział 12.3. Pełny opis modułu: rozdział 8b.

## Prywatność

Przegląd i odpowiedzi przechodzą przez WhatsApp (szyfrowane end-to-end) i zostają na telefonie. Jeśli sprawy klientów nie powinny trafiać na telefon, ustaw `WA_SCOPES private`. Przygotowanie przeglądu, głos i rozumienie głosówek dzieją się lokalnie na Macu. Klucze połączenia leżą w `data/whatsapp/sesja.sqlite3`: nigdy na GitHub, a przy podejrzeniu wycieku `wa-logout` i usunięcie urządzenia w telefonie.

## Gdyby coś poszło nie tak

Aktualizator sam przywraca kopię, gdy test po podmianie nie przejdzie. Wyłączenie samego WhatsAppa: `python sebastian.py wa-stop` (reszta Sebastiana działa bez zmian). Ręczny powrót do 2.2:

```bash
python sebastian.py wa-stop
python sebastian.py learn-stop
cp -R backups/aktualizacja-2.3-*/files/* .
rm whatsapp.py whatsapp_link.py whatsapp_web.py test_whatsapp.py templates/whatsapp.html requirements-whatsapp.txt
launchctl kickstart -k gui/$(id -u)/pl.sebastian.panel
python sebastian.py learn-start
```
