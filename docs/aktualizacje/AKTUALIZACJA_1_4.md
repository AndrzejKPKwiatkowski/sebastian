# Sebastian 1.4 — szybkie decyzje, zadania i pamięć dla Open WebUI

Ta aktualizacja jest dla działającej wersji 1.3 na Macu. Zachowuje wiadomości, ustawienia, wcześniejsze decyzje, załączniki, odpowiedzi i kalendarz. Nie wymaga nowych bibliotek. Aktualizator robi kopię bazy i zmienianych plików oraz zatrzymuje się, jeżeli wykryje inną wersję kodu.

## 1. Aktualizacja — wklejaj po jednym kroku

Pobierz `Sebastian_aktualizacja_1_4.py` do Pobranych na Macu. Otwórz Terminal w swoim folderze `sebastian-start`.

```bash
source .venv/bin/activate
```

Powinno pojawić się `(.venv)`. Jeśli panel uruchomiłeś ręcznie przez `serve`, zatrzymaj go Control + C. Zatrzymaj też zadania działające w tle:

```bash
python sebastian.py schedule remove
```

Uruchom aktualizację:

```bash
python "$HOME/Downloads/Sebastian_aktualizacja_1_4.py"
```

Dopiero po komunikacie OK:

```bash
python sebastian.py morning-setup
```

To ponownie włącza panel w tle i poranek o 06:30 od następnego dnia. Przy instalacji 11.10.2026 pierwszy poranek przypada 12.10.2026. Sprawdź wypisane konta i ostrzeżenia. Harmonogram zachowuje istniejące granice synchronizacji wiadomości. Nie uruchamiaj dodatkowo `serve`.

Otwórz http://127.0.0.1:8765 i odśwież Command + R. Nagłówek powinien pokazać SEBASTIAN 1.4. Możesz zamknąć Terminal. Mac musi pozostać włączony, zalogowany, z dostępem do Pęku kluczy i Internetu; do punktualnego startu także nieuśpiony, ze strefą Warszawa. Harmonogram nie włącza wyłączonego komputera. Po wybudzeniu podejmuje próbę z opóźnieniem.

Jeśli aktualizacja zatrzyma się z komunikatem STOP, nie uruchamiaj dalszych kroków na ślepo. Zachowaj komunikat. Przy wykryciu niezgodnego pliku kod pozostaje bez zmian; po nieudanej migracji przywracany jest poprzedni kod, a kopia bazy czeka w `backups`.

## 2. Co oznaczają przyciski

| Przycisk | Co robi | Co zostaje do zrobienia |
| --- | --- | --- |
| Pomiń — mało ważne | Zapisuje powód szybkiego pominięcia i usuwa mail z kolejki decyzji | Mail nadal jest w Wszystkie; bez zmian na serwerze |
| Tak, przypisz: kategoria | Zatwierdza propozycję tematu i podkategorii; zamyka decyzję o przypisaniu | Samo przypisanie nie tworzy zadania |
| Zmień kategorię | Rozwija wybór kategorii; możesz dodać własną i podkategorię | Zapis zachowuje istniejący status i zadanie |
| Zadanie wykonane | Zapisuje wykonanie, usuwa z kolejki decyzji i aktywnych zadań | Możesz przywrócić przyciskiem Do zadań w widoku Wszystkie |
| Do zadań | Odkłada do listy Zadania do wykonania, usuwa z kolejki decyzji | Wykonujesz zadanie i klikasz Zadanie wykonane |
| Zmień priorytet Eisenhowera | Pozwala wybrać jedną z czterech grup albo wrócić do propozycji AI | Samo poprawienie priorytetu nie zamyka decyzji o mailu |

Przycisk zatwierdzania kategorii jest widoczny, gdy AI podało kategorię i nie została jeszcze zatwierdzona. Przy braku propozycji użyj Zmień kategorię.

Każda szybka zmiana ma cofnięcie na górze listy. Cofnięcie nie nadpisze później zapisanej zmiany w tej wiadomości. Podwójne kliknięcie lub stara karta przeglądarki nie powinny nadpisać nowszej decyzji: lista poprosi o sprawdzenie aktualnego stanu. Zapis wraca do tej samej części prywatnej/firmowej i widoku; filtr wyszukiwania trzeba wpisać ponownie.

