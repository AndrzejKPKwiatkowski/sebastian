# Sebastian 1.2 — załączniki, odpowiedzi, kalendarz

Ta aktualizacja rozszerza działającą wersję 1.1. Zachowuje kolejkę decyzji, kategorie, komentarze, pamięć przykładów i poprawkę think=False. Pierwszy raz dodaje możliwość rzeczywistego wysłania maila, wyłącznie po Twoim kliknięciu „Wyślij odpowiedź” pod podglądem. Żadne zadanie w tle nie wysyła wiadomości.

## Instalacja krok po kroku

1. Pobierz `Sebastian_aktualizacja_1_2.py` na Maca do Pobranych (`Downloads`).
2. W Terminalu z panelem naciśnij Control + C. Pozostań w folderze `sebastian-start`, z aktywnym `(.venv)`.
3. Zainstaluj dwie biblioteki do kalendarzy (to wymaga Internetu):

```bash
python -m pip install "icalendar==7.3.0" "recurring-ical-events==3.8.2"
```

Jeżeli instalacja się nie powiedzie, zatrzymaj się i podeślij komunikat.

4. Uruchom aktualizator:

```bash
python "$HOME/Downloads/Sebastian_aktualizacja_1_2.py"
```

5. Po komunikacie „OK — zainstalowano aktualizację 1.2”:

```bash
python sebastian.py serve
```

6. Otwórz http://127.0.0.1:8765 i odśwież stronę Command + R.

Aktualizator wymaga wersji 1.1. Sprawdza pliki przed zmianą i odmawia nadpisania nieznanych modyfikacji. Robi kopię bazy oraz zmienianych plików w `backups/aktualizacja-1.2-DATA/`. Nie zmienia haseł, tokenu panelu, adresów kont ani istniejących maili. Baza zyskuje tabele tożsamości, szkiców odpowiedzi i kalendarzy. Instalacja nie łączy się z pocztą i niczego nie wysyła. Jeśli panel działa z harmonogramu i po zatrzymaniu wstaje ponownie, skonsultuj komunikat zamiast wielokrotnie kończyć proces.

## Załączniki

Otwórz kartę maila → „Pobierz załączniki” → „Pobierz plik” przy właściwej nazwie.

Lista i pobranie korzystają z oryginału na serwerze IMAP. Za każdym razem sprawdzany jest folder, UIDVALIDITY i Message-ID. Używane są tryb tylko do odczytu i BODY.PEEK[], więc pobieranie nie oznacza maila jako przeczytanego. Jeśli mail został przeniesiony lub usunięty na serwerze, trzeba pracować na aktualnie pobranej wiadomości. Panel wymaga połączenia z Internetem i dostępu do Pęku kluczy.

Limit dotyczy całej wiadomości MIME: 25 MiB. Większy mail otwórz w webmailu. Pobierane są prawdziwe załączniki MIME, również pliki dołączonych wiadomości EML; linki do chmury nie są zamieniane na załączniki. Pliki trafiają do folderu pobrań przeglądarki. Nie otwieramy ich automatycznie, nie renderujemy niezaufanego HTML i nie przekazujemy ich do AI.

## Nazwa i podpis dla każdej skrzynki

W górnej nawigacji wybierz „Nazwy i stopki”. Dla każdego konta osobno wpisz:

- wyświetlaną nazwę nadawcy;
- stopkę tekstową (wiele wierszy);
- krój pisma i kolor tekstu.

Kliknij „Zapisz ustawienia tej skrzynki”. Adres From pozostaje adresem danego konta. Stopki z Gmaila, Mureny i Partners nie są automatycznie kopiowane z webmaila. Ta wersja obsługuje tekstowe podpisy z formatowaniem kroju i koloru; nie importuje logo, dowolnego HTML ani skomplikowanych firmowych szablonów. Wiadomość wychodzi w wersji tekstowej oraz HTML. Poszczególne programy pocztowe mogą wyświetlać krój nieco inaczej.

Zmiana stopki wpływa na nowe podglądy; już przygotowany podgląd jest niezmienny. Jeśli zmienisz podpis, wróć do edycji odpowiedzi i utwórz nowy podgląd.

## Odpowiadanie

Karta wiadomości → „Odpowiedz na maila”.

1. Sprawdź konto wysyłające i odbiorcę. Domyślnie jest to nagłówek Reply-To, a jeśli go brak — From. Nie jest to „Odpowiedz wszystkim”. Odbiorców możesz poprawić, rozdzielając adresy przecinkami.
2. Wpisz odpowiedź. Nie dopisuj ponownie stopki, jeśli skonfigurowałeś ją w ustawieniach.
3. Kliknij „Przejdź do podglądu”. Nic jeszcze nie zostało wysłane.
4. Sprawdź kompletny podgląd, nazwę i adres nadawcy, odbiorców, temat oraz stopkę. Możesz wrócić do edycji lub anulować podgląd.
5. Zaznacz potwierdzenie i kliknij „Wyślij odpowiedź”.

