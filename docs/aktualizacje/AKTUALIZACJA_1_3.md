# Sebastian 1.3 — szybkie decyzje, postęp i poranek

Wymaga działającej wersji 1.2. Nie wprowadza nowych bibliotek. Aktualizacja kodu i włączenie harmonogramu to dwa oddzielne kroki: sam plik aktualizacji nie uruchamia zadań na Twoim Macu.

## Instalacja i uruchomienie od jutra

1. Pobierz `Sebastian_aktualizacja_1_3.py` na Maca do Pobranych.
2. Zatrzymaj ręcznie działający panel przez Control + C. Jeśli działa już harmonogram, najpierw użyj `python sebastian.py schedule remove`, aby panel nie wstawał ponownie podczas aktualizacji.
3. W folderze `sebastian-start`, z aktywnym `(.venv)`, uruchom:

```bash
python "$HOME/Downloads/Sebastian_aktualizacja_1_3.py"
```

Po komunikacie OK uruchom:

```bash
python sebastian.py morning-setup
```

Polecenie sprawdzi Ollamę, model i dostęp do skrzynek. macOS może poprosić o dostęp Pythona do Pęku kluczy. Dla kont bez kursora odczyta listę UID i ustali granicę nowych maili na chwilę konfiguracji — wcześniejsze wiadomości zostają do stopniowego pobierania jako archiwum. Istniejące kursory zachowuje. Zmiana UIDVALIDITY wymaga ponownego pierwszego testu folderu; nie próbujemy jej naprawiać przez ciche pomijanie poczty.

Następnie zostaną włączone zadania launchd: panel w tle i poranek o 06:30 czasu Maca, począwszy od następnego dnia. Jeśli włączysz je 11 października 2026, pierwszym dniem będzie 12 października 2026. Ponowne przygotowanie już włączonego harmonogramu nie przesuwa daty startu. Zastępuje wcześniejsze godziny 07:00/20:30.

Sprawdź w Terminalu listę gotowych kont i ostrzeżenia. Konta lub foldery, które nie przeszły sprawdzenia, nie są objęte harmonogramem. Po poprawieniu hasła/konfiguracji uruchom `morning-setup` ponownie.

Panel już działa w tle: otwórz http://127.0.0.1:8765 i odśwież Command + R. Nie uruchamiaj dodatkowo `serve` na tym samym porcie.

### Test przed pierwszym porankiem

```bash
python sebastian.py morning-run --force
```

To rzeczywiste pobieranie i analiza nowych wiadomości, niezależnie od godziny. Nie wysyła maili. „Nowe: 0” może oznaczać, że od granicy synchronizacji nic nie przyszło. Wynik zobaczysz w „Podsumowanie i postęp”. Pomyślny test dzisiaj nie blokuje zaplanowanego poranka jutro.

### Warunki pracy o 06:30

Mac musi być włączony, zalogowany, nieuśpiony, z dostępnym Pękiem kluczy i Internetem. Strefa systemowa powinna być ustawiona na Warszawę. Instalacja porównuje aktualne przesunięcie czasu z Europe/Warsaw, ale nie zastępuje kontroli ustawień strefy. Ustawienia ekranu mogą pozwalać wygasić ekran bez usypiania komputera.

Harmonogram nie włącza wyłączonego Maca i nie omija logowania ani FileVault. Po wybudzeniu lub późniejszym logowaniu zadanie może ruszyć z opóźnieniem. Kontrola co 15 minut podejmuje do 4 prób dziennie po 06:30. Po pełnym sukcesie nie wykonuje drugiego zwykłego pobierania tego dnia. Podczas pracy używa caffeinate, aby ograniczyć usypianie z bezczynności. Nie wymaga uprawnień administratora i nie zmienia globalnych ustawień energii.

Worker próbuje uruchomić aplikację Ollama, jeśli lokalny serwer nie odpowiada. Jeżeli używasz instalacji bez aplikacji Ollama.app, uruchomienie usługi należy ustawić oddzielnie; niepowodzenie będzie widoczne. Docker jest potrzebny jedynie do odświeżenia skonfigurowanej kopii Open WebUI, nie do lokalnego panelu.