Zadania mają źródłowy mail, kategorię, priorytet i nazwę, którą można poprawić przez „Edytuj nazwę zadania”. Wcześniejsze otwarte, ocenione sprawy z wersji 1.3 stają się zadaniami. Nie ma jeszcze autonomicznego wysyłania przypomnień o zadaniach — to kolejny etap. Wersja 1.4 nie wysyła maili ani nie klika Pomiń za Ciebie.

## 3. Dwa różne rodzaje kategorii

Kategoria sprawy: InPartners → Klienci, Rodzina, Wyjazdy, Nieruchomość Rybnik itd.

Priorytet Eisenhowera (zachowana Twoja kolejność):

1. Pilne i ważne.
2. Pilne i mniej ważne.
3. Niepilne i ważne.
4. Niepilne i mniej ważne.

Ręczny priorytet ma pierwszeństwo. Propozycja AI musi być poparta cytatem z bieżącego maila; bez niej działa wcześniejsza ocena według rodzaju sprawy i terminu do 3 dni. Minione terminy wymagają sprawdzenia aktualności. Wyjątki dla ważnych nadawców Partners pozostają aktywne, ale świadomy ręczny wybór użytkownika ma pierwszeństwo.

Poprawki trafiają do przykładów używanych przy kolejnych analizach. Dawna pilna sprawa nie dowodzi, że nowa jest pilna; zamknięcie starego zadania nie oznacza wykonania nowego. Już zapisane analizy nie są automatycznie przeliczane po każdej poprawce.

## 4. Pamięć bota — co naprawdę jest zapisywane

Otwórz zakładkę Pamięć bota, wybierz Prywatne albo Firmowe. Znajdziesz tam:

- własne fakty i preferencje, które możesz dodać, poprawić lub wyłączyć;
- bieżące kategorie, priorytety, komentarze, pominięcia i statusy zadań z linkiem do źródła;
- fragmenty odpowiedzi wysłanych przez dashboard i przyjętych przez SMTP;
- oznaczone fragmenty maili i streszczenia AI jako kontekst, nie potwierdzone fakty o Tobie.

Dodałem edytowalną preferencję dotyczącą powiadomień cal.com, zgodnie z Twoją prośbą. Dotyczy zwykłych powiadomień o wydarzeniu już obecnym w kalendarzu. Odwołanie, zmiana terminu lub prośba o działanie powinny być oceniane osobno. Sebastian nie uznaje samego powiadomienia za dowód, że wydarzenie rzeczywiście jest w Twoim kalendarzu.

Przykładowe własne notatki:

- Preferencja: „Klient czekający na moją odpowiedź jest ważniejszy od newslettera”.
- Fakt podany przeze mnie: „Projekt Rybnik dotyczy ustalenia właścicieli mieszkania”.
- Preferencja: „Nie zamieniaj każdego informacyjnego maila w zadanie”.

Domyślnie uczenie dla wiadomości pozostaje włączone. Wyłączenie go w karcie maila wyklucza wiadomość z nowych przykładów i kolejnych eksportów pamięci. Wyłączenie notatki działa analogicznie. Nie usuwa historycznych rozmów ani plików ręcznie wgranych do Open WebUI. Po wyłączeniu odśwież kopię WebUI, aby stara migawka nie pozostawała dostępna dla narzędzia.

Analiza pojedynczego maila dostaje maksymalnie 4 podobne przykłady z 200 ostatnio opracowanych wiadomości tego samego konta i zakresu, oraz 12 najnowszych aktywnych notatek zakresu (do 450 znaków każda). Wyszukiwanie pamięci w Open WebUI obejmuje wszystkie aktualnie eksportowane źródła danego zakresu, także starsze. Pamięć jest narastająca w liczbie źródeł, lecz stan konkretnego maila jest aktualizowany zamiast mnożenia sprzecznych kopii każdej decyzji.

To RAG — pobranie pasujących źródeł do odpowiedzi. Model nie trenuje swoich wag po każdym kliknięciu i nie pamięta danych bez pobrania ich przez narzędzie lub bazę wiedzy.