Program używa SMTP STARTTLS i hasła zapisanego dla tego konta w Pęku kluczy. Serwery: Gmail `smtp.gmail.com:587`, Murena `mail.ecloud.global:587`, Partners `webmail.inpartners.pl:587`. Gmail może wymagać hasła aplikacji; działające IMAP nie gwarantuje, że administrator zezwolił na SMTP. Nie trzeba wpisywać sekretów w przeglądarce.

Nagłówki In-Reply-To i References zachowują powiązanie wątku. Cytowany jest zapisany tekst oryginału; jeśli wcześniej został skrócony, cytat zawiera oznaczenie skrócenia. Oryginalne załączniki nie są odsyłane. Ta wersja nie dodaje nowych załączników, CC, BCC ani odpowiedzi wszystkim.

### Status wysyłki

- „Szkic”: nic nie wysłano.
- „Serwer przyjął wiadomość”: SMTP potwierdził przyjęcie; to nie potwierdzenie doręczenia ani przeczytania.
- „Nie wysłano”: błąd przed wysyłką lub wyraźne odrzucenie przez serwer.
- „Wynik nieznany” albo utrzymujące się „Wysyłanie”: połączenie mogło przerwać się po przyjęciu maila. Sprawdź webmail, zanim utworzysz kolejną odpowiedź. Panel nie ponawia jej automatycznie.
- „Wysyłka częściowa”: część odbiorców mogła dostać wiadomość, a inni zostali odrzuceni. Nie wysyłaj ponownie do wszystkich.

Podwójne kliknięcie tego samego podglądu nie wysyła drugiej kopii. Można pobrać lokalny plik EML i wrócić do historii odpowiedzi z poziomu „Odpowiedz”. Wysłanie nie zamyka automatycznie zadania — decyzję zapisz w karcie maila.

### Folder Wysłane

Niektóre serwery zapisują wiadomości wysłane przez SMTP automatycznie. Sprawdź to najpierw na wiadomości testowej do siebie. Niezależnie od serwera Sebastian zachowuje lokalną kopię EML.

Jeśli serwer nie zapisuje kopii, skonfiguruj folder wysłanych zgodnie z podręcznikiem (`folders`, potem `sent`) i w „Nazwy i stopki” włącz „Po wysłaniu dopisuj kopię…”. To świadomie włączany zapis IMAP, wyłącznie kopii wysłanej wiadomości. Włączenie go przy automatycznym zapisie serwera może tworzyć duplikaty. Nieudana kopia do Wysłanych nie oznacza nieudanej wysyłki SMTP.

## Propozycje kalendarza

Nowe analizy maili proszą model także o datę, godziny, tytuł i miejsce. Gdy AI wskaże termin, w karcie pojawi się „Sugerowany termin — sprawdź i utwórz ICS”. To propozycja, nie potwierdzony termin. Przytoczony fragment musi występować w zapisanej treści, ale sam ten test nie gwarantuje poprawnego rozumienia daty.

Dla wcześniej przeanalizowanego maila użyj „Utwórz wydarzenie / wyszukaj termin”, następnie „Wyszukaj termin w tym mailu przez AI”. Możesz też od razu wpisać dane ręcznie. Zapisany szkic nie jest nadpisywany następną sugestią AI.

W formularzu poprawisz: tytuł, datę, początek i koniec, wydarzenie całodniowe, busy/available, miejsce, opis, kontakt i dojazd. Opis na start zawiera podsumowanie, nadawcę, konto, temat, datę źródła, cytat oraz lokalny link do karty. Link 127.0.0.1 otwiera właściwy panel tylko na komputerze, na którym on działa. Dodatkowy Message-ID pomaga rozpoznać źródło poza tym komputerem.

Kliknij „Zapisz zmiany i sprawdź konflikty”, a potem „Pobierz zapisany plik ICS”. Zapis jest trwały w lokalnej bazie. Możesz wrócić i poprawić formularz. Nowy eksport zachowuje UID wydarzenia i zwiększa SEQUENCE, ale aplikacje kalendarza różnie obsługują ponowny import — sprawdź, czy stary wpis został zaktualizowany, czy powstał duplikat.

Pobranie pliku nie dodaje nic do kalendarza źródłowego. Otwórz ICS w swojej aplikacji i wybierz kalendarz docelowy. Nie tworzymy zaproszeń i nie wysyłamy powiadomień do nadawcy. Kontakt w ICS ma charakter informacyjny.

Na razie jeden mail ma jeden główny szkic wydarzenia. Dodatkowe wydarzenia dojazdu i powrotu mogą być częścią eksportu. Model może przeoczyć jeden z kilku terminów w długim mailu; załączników nadal nie analizuje. Zapisywane poprawki kalendarza nie trenują modelu ani nie stanowią nowego mechanizmu uczenia — pamięć decyzji o mailach z wersji 1.1 działa tak jak wcześniej.

## Busy, available i konflikty

Wczytaj eksport swojego kalendarza: „Kalendarze” → nazwa → plik ICS → „Wczytaj kalendarz”. Wczytaj osobno wszystkie istotne kalendarze. Import obejmuje wydarzenia z pliku, a nie synchronizację na żywo. Po zmianach ponownie wyeksportuj plik i zastąp kopię pod tą samą nazwą. Przy wynikach widoczna jest data importu.

Program porównuje przedziały czasu, uwzględnia daty całodniowe, strefy, cykle RRULE i wyjątki. Wydarzenia TRANSPARENT („available”, „dostępny”) są pokazywane jako nakładanie bez blokady; OPAQUE lub brak TRANSP oznacza zajętość. Anulowane są pomijane. TENTATIVE nadal może blokować czas. Daty bez strefy interpretowane są jako Europe/Warsaw. Formularz odrzuca niejednoznaczne lub nieistniejące godziny w nocy zmiany czasu zamiast zgadywać.

Jeśli nie ma pliku kalendarza lub wystąpił błąd odczytu, komunikat mówi, że nie można wykluczyć konfliktów. Nie wyświetlamy zapewnienia, że jesteś wolny. Obsługiwane są VEVENT, nie same raporty VFREEBUSY. Limit importu to 5 MiB i 20 000 składników; cykle sekundowe i minutowe są odrzucane. Proponowane wydarzenie może trwać do 31 dni.

Eksportowane wydarzenia Sebastiana są uwzględniane także jako lokalne rezerwacje, nawet jeśli jeszcze nie otworzyłeś pliku w kalendarzu. Możesz wyłączyć tę rezerwację w formularzu. Zmiana lub usunięcie rezerwacji w panelu nie aktualizuje wpisu w aplikacji kalendarza — tam trzeba dokonać zmiany osobno i odświeżyć kopię ICS.

Przy konflikcie pokazywany jest organizator, ewentualnie uczestnicy lub CONTACT z wydarzenia. To rzeczywiste pola z importu, a nie zgadywane kontakty. Drugą możliwością jest uzgodnienie terminu z nadawcą nowego maila. Sebastian sam do nikogo nie pisze i nie przesuwa wydarzeń.

## Dojazd

Panel tworzy link do trasy samochodem i transportem publicznym w Google Maps. Kliknięcie przekazuje mapom wpisane miejsca. Link transportu publicznego nie gwarantuje połączenia wyłącznie kolejowego; datę i godzinę sprawdź w mapach lub rozkładzie przewoźnika.

W tej wersji nie ma połączenia z API map, korków ani rozkładów. Wpisujesz sprawdzony czas obu wariantów. Sebastian wskazuje krótszy z nich na podstawie Twoich wartości, a nie własnej estymacji. Uwzględnij dojścia, parking, przesiadki, koszt i wygodę.

Wpisz liczbę minut rezerwowanych przed i po wydarzeniu. Na tej podstawie otrzymasz godzinę wyjścia, a analiza konfliktów obejmie także ten czas. Eksport ICS utworzy osobne bloki dojazdu i powrotu. Dla całodniowych nie dodajemy takich bloków. Wpisane notatki o podróży zostają w szkicu i opisie ICS.

Pełne automatyczne czasy dojazdu i sprawdzanie kalendarza na żywo wymagają podłączenia wybranego kalendarza oraz źródła tras/rozkładów. Ta aktualizacja nie udaje tych połączeń.

## Pierwsza kontrola po instalacji

1. Otwórz znany mail z małym załącznikiem i pobierz go. Porównaj nazwę i zawartość z webmailem.
2. Skonfiguruj jedną stopkę. Przygotuj odpowiedź, zmień odbiorcę na własny adres, sprawdź podgląd i wyślij test do siebie. Sprawdź odbiór, stopkę oraz folder Wysłane.
3. Na testowym wydarzeniu sprawdź datę i godzinę po imporcie ICS do kalendarza.
4. Wczytaj eksport kalendarza zawierający znane wydarzenie „zajęty” i sprawdź propozycję na tę samą godzinę.

Testy programistyczne korzystały z fikcyjnej poczty, symulowanego SMTP/IMAP i syntetycznych kalendarzy. Nie wysłano prawdziwych maili ani nie sprawdzono dostępu SMTP Twoich kont. Testy obejmują idempotencję wysyłki, błędy logowania i niepewny wynik, CSRF, threading, pobieranie tylko do odczytu, eksport ICS, czas letni, cykle, wyjątki, available, cancelled oraz zachowanie danych przy aktualizacji. Nie jest to potwierdzenie zgodności ze wszystkimi serwerami i programami kalendarza.

## Źródła techniczne użyte podczas przygotowania

- Ustawienia Partners: oficjalna instrukcja konfiguracji poczty przekazana przez użytkownika.
- Murena: https://doc.e.foundation/workspace/email/
- Gmail SMTP: https://support.google.com/mail/answer/7104828?hl=pl
- Standard iCalendar: https://www.rfc-editor.org/info/rfc5545/
- Biblioteka iCalendar: https://icalendar.readthedocs.io/en/stable/
- Obsługa cykli: https://recurring-ical-events.readthedocs.io/en/stable/
- Linki do map: https://developers.google.com/maps/documentation/urls/get-started