Limity jednej próby: 200 nowych wiadomości na skonfigurowany folder oraz do 200 analiz nowych maili łącznie. Osiągnięcie limitu lub częściowy błąd uruchomi następną próbę w ramach limitu 4 prób. Pozostałości po wykorzystaniu limitu zostają w kolejce na kolejny dzień lub ręczne `morning-run --force`. To celowo mała automatyzacja; nie skanuje całego archiwum co rano.

Zatrzymanie panelu i harmonogramu:

```bash
python sebastian.py schedule remove
```

Potem panel można uruchomić ręcznie: `python sebastian.py serve`.

## Szybkie Pomiń

Na liście przy nieocenionym mailu jest „Pomiń — mało ważne”. Jedno kliknięcie:

- zapisuje lokalny status Pomiń;
- zapisuje powód „Szybkie pominięcie: mało ważne według użytkownika, bez pełnej lektury”;
- zachowuje dotychczasowe ustawienie wykorzystywania wskazówek (dla nowych maili domyślnie włączone);
- usuwa pozycję z kolejki decyzji i pokazuje „Cofnij ostatnie szybkie pominięcie”.

Nie usuwa, nie przenosi i nie oznacza jako przeczytanej wiadomości na serwerze. Podwójne kliknięcie nie dopisuje kolejnej decyzji. Cofnięcie odtwarza poprzednie pola i nie nadpisuje nowszej ręcznej decyzji. Jeśli później chcesz podać dokładniejszy powód, otwórz mail przez „Wszystkie” i popraw decyzję.

Taki skrót jest słabszą wskazówką niż pełna ocena — program nie udaje, że przeczytałeś i zweryfikowałeś cały mail. Nie tworzy reguły pomijania wszystkich wiadomości nadawcy. AI nadal tylko sugeruje pominięcie.

## Kolejność według macierzy

1. Pilne i ważne.
2. Pilne i mniej ważne.
3. Niepilne i ważne.
4. Niepilne i mniej ważne.

Przy równym priorytecie nowsze wiadomości są wyżej. W „Wszystkie” nieocenione pozostają przed ocenionymi. Wyliczanie priorytetu odbywa się przed ograniczeniem widocznej listy do 100 pozycji, więc starszy ważny mail nie jest pomijany tylko z powodu wieku.

Domyślna pilność oznacza potwierdzoną w analizie datę od dziś do 3 dni włącznie. Minione terminy dostają ostrzeżenie o konieczności sprawdzenia aktualności, zamiast automatycznie zalewać górę kolejki starymi zaległościami. Ważność wynika z propozycji AI popartej cytatem, a dla wcześniejszych analiz z rodzaju działania. Nie jest to pewna ocena skutków ani obietnica, że zadanie potrwa mniej niż 2 minuty. Możesz wybrać priorytet ręcznie w karcie maila.

Ogłoszenia Partners od Dawida Kozioła i Tomasza Pustówki są wyjątkiem: nie trafiają automatycznie do „mało ważnych” tylko dlatego, że wyglądają jak ogłoszenie. Wbudowane dopasowanie sprawdza czytelną nazwę nadawcy lub adres zawierający te nazwiska i imiona. Nowe importy zachowują nazwę nadawcy; stary program zachowywał jedynie adres. Jeżeli adres jest nieczytelny (np. skrót imienia), dodaj dokładny adres w Podsumowaniu → „Ważni nadawcy — wyjątki”. Program nie zgaduje adresów ani nie traktuje nazwy nadawcy jako dowodu jego tożsamości.

Ręczny priorytet użytkownika ma pierwszeństwo. Ważnego nadawcę też możesz świadomie pominąć jednym kliknięciem, jeśli dana wiadomość tego wymaga.

## Podsumowanie i postęp

Zakładka pokazuje osobno dla spraw prywatnych i firmowych:

