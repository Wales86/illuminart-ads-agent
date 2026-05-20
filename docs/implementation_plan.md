# Agent Audytu Marketingowego — Plan Implementacji

Agent automatycznie pobiera dane z GA4, Google Ads i Search Console, a następnie generuje dwutygodniowy raport audytowy w Markdown, oceniający pracę agencji marketingowej.

## User Review Required

> [!WARNING]
> **Google Ads API wymaga Developer Token** — aby korzystać z Google Ads API, musisz:
> 1. Mieć konto Google Ads (masz ✅)
> 2. Uzyskać **Developer Token** w panelu Google Ads → Narzędzia → API Center
> 3. Token startuje w trybie "Test" (dostęp do jednego konta) — to wystarczy na początek
> 4. Do pełnego dostępu trzeba przejść weryfikację Google (kilka dni)
>
> **To jest główny blocker** — bez tego skrypt `fetch_ads.py` nie będzie działał.

> [!IMPORTANT]
> **OAuth2 vs Service Account** — Google Ads API wymaga OAuth2 (nie obsługuje service account bezpośrednio).
> GA4 i GSC mogą korzystać z service account. Mamy dwie opcje:
> - **Opcja 1 (Prostsza):** OAuth2 Desktop flow dla wszystkich trzech API — jeden zestaw credentials
> - **Opcja 2:** Service account dla GA4/GSC + OAuth2 dla Ads — dwa zestawy credentials
>
> **Rekomenduję Opcję 1** — prostsze zarządzanie, jeden plik `credentials.json` + `token.json`.

## Proponowane zmiany

### Struktura projektu

```
illuminart-ads/
├── .github/
│   └── workflows/             # [OPCJONALNIE] GitHub Pages deploy
├── scripts/
│   ├── fetch_ga4.py           # Pobieranie danych z GA4 Data API
│   ├── fetch_ads.py           # Pobieranie danych z Google Ads API + change history
│   ├── fetch_gsc.py           # Pobieranie danych z Search Console API
│   ├── utils.py               # Wspólne funkcje (auth, daty, I/O)
│   └── requirements.txt       # Zależności Python
├── data/                      # Dane źródłowe (gitignored)
│   ├── 2026-05-20/            # Katalog per uruchomienie
│   │   ├── ga4_data.json
│   │   ├── ads_campaigns.json
│   │   ├── ads_keywords.json
│   │   ├── ads_changes.json
│   │   └── gsc_data.json
│   └── 2026-05-06/
│       └── ...
├── reports/
│   ├── current_report.md      # Aktualny raport (GitHub Pages index)
│   └── history/               # Archiwum raportów
│       ├── 2026-05-06.md
│       └── 2026-04-22.md
├── skills/
│   └── ads-analyst/
│       └── SKILL.md           # Prompt eksperta — instrukcje analizy
├── workflows/
│   └── analiza-ads.md         # Workflow orkiestracji
├── config/
│   ├── credentials.json       # OAuth credentials (gitignored!)
│   ├── token.json             # OAuth token (gitignored!)
│   └── settings.yaml          # Property IDs, customer IDs, site URLs
├── .gitignore
└── README.md
```

---

### Faza 0: Konfiguracja GCP i credentials

#### [NEW] [README.md](file:///home/wales/projects/agents/illuminart-ads/README.md)

Instrukcja krok-po-kroku:
1. Stwórz projekt w Google Cloud Console
2. Włącz API: Google Analytics Data API, Google Ads API, Search Console API
3. Stwórz OAuth2 Desktop App credentials → pobierz `credentials.json`
4. Uzyskaj Developer Token w Google Ads → zapisz w `settings.yaml`
5. Uruchom skrypt autentykacji → wygeneruje `token.json`

#### [NEW] [settings.yaml](file:///home/wales/projects/agents/illuminart-ads/config/settings.yaml)

```yaml
ga4:
  property_id: "XXXXXXXXX"           # GA4 Property ID

google_ads:
  customer_id: "XXX-XXX-XXXX"        # Google Ads Customer ID
  developer_token: "XXXXXXXX"        # Developer Token z API Center
  login_customer_id: ""               # Puste jeśli nie MCC

gsc:
  site_url: "https://example.com"     # URL strony w Search Console

report:
  default_period_days: 14             # Domyślny zakres analizy
  history_reports_to_load: 3          # Ile poprzednich raportów ładować
  language: "pl"                      # Język raportu
```

#### [NEW] [.gitignore](file:///home/wales/projects/agents/illuminart-ads/.gitignore)

Ignorowane: `config/credentials.json`, `config/token.json`, `data/`, `__pycache__/`, `.venv/`

---

### Faza 1: Skrypty Python — pobieranie danych

#### [NEW] [requirements.txt](file:///home/wales/projects/agents/illuminart-ads/scripts/requirements.txt)

```
google-analytics-data>=0.18.0
google-ads>=25.0.0
google-api-python-client>=2.100.0
google-auth-oauthlib>=1.1.0
pyyaml>=6.0
```

#### [NEW] [utils.py](file:///home/wales/projects/agents/illuminart-ads/scripts/utils.py)

Wspólne funkcje:
- `load_settings()` → parsuje `settings.yaml`
- `get_oauth_credentials()` → ładuje/odświeża OAuth token
- `ensure_data_dir(run_date)` → tworzy `data/{run_date}/`
- `save_json(data, filename, run_date)` → zapisuje do `data/{run_date}/{filename}`
- `parse_date_range(args)` → parsuje argumenty `--start` / `--end`

#### [NEW] [fetch_ga4.py](file:///home/wales/projects/agents/illuminart-ads/scripts/fetch_ga4.py)

**Argumenty:** `--start YYYY-MM-DD --end YYYY-MM-DD --run-date YYYY-MM-DD`

**Pobierane dane:**

1. **Przegląd ruchu** (`ga4_traffic.json`):
   - Metryki: sessions, totalUsers, newUsers, engagementRate, averageSessionDuration, bounceRate, screenPageViews
   - Wymiary: date
   - Zakres: podany okres

2. **Ruch wg źródła** (`ga4_sources.json`):
   - Metryki: sessions, totalUsers, conversions, totalRevenue
   - Wymiary: sessionSource, sessionMedium, sessionCampaignName

3. **Konwersje** (`ga4_conversions.json`):
   - Metryki: conversions, totalRevenue, purchaseRevenue
   - Wymiary: date, sessionSource, sessionMedium
   - Filtr: eventName = purchase (lub inne skonfigurowane konwersje)

4. **Top strony** (`ga4_pages.json`):
   - Metryki: screenPageViews, averageSessionDuration, bounceRate
   - Wymiary: pagePath
   - Limit: top 30

#### [NEW] [fetch_ads.py](file:///home/wales/projects/agents/illuminart-ads/scripts/fetch_ads.py)

**Argumenty:** `--start YYYY-MM-DD --end YYYY-MM-DD --run-date YYYY-MM-DD`

**Pobierane dane:**

1. **Kampanie** (`ads_campaigns.json`):
   - Metryki: cost, conversions, conversion_value, impressions, clicks, ctr, avg_cpc
   - Wymiary: campaign name, campaign status, campaign type
   - Wyliczane: ROAS (conversion_value / cost)

2. **Słowa kluczowe** (`ads_keywords.json`):
   - Metryki: cost, conversions, conversion_value, impressions, clicks, ctr, avg_cpc, quality_score
   - Wymiary: keyword, match_type, ad_group, campaign
   - **Flagowanie "śmieci"**: słowa z kosztem > 0 i konwersjami = 0

3. **Wyszukiwane frazy (Search Terms)** (`ads_search_terms.json`):
   - Metryki: cost, conversions, impressions, clicks
   - Wymiary: search_term, keyword, campaign
   - Kluczowe do identyfikacji "przepalonego" budżetu

