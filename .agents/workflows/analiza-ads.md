---
name: analiza-ads
description: >
  Workflow dwutygodniowego audytu marketingowego. Pobiera dane z GA4,
  Google Ads i Search Console, analizuje je i generuje raport Markdown
  oceniający pracę agencji. Uruchamiany ręcznie co ~2 tygodnie.
---

# Audyt marketingowy — Workflow

Ten workflow orkiestruje cały proces audytu: od pobrania danych przez analizę po wygenerowanie raportu.

## Krok 1: Parametry

Zapytaj użytkownika o zakres dat do analizy. Domyślnie: ostatnie 14 dni (od dziś wstecz).

Ustal zmienne:
- `START_DATE` — data początkowa (YYYY-MM-DD)
- `END_DATE` — data końcowa (YYYY-MM-DD)
- `RUN_DATE` — dzisiejsza data (YYYY-MM-DD), używana jako identyfikator uruchomienia

Przykład:
- START_DATE = 2026-05-06
- END_DATE = 2026-05-20
- RUN_DATE = 2026-05-20

## Krok 2: Pobierz dane

Uruchom sekwencyjnie trzy skrypty Python. Każdy zapisze dane JSON do `data/{RUN_DATE}/`.

**Ważne**: Uruchom skrypty z katalogu głównego projektu (`/home/wales/projects/agents/illuminart-ads`).

```bash
# 1. Google Analytics 4
python scripts/fetch_ga4.py --start {START_DATE} --end {END_DATE} --run-date {RUN_DATE}

# 2. Google Ads (kampanie, słowa kluczowe, search terms, historia zmian)
python scripts/fetch_ads.py --start {START_DATE} --end {END_DATE} --run-date {RUN_DATE}

# 3. Google Search Console
python scripts/fetch_gsc.py --start {START_DATE} --end {END_DATE} --run-date {RUN_DATE}
```

Po każdym skrypcie sprawdź czy zakończył się sukcesem (exit code 0).
Jeśli któryś skrypt się nie powiedzie, poinformuj użytkownika i zapytaj czy kontynuować z dostępnymi danymi.

## Krok 3: Załaduj kontekst historyczny

Przeczytaj ostatnie 3 raporty z `reports/history/` (posortowane po dacie, od najnowszego).
Jeśli nie ma żadnych poprzednich raportów — to pierwszy audyt, zaznacz to w raporcie.

Zanotuj z poprzednich raportów:
- Kluczowe metryki (ROAS, koszt, konwersje) do porównania trendów
- Rekomendacje — sprawdź czy zostały wdrożone
- Problemy — sprawdź czy zostały rozwiązane

## Krok 4: Analiza i generowanie raportu

1. Przeczytaj SKILL.md z `skills/ads-analyst/SKILL.md` — zawiera szczegółowe instrukcje analizy.
2. Pobierz Bazę Wiedzy Illuminart pod adresem URL wskazanym w SKILL.md (użyj narzędzia `read_url_content`).
3. Przeczytaj WSZYSTKIE pliki JSON z `data/{RUN_DATE}/`.
4. Przeczytaj załadowane raporty historyczne.
5. Wygeneruj raport zgodnie z metodyką opisaną w SKILL.md, odnosząc się do celów biznesowych z Bazy Wiedzy.

Raport powinien zaczynać się od nagłówka:

```markdown
# Raport audytu marketingowego

📅 Okres: {START_DATE} — {END_DATE}
📊 Data raportu: {RUN_DATE}
```

## Krok 5: Zapisz raport

1. Zapisz raport jako `reports/current_report.md` (nadpisz poprzedni).
2. Skopiuj raport do `reports/history/{RUN_DATE}.md` (archiwum).

## Krok 6: Podsumowanie dla użytkownika

Wyświetl użytkownikowi krótkie podsumowanie:

```
✅ Raport wygenerowany pomyślnie!

📊 3 najważniejsze wnioski:
1. [wniosek 1]
2. [wniosek 2]
3. [wniosek 3]

📁 Raport: reports/current_report.md
📁 Kopia archiwalna: reports/history/{RUN_DATE}.md

💬 Mogę odpowiedzieć na dodatkowe pytania dotyczące raportu.
   Np. "Dlaczego ROAS spadł?", "Które frazy warto wykluczyć?", 
   "Co dokładnie zmieniła agencja?"
```
