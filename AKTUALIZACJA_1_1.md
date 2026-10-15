# Sebastian 1.1 — decyzje, kategorie i wskazówki

## Instalacja

1. Pobierz `Sebastian_aktualizacja_1_1.py` na Maca do folderu Pobrane (Downloads).
2. Zatrzymaj ręcznie uruchomiony panel: Control + C.
3. W tym samym Terminalu, w folderze sebastian-start i z aktywnym .venv:

```bash
python "$HOME/Downloads/Sebastian_aktualizacja_1_1.py"
```

4. Po komunikacie OK uruchom `python sebastian.py serve` i odśwież http://127.0.0.1:8765.

Instalator sprawdza zgodność wersji i zatrzymuje się, jeśli wykryje inne zmiany w plikach. Obsługuje wersję startową oraz tę samą wersję z poprawką think=False. Przed zmianą robi kopię bazy SQLite i zmienianych plików w `backups/aktualizacja-1.1-DATA/`. Zachowuje konfigurację, hasła w Pęku kluczy, token panelu i poprzednie dane. Baza zyskuje nowe pola. Nie pobiera ani nie analizuje maili podczas instalacji. Nie aktualizuje programu wewnątrz Open WebUI — zmienia lokalny panel i analizator na Macu.

## Codzienna obsługa

- **Do decyzji**: domyślny widok, tylko wiadomości bez zapisanej decyzji. Licznik dotyczy wybranej części: prywatnej lub firmowej. Wyniki są ograniczone do 100 na ekranie; po ocenieniu pojawiają się kolejne.
- **Otwarte zadania**: wiadomości, które już oceniłeś i pozostawiłeś jako Otwarte.
- **Wszystkie + zakończone**: nieocenione na górze, ocenione niżej. Wyszukiwanie obejmuje temat, treść, kategorię, podkategorię i komentarz.
- Zapis decyzji wraca do kolejki. Przywróć do decyzji cofa ocenę do kolejki, zachowując wpisane dane. Zanim zapiszesz nową decyzję, ten przykład nie jest używany w nowych analizach.
- Zero w kolejce oznacza brak nieocenionych wiadomości w pobranej próbce danej części. Nie oznacza pustego konta IMAP ani wykonania wszystkich otwartych zadań.
- Status w panelu nie jest statusem przeczytania na serwerze. Zapis decyzji nie wysyła odpowiedzi mailowej.

## Status i pola

**Pomiń**: widoczny jest powód pominięcia (obowiązkowy). Formularz nie wymaga kategorii ani komentarza. Wpisz warunek, który wyjaśnia decyzję, np. „Reklama szkolenia, które już ukończyłem”, zamiast „Nie”.

**Otwarte / Zrobione**: kategoria, podkategoria i Komentarz. Sekcja „Dodaj kategorię lub podkategorię” pozwala zapisać własne nazwy razem z decyzją. Podkategoria wymaga kategorii głównej. Katalogi są oddzielne dla części prywatnej i firmowej; na start oba mają ten sam zestaw nazw.

Domyślne kategorie: InPartners → Klienci, Zespół, Prawo, Marketing, Asystenci, Partnerzy; Nieruchomość Rybnik, Rodzina, Agnieszka, Wyjazdy, Dom, Finanse osobiste, Zdrowie, Rozwój i nauka, Inne.

„Rodzaj działania” to osobne pole, schowane w rozwijanej sekcji: odpowiedź, termin, informacja, newsletter, podejrzane, do sprawdzenia. Kategoria sprawy mówi, czego mail dotyczy; rodzaj działania mówi, co trzeba zrobić.

Dawne pole „Projekt / cel z mojego planu” służyło do opisania powiązania z większym przedsięwzięciem. Nie było komentarzem. Nowe pole Komentarz jest osobne. Stare wartości nie są kasowane ani automatycznie uznawane za komentarze; jeśli były wpisane, można je odczytać w karcie maila. „Mój większy plan” na stronie głównej pozostaje osobną listą celów.

## Jak Sebastian korzysta z decyzji

„Wykorzystanie decyzji w przyszłych analizach” jest domyślnie włączone. Zapisuje status, kategorię, podkategorię, rodzaj działania, komentarz i powód pominięcia. Można odznaczyć opcję i ponownie zapisać decyzję — wycofuje to przykład z przyszłego dobierania wskazówek. Historia decyzji pozostaje w lokalnej bazie.

Podczas nowej analizy program szuka przykładów wśród 200 ostatnio ocenionych wiadomości z tego samego konta i tej samej części prywatnej/firmowej. Dobiera maksymalnie 4 przykłady na podstawie tego samego nadawcy albo wspólnych słów w temacie i treści. Model otrzymuje ograniczone fragmenty oraz najnowsze decyzje. Wskazówki w bardzo długich komentarzach są skracane do 500 znaków w kontekście AI (w bazie do 1500). To prosta heurystyka dopasowania i pamięć przykładów, a nie trening wag modelu ani gwarancja poprawnej oceny. Bez podobnych przykładów model analizuje wiadomość bez nich.

Model może zaproponować kategorię i pominięcie z uzasadnieniem. Nie może automatycznie oznaczyć nowego maila jako pominiętego lub wykonanego. W karcie są linki do przykładów użytych podczas analizy. Obecność przykładu nie dowodzi, że przesądził on o wyniku. Cytaty z maili są traktowane jako niezaufana treść.

Wskazówki wpływają na kolejne analizy. Zapis komentarza nie przelicza wcześniejszych streszczeń. Zwykłe `analyze --retry` ponawia tylko nieudane/brakujące analizy, a nie poprawnie zakończone. Dotychczasowe ręczne reguły nadawców zachowują działanie i mogą nadal narzucać rodzaj działania; usuniesz je na stronie głównej.

Poprawka wyłączająca myślenie dla wywołań analizy (think=False) jest w tej aktualizacji. Ustawienia czatów Open WebUI pozostają niezależne. Raport lokalny zawiera nowe pola; po konfiguracji połączenia z WebUI standardowa komenda `python sebastian.py bridge` odświeża jego kopię. Samo zapisanie decyzji odświeża raport na Macu, a nie kopię w kontenerze.

## Gdy instalator się zatrzyma

- „Panel nadal działa”: zatrzymaj go Control + C. Jeśli masz już harmonogram, panel może uruchamiać się ponownie — nie próbuj go wielokrotnie zabijać, skonsultuj komunikat.
- „Inne zadanie trwa”: poczekaj na zakończenie pobierania/analizy.
- „Inna wersja pliku”: nie nadpisuj ręcznie plików; podeślij komunikat.
- W razie błędu zapisu instalator przywraca wcześniejsze pliki kodu. Migracja bazy jest tylko rozszerzeniem. Pełna kopia sprzed instalacji pozostaje w podanej lokalizacji.

## Weryfikacja

Zmiany sprawdzono na fikcyjnych wiadomościach: migracja wcześniejszych decyzji, wymagany powód pominięcia, kategorie, komentarze, rezygnacja z używania przykładów, izolacja kont, przekazywanie przykładów do AI, brak automatycznego pomijania oraz kolejka do zera. Analizę Ollamy w testach symulowano; aktualizacja wymaga końcowego sprawdzenia na Twoim Macu. Test nie korzysta z prawdziwych skrzynek ani haseł.