## 5. Open WebUI — zalecane połączenie aktualizowane automatycznie

Ta ścieżka wykorzystuje narzędzie wyszukujące lokalną kopię wiedzy. Nie wymaga klucza API, nowej bazy wektorowej ani dodatkowego modelu embeddingów.

### A. Sprawdź kopiowanie do Dockera

W Terminalu, w aktywnym środowisku Sebastiana:

```bash
python sebastian.py bridge
```

Oczekiwany komunikat: odświeżono raport i pamięć prywatną/firmową. W dashboardzie stan w Pamięci bota powinien być „Odświeżono”. Jeśli nie masz jeszcze ustawionej nazwy kontenera, sprawdź ją:

```bash
docker ps --format "table {{.Names}}\t{{.Image}}"
```

Odszukaj kontener Open WebUI. Jeżeli nazywa się `open-webui`, użyj:

```bash
python sebastian.py webui "open-webui"
python sebastian.py bridge
```

Jeśli nazwa jest inna, wpisz dokładnie tę z kolumny NAMES. `webui` zapamiętuje również ścieżkę programu Docker. Nie usuwaj ani nie twórz od nowa kontenera.

### B. Dodaj narzędzie — jednorazowo

Skopiuj kod do schowka Maca:

```bash
pbcopy < openwebui_memory_tool.py
```

1. Otwórz swoje Open WebUI.
2. Workspace / Obszar roboczy → Tools / Narzędzia → utwórz nowe narzędzie.
3. W edytorze kodu zaznacz dotychczasową zawartość i wklej Command + V. Zapisz jako „Sebastian — pamięć prywatna”. To kod Tools, nie wiadomość na czacie ani Function.
4. W ustawieniach Valves / Zawory wpisz ALLOWED_EMAIL: dokładny adres e-mail konta Andrzeja w Open WebUI. Nie musi to być adres skrzynki murena ani Partners — chodzi o konto, z którego rozmawiasz z botem.
5. Ustaw ALLOWED_SCOPE na `private`. Pozostaw prywatną widoczność narzędzia, przypisaną tylko właścicielowi.
6. Dla firmy utwórz drugie narzędzie z tym samym kodem, nazwą „Sebastian — pamięć firmowa” i ALLOWED_SCOPE równym `work`. Nie przypinaj go do modelu współdzielonego z rodziną.
7. W nowej rozmowie z lokalnym modelem włącz właściwe narzędzie przy polu wiadomości. Jeśli dostępne, ustaw Function Calling → Native. Nazwy i układ menu mogą zależeć od wersji.
8. Aby narzędzie było dostępne stale w danym modelu: Workspace → Models → edycja Twojego modelu → Tools → zaznacz narzędzie → Save. Samo zapisanie kodu Tools nie włącza go w rozmowach.

Jeżeli nie widzisz Tools, użyj konta administratora lub nadaj właścicielowi odpowiednie uprawnienie. Kod narzędzi działa wewnątrz serwera Open WebUI; edycja takich narzędzi powinna pozostać w rękach administratora.

### C. Test wiedzy

Napisz w nowym czacie:

> Użyj narzędzia moje_preferencje. Jak mam traktować przypomnienia cal.com? Podaj identyfikator źródła i datę migawki pamięci.

Następnie popraw priorytet wybranego maila w dashboardzie, zapamiętaj jego numer, kliknij Pamięć bota → Odśwież kopię Open WebUI teraz. W czacie:

> Użyj szukaj_pamieci ze source_id mail:123 i podaj mój ręczny priorytet oraz stan zadania.

Zamień 123 na rzeczywisty numer. Jeżeli model nie wywoła narzędzia lub zgłosi brak źródeł, nie uznawaj odpowiedzi z pamięci modelu za udany test. Sprawdź aktywację narzędzia, ALLOWED_EMAIL, zakres i datę kopiowania. „Brak dostępu” oznacza odmowę odczytu, a nie uszkodzenie bazy.

### D. Odświeżanie