- liczbę pobranych i przeanalizowanych wiadomości;
- liczbę wiadomości z aktualną decyzją i procent opracowania pobranej części;
- otwarte sprawy, zrobione i pominięte;
- decyzje z ostatnich 7 dni, bez zawyżania wyniku powtórnym klikaniem;
- komentarze, powody, kategorie i fragmenty Twoich wysłanych odpowiedzi;
- przykłady dostępne jako wskazówki oraz analizy, do których rzeczywiście je przekazano;
- odpowiedzi przyjęte przez SMTP i szkice kalendarza;
- konfigurację poranka, daty uruchomień, wyniki częściowe i błędy.

To ślad realnej pracy w bazie. Nie ma fikcyjnego wskaźnika inteligencji ani zapewnienia, że każda wskazówka poprawiła trafność AI. Procent dotyczy pobranej części, nie wszystkich maili na serwerze. Cofnięcie decyzji może zmniejszyć licznik. Kopie tej samej wiadomości w różnych folderach pozostają osobnymi rekordami.

„Źródła wskazówek” to wiadomości z włączonym uczeniem, które mają decyzję albo zaakceptowaną przez Ciebie odpowiedź przyjętą przez SMTP. Dobór obejmuje maksymalnie 4 podobne przykłady z 200 ostatnio ocenionych lub takich, na które odpowiedziałeś. Liczy się data Twojej pracy, nie wiek maila — dzisiejsza ocena starego maila może pomóc w jutrzejszej analizie. Zachowana jest granica konta i zakresu prywatne/firmowe. Podglądy niewysłane i wysyłki o niepewnym wyniku nie są używane jako potwierdzone odpowiedzi.

Przykłady zawierają ograniczony fragment maila, decyzję, kategorię, komentarz, powód pominięcia, ręczny priorytet i do 700 znaków ostatniej wysłanej przez panel odpowiedzi. Odpowiedź przyjęta przez SMTP nie dowodzi doręczenia ani aktualności ustaleń. Wskazówki są pobierane na początku każdej nowej analizy; już zapisane streszczenia nie przeliczają się automatycznie po Twojej korekcie. Cofnięcie pominięcia lub wyłączenie uczenia zmienia przyszły dobór, nie usuwa historycznego śladu z wcześniejszej analizy.

## Nowe maile a archiwum

„Nowe — do decyzji” pokazuje nieocenione wiadomości pobrane poleceniem sync lub porannym workerem. Wcześniejsze rekordy i backfill są oznaczone jako archiwum. Oznaczenie „nowe” opisuje sposób pobrania, nie twierdzi, że mail wysłano dzisiaj. Nowe nieocenione pozostają w tej kolejce także następnego dnia.

Wszystkie nieocenione wiadomości, łącznie z archiwum, są nadal w „Do decyzji”. Archiwum możesz dokładać małymi porcjami, np.:

```bash
python sebastian.py backfill --account murena --limit 20
python sebastian.py analyze --limit 20
```

Limit pobierania dotyczy folderu. Zwykłe analyze wybiera najnowsze nieprzeanalizowane rekordy w bazie, więc jeśli czekają też nowe maile, może najpierw zająć się nimi. Nie używaj ponownie pilot do codziennej synchronizacji — pilot ustala granicę archiwum. Worker używa sync i analizuje wyłącznie rekordy „new”, także te, których wcześniejsza analiza nie powiodła się. Nie wysyła odpowiedzi, nie klika Pomiń i nie zamyka spraw za Ciebie.

## Weryfikacja i ograniczenia

Aktualizator robi kopię bazy oraz zmienianych plików i sprawdza zgodność z wersją 1.2. Zachowuje konfigurację, hasła, tokeny, istniejące decyzje i dotychczasowe funkcje. Kopia nie zastępuje regularnego backupu.

Testy wykonano na fikcyjnych mailach i symulowanych połączeniach: pomijanie i cofanie, nowe decyzje po cofnięciu, macierz i wyjątki, zakres prywatny/firmowy, wpływ archiwalnej decyzji na nową analizę, granica UID, błędy Ollamy, limit ponowień, definicje launchd i aktualizacja danych. To nie jest potwierdzenie uruchomienia harmonogramu na Twoim Macu. Dokładny start o 06:30 sprawdzisz dopiero po instalacji i spełnieniu warunków pracy komputera.

Podstawa użycia lokalnych LaunchAgents: dokumentacja Apple https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