4. **Historia zmian** (`ads_changes.json`):
   - Źródło: ChangeEvent resource
   - Dane: co zmieniono, kiedy, kto (email), stare/nowe wartości
   - Typy zmian: budżet, stawki, słowa kluczowe, reklamy, grupy reklam

#### [NEW] [fetch_gsc.py](file:///home/wales/projects/agents/illuminart-ads/scripts/fetch_gsc.py)

**Argumenty:** `--start YYYY-MM-DD --end YYYY-MM-DD --run-date YYYY-MM-DD`

**Pobierane dane:**

1. **Zapytania** (`gsc_queries.json`):
   - Metryki: clicks, impressions, ctr, position
   - Wymiary: query, date
   - Limit: top 100 zapytań

2. **Strony** (`gsc_pages.json`):
   - Metryki: clicks, impressions, ctr, position
   - Wymiary: page
   - Limit: top 50 stron

3. **Problemy indeksacji** (`gsc_index_status.json`):
   - URL Inspection API — status indeksacji kluczowych stron
   - (Opcjonalnie, API jest rate-limited)

---

### Faza 2: Antigravity Skill — Ekspert Ads

#### [NEW] [SKILL.md](file:///home/wales/projects/agents/illuminart-ads/skills/ads-analyst/SKILL.md)

```yaml
---
name: ads-analyst
description: >
  Ekspert Google Ads i analityki internetowej. Analizuje dane z GA4, 
  Google Ads i Search Console, tworząc raport audytowy dla małego sklepu 
  internetowego. Skupia się na ROAS, wasted spend, skuteczności kampanii 
  i ocenie pracy agencji marketingowej.
---
```

**Zawartość SKILL.md — instrukcje dla agenta:**

1. **Rola**: Jesteś doświadczonym specjalistą Google Ads i analityki webowej. Audytujesz pracę agencji marketingowej dla małego sklepu e-commerce.

2. **Kontekst biznesowy**: Mały sklep internetowy, <10k sesji/mies., kilka kampanii Ads.

3. **Dane wejściowe**: JSON-y z katalogu `data/{run_date}/`

4. **Metodologia analizy** (sekcje raportu):
   - **Podsumowanie wykonawcze** — 3-5 zdań: najważniejsze wnioski, ocena 1-10
   - **ROAS i efektywność budżetu** — przychód vs wydatki, ROAS per kampania
   - **Analiza kampanii** — skuteczność każdej kampanii, rekomendacje
   - **Słowa kluczowe i wyszukiwane frazy**:
     - TOP konwertujące słowa kluczowe
     - "Śmieciowe" słowa kluczowe (koszt > 0, konwersje = 0, niski QS)
     - Propozycje negative keywords na podstawie search terms
   - **Wasted spend** — ile budżetu "przepalono" na niekonwertujące frazy
   - **Aktywność agencji** — co zmienili, ocena sensowności zmian
   - **Ruch organiczny (GSC)** — trendy SEO, szanse
   - **Porównanie z poprzednimi okresami** — trendy, zmiany vs poprzedni raport
   - **Problemy i ryzyka** — co wymaga natychmiastowej uwagi
   - **Rekomendacje** — konkretne działania z priorytetem i uzasadnieniem

5. **Zasady analizy**:
   - Każda rekomendacja musi mieć uzasadnienie oparte na danych
   - Przy wasted spend podawaj konkretne kwoty
   - Przy ocenie agencji bądź obiektywny — doceniaj dobre zmiany
   - Porównuj z benchmarkami branżowymi gdzie to możliwe
   - Flaguj brak aktywności agencji jako potencjalny problem

6. **Format wyjściowy**: Markdown, po polsku, z tabelami i emoji do szybkiego skanowania (🟢🟡🔴)

---

### Faza 3: Antigravity Workflow — Orkiestracja

#### [NEW] [analiza-ads.md](file:///home/wales/projects/agents/illuminart-ads/workflows/analiza-ads.md)

Workflow wywoływany komendą `/analiza-ads` w IDE.

**Kroki orkiestracji:**

```markdown
## Krok 1: Parametry

Zapytaj użytkownika o zakres dat (lub użyj domyślnego: ostatnie 14 dni).
Ustal `run_date` jako dzisiejszą datę (YYYY-MM-DD).

## Krok 2: Pobierz dane

Uruchom sekwencyjnie skrypty Python:

1. `python scripts/fetch_ga4.py --start {start} --end {end} --run-date {run_date}`
2. `python scripts/fetch_ads.py --start {start} --end {end} --run-date {run_date}`
3. `python scripts/fetch_gsc.py --start {start} --end {end} --run-date {run_date}`

Sprawdź czy wszystkie JSON-y zostały utworzone w `data/{run_date}/`.

## Krok 3: Załaduj kontekst historyczny

Przeczytaj ostatnie 3 raporty z `reports/history/` (jeśli istnieją).
Zanotuj kluczowe metryki z poprzednich raportów do porównania.

## Krok 4: Analiza

Przeczytaj SKILL.md z `skills/ads-analyst/SKILL.md`.
Przeczytaj wszystkie JSON-y z `data/{run_date}/`.
Wygeneruj raport zgodnie z instrukcjami ze SKILL.md.

## Krok 5: Zapisz raport

Zapisz raport jako `reports/current_report.md`.
Skopiuj raport do `reports/history/{run_date}.md`.

## Krok 6: Podsumowanie

Wyświetl użytkownikowi krótkie podsumowanie (3 najważniejsze wnioski).
Zaproponuj dalszą rozmowę: "Mogę odpowiedzieć na dodatkowe pytania."
```

---

### Faza 4: GitHub Pages

#### [NEW] GitHub Pages config

- `reports/current_report.md` jako główna strona
- Prosty theme (np. Cayman) do czytelnego renderowania Markdown
- Opcjonalnie: index z linkami do historycznych raportów

---

## Open Questions

> [!IMPORTANT]
> **Lokalizacja Workflow i Skill** — Workflow i Skill mogą być umieszczone:
> - **W repozytorium projektu** (`illuminart-ads/workflows/`, `illuminart-ads/skills/`) — bardziej przenośne, commitowane z projektem
> - **W katalogu konfiguracji Antigravity** (`~/.gemini/config/`) — dostępne globalnie
>
> Rekomendacja: **W repozytorium** — bo workflow jest ściśle powiązany z tym konkretnym projektem i jego skryptami. Potwierdź.

> [!IMPORTANT]
> **Search Terms Report** — Google Ads API może nie zwracać pełnych danych o wyszukiwanych frazach dla małych kont (Google ukrywa frazy o niskiej liczbie wyszukiwań ze względu na prywatność). Czy agencja udostępnia Ci raporty search terms w inny sposób?

> [!IMPORTANT]
> **Autentykacja OAuth — odświeżanie tokenu** — OAuth token wygasa po pewnym czasie. Skrypt powinien automatycznie odświeżać refresh token, ale przy pierwszym uruchomieniu wymagana jest interakcja w przeglądarce (autoryzacja). Czy to OK?

## Plan weryfikacji

### Testy automatyczne
1. **Skrypty Python** — uruchomienie każdego skryptu z testowymi credentials
2. **Sprawdzenie struktury JSON** — walidacja że skrypty generują poprawne pliki
3. **Dry-run workflow** — uruchomienie workflow z danymi testowymi

### Weryfikacja manualna
1. **Porównanie z ręcznym eksportem** — porównaj dane ze skryptów z eksportem CSV z panelu GA4/Ads/GSC
2. **Jakość raportu** — przeczytaj pierwszy raport i oceń czy analiza ma sens
3. **GitHub Pages** — sprawdź czy raport renderuje się poprawnie