Decyzja aktualizuje lokalny eksport od razu. Worker harmonogramu z wersji 1.3 uruchamia się także co 15 minut; wersja 1.4 wykorzystuje te wywołania do kopiowania pamięci, nawet gdy poranne pobieranie już się zakończyło. Dłuższa analiza lub uśpienie komputera mogą opóźnić kopiowanie. Przyciskiem w Pamięci bota albo komendą `bridge` odświeżysz ją na żądanie.

Narzędzie wyszukuje leksykalnie metodą BM25. To działający wariant RAG, ale bez wektorów i pełnego rozumienia synonimów. Przy braku wyniku spróbuj konkretnych słów z maila albo source_id. Wynik zawiera do 8 źródeł, a osobne moje_preferencje pokazuje do 20 aktywnych notatek. Nie wszystkie źródła są wpychane do każdego pytania.

Kopie w kontenerze są plikami z prywatnymi danymi; administrator kontenera może je odczytać. Narzędzie kontroluje e-mail użytkownika i zakres przy każdym wywołaniu. Używaj lokalnego modelu, jeśli treść ma pozostać na Macu. Linki 127.0.0.1 otwierają dashboard na Macu; na telefonie wymagają osobnej konfiguracji dostępu zdalnego.

## 6. Alternatywa: prawdziwy indeks wektorowy Open WebUI

Open WebUI potrafi sam indeksować dokumenty w Knowledge i wyszukiwać ich fragmenty. Sebastian przygotowuje źródła; nie trzeba budować drugiej, konkurencyjnej bazy wektorowej od zera.

1. Dashboard → Pamięć bota → wybierz zakres → Wariant z wektorowym RAG → Pobierz bieżącą pamięć jako Markdown.
2. Open WebUI → Workspace → Knowledge → Create.
3. Nazwij bazę „Sebastian — prywatne” albo „Sebastian — firmowe”; pozostaw prywatny dostęp.
4. Wgraj pobrany plik `.md`. Poczekaj, aż zakończy się przetwarzanie.
5. W czacie wybierz bazę przez `#` albo przypnij ją do modelu w Workspace → Models → edycja modelu → Knowledge.
6. Zadaj pytanie o konkretną zapisaną preferencję i poproś o źródło. Dla lokalności danych ustaw lokalny silnik embeddingów i model odpowiedzi w Open WebUI.

To ręczna migawka, nie automatyczna synchronizacja bazy wektorowej. Po zmianach usuń poprzedni plik z tej konkretnej bazy i wgraj świeży; nie dopisuj w nieskończoność kopii ze sprzecznymi statusami. Nie resetuj innych baz wiedzy. Przycisk „Odśwież kopię Open WebUI” aktualizuje pliki dla narzędzia z punktu 5, a nie dokument w Knowledge.

Do codziennej pracy od teraz proponuję narzędzie z punktu 5. Wariant Knowledge daje wektorowe wyszukiwanie, ale w tej wersji wymaga ręcznego odświeżania. Nazwy menu zależą od wersji Open WebUI; nie ma potrzeby aktualizować całej instalacji tylko dla Sebastiana.

## 7. Weryfikacja i granice wersji

Sprawdzone na fikcyjnych wiadomościach i symulowanych połączeniach: przejścia kategoria → zadanie → wykonanie → cofnięcie, podwójne kliknięcia, stare karty, CSRF, oddzielenie zakresów, wyłączenie uczenia, poprawianie notatek, nowe priorytety AI, przekazywanie preferencji do kolejnego maila, wyszukiwanie pamięci, kopiowanie atomowe plików i raport błędu Dockera, migracja z 1.3 i zachowanie danych.

Nie wykonywałem połączenia z Twoim Maciem, prawdziwą skrzynką, Ollamą ani instancją Open WebUI. Udane testy kodu nie zastępują lokalnego testu z punktu 5C. Wiadomości i instrukcje ich nadawców pozostają danymi do analizy; nie upoważniają bota do działań. Czynności wysyłania w panelu zachowują wcześniejszy podgląd i ręczne potwierdzenie.

Źródła integracji, sprawdzone 11.10.2026:
- Open WebUI Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- Knowledge i tryby RAG: https://docs.openwebui.com/features/workspace/knowledge/
