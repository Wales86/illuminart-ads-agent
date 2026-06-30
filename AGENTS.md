# 📊 IlluminArt Ads — Agent Audytu Marketingowego

Automatyczny agent do dwutygodniowego audytu kampanii Google Ads i analityki. Pobiera dane z GA4, Google Ads i Search Console, generuje raport Markdown oceniający pracę agencji marketingowej.

---

## Dla użytkownika: Jak uruchomić audyt

### Wymagania wstępne (jednorazowo)

1. **Skonfiguruj Google Cloud** → [`wiki/gcp-setup.md`](wiki/gcp-setup.md)
2. **Zainstaluj zależności Python:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r scripts/requirements.txt
   ```
3. **Uzupełnij** `config/settings.yaml` (property ID, customer ID, site URL)

### Uruchomienie audytu

Otwórz projekt w Antigravity IDE i wpisz w czacie:

```
/analiza-ads
```

Agent przeprowadzi cały proces automatycznie — pobierze dane, wygeneruje raport i zaproponuje dalszą rozmowę.

### Ręczne uruchomienie skryptów

```bash
source .venv/bin/activate

python scripts/fetch_ga4.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20
python scripts/fetch_ads.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20
python scripts/fetch_gsc.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20

# Dane zostaną zapisane w data/2026-05-20/
```

---

## Dla agenta: Mapa projektu

### Architektura przepływu

```
/analiza-ads
    └─► .agents/workflows/analiza-ads.md   ← orkiestracja
            ├─► scripts/fetch_ga4.py
            ├─► scripts/fetch_ads.py
            ├─► scripts/fetch_gsc.py
            │       └─► data/YYYY-MM-DD/*.json   ← surowe dane
            ├─► reports/history/*.md              ← kontekst historyczny
            └─► .agents/skills/ads-analyst/SKILL.md  ← ekspert analizy
                    └─► reports/current_report.md
                            └─► reports/history/YYYY-MM-DD.md
```

### Struktura plików

```
illuminart-ads/
├── .agents/
│   ├── skills/ads-analyst/SKILL.md    # Prompt eksperta — metodologia i format raportu
│   └── workflows/analiza-ads.md       # Workflow wywoływany przez /analiza-ads
├── scripts/
│   ├── fetch_ga4.py                   # GA4: ruch, źródła, konwersje, top strony
│   ├── fetch_ads.py                   # Ads: kampanie, keywords, search terms, change history
│   ├── fetch_gsc.py                   # GSC: zapytania, strony, trend dzienny
│   ├── utils.py                       # OAuth2 auth, settings, CLI args, JSON I/O
│   └── requirements.txt               # Zależności Python
├── config/
│   ├── settings.yaml                  # IDs i tokeny (wypełnia user)
│   ├── credentials.json               # OAuth credentials (gitignored)
│   └── token.json                     # OAuth token (gitignored, auto-refresh)
├── data/
│   └── YYYY-MM-DD/                    # Katalog per uruchomienie (gitignored)
│       ├── ga4_traffic.json
│       ├── ga4_sources.json
│       ├── ga4_conversions.json
│       ├── ga4_pages.json
│       ├── ads_campaigns.json
│       ├── ads_keywords.json
│       ├── ads_search_terms.json
│       ├── ads_changes.json
│       ├── gsc_queries.json
│       └── gsc_pages.json
├── reports/
│   ├── current_report.md              # Aktualny raport (też GitHub Pages)
│   └── history/                       # Archiwum — ostatnie 3 ładowane do kontekstu
│       └── YYYY-MM-DD.md
├── chat-worker/                       # Cloudflare Worker — proxy do Gemini API
│   ├── src/index.js
│   └── wrangler.toml
├── site/                              # GitHub Pages assets
├── wiki/                              # Dodatkowa dokumentacja
│   ├── gcp-setup.md                   # Krok-po-kroku setup Google Cloud
│   └── chat-widget.md                 # Dokumentacja chat widgetu
└── AGENTS.md                          # Ten plik
```

### Kluczowe pliki agenta

| Plik | Rola |
|---|---|
| [`.agents/workflows/analiza-ads.md`](.agents/workflows/analiza-ads.md) | Główny workflow — tu zaczyna się orkiestracja |
| [`.agents/skills/ads-analyst/SKILL.md`](.agents/skills/ads-analyst/SKILL.md) | Prompt eksperta — metodologia analizy, format raportu |
| [`config/settings.yaml`](config/settings.yaml) | Konfiguracja: property IDs, customer ID, site URL |
| [`scripts/utils.py`](scripts/utils.py) | Wspólna logika: `load_settings()`, `get_oauth_credentials()`, `save_json()` |

### Kluczowe decyzje architektoniczne

1. **OAuth2 Desktop flow** dla wszystkich 3 API — jeden zestaw credentials (`credentials.json` + `token.json`)
2. **Dane per run** w `data/{YYYY-MM-DD}/` — pełna historia źródłowa, gitignored
3. **Jeden prompt z wszystkimi danymi** (nie łańcuch) — przy małej skali danych to optymalne
4. **Skill + Workflow separation** — Skill to ekspertyza analityczna, Workflow to orkiestracja kroków
5. **Automatyczne flagowanie wasted spend** już na etapie skryptów (`is_wasted: true` w JSON keywords)

### Dane zbierane przez skrypty

| Skrypt | Pliki wyjściowe | Zawartość |
|---|---|---|
| `fetch_ga4.py` | `ga4_traffic.json` | Sessions, users, engagement rate, bounce rate (po dniach) |
| | `ga4_sources.json` | Ruch wg źródła/medium/kampanii + konwersje i revenue |
| | `ga4_conversions.json` | Zakupy wg daty i źródła |
| | `ga4_pages.json` | Top 30 stron wg wyświetleń |
| `fetch_ads.py` | `ads_campaigns.json` | Kampanie: cost, conversions, ROAS, CTR, CPC |
| | `ads_keywords.json` | Keywords + `is_wasted` flag (koszt > 0, konwersje = 0) |
| | `ads_search_terms.json` | Wyszukiwane frazy — do identyfikacji przepalonego budżetu |
| | `ads_changes.json` | Historia zmian agencji: co, kiedy, kto |
| `fetch_gsc.py` | `gsc_queries.json` | Top 100 zapytań organicznych |
| | `gsc_pages.json` | Top 50 stron organicznych |

### Bezpieczeństwo

- `credentials.json`, `token.json` → `.gitignore` — **nigdy nie commituj**
- `data/` → `.gitignore` — surowe dane nie trafiają do repo
- Developer Token w `settings.yaml` — rozważ zmienną środowiskową w przyszłości
- Klucz Gemini API jako secret w Cloudflare Worker (nie w kodzie)

---

## Dodatkowa dokumentacja

- [`wiki/gcp-setup.md`](wiki/gcp-setup.md) — Krok-po-kroku konfiguracja Google Cloud, OAuth2, Developer Token
- [`wiki/chat-widget.md`](wiki/chat-widget.md) — Dokumentacja chat widgetu i TODO: password protection
- [`chat-worker/README.md`](chat-worker/README.md) — Instrukcja deploy Cloudflare Worker


## github pages url
https://wales86.github.io/illuminart-ads-agent/index.html