# Sebastian 2.15.1 — Gwaranci: Kalendarz Apple

Wymaga wersji 2.15 (Centrum dowodzenia zostaje bez zmian).

```bash
cd ~/SebastianSystem/sebastian-start && source .venv/bin/activate
python ~/Downloads/Sebastian_aktualizacja_2_15_1.py
```

## Co nowego

W pierwszym kroku panelu gwaranta („Podłącz swój kalendarz”) są teraz trzy drogi: **cal.com**, **Kalendarz Google** i **Kalendarz Apple (iCloud)**.

| Apple | Jak |
| --- | --- |
| iPhone / iPad | Kalendarz → „Kalendarze” → ⓘ przy kalendarzu iCloud → włącz „Kalendarz publiczny” → „Udostępnij łącze…” → „Kopiuj” → wklej w Sebastianie. |
| Mac | Kalendarz → prawy przycisk na kalendarzu iCloud → „Udostępnij kalendarz…” → zaznacz „Kalendarz publiczny” → skopiuj adres webcal://… → „Gotowe”. |

- Link `webcal://…` Sebastian sam zamienia na `https://…`; odczytuje z niego wyłącznie zajęte godziny (bez tytułów i opisów), jak z tajnego adresu Google.
- Kalendarze można łączyć: np. firmowy w Google i prywatny w Apple — każdy link w osobnej linii.
- Gdy ktoś wklei link-zaproszenie iCloud (icloud.com/calendar/share/…), Sebastian podpowie, że trzeba włączyć „Kalendarz publiczny” i skopiować link webcal://.
- Kalendarz Google albo firmowy (Exchange/Outlook) podpięty w aplikacji Kalendarz na iPhonie podłącza się nadal drogą swojego dostawcy (Google — tajny adres iCal).
