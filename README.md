# 📊 IlluminArt Ads — Agent Audytu Marketingowego

Automatyczny agent do dwutygodniowego audytu kampanii Google Ads i analityki. Pobiera dane z GA4, Google Ads i Search Console, a następnie generuje raport Markdown oceniający pracę agencji marketingowej.

## Spis treści

- [Szybki start](#szybki-start)
- [Konfiguracja Google Cloud](#konfiguracja-google-cloud)
- [Konfiguracja projektu](#konfiguracja-projektu)
- [Uruchamianie](#uruchamianie)
- [Chat Widget (AI Q&A)](#chat-widget-ai-qa)
- [Struktura projektu](#struktura-projektu)

## Szybki start

```bash
# 1. Sklonuj repozytorium
git clone <repo-url>
cd illuminart-ads

# 2. Zainstaluj zależności Python
python -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt

# 3. Skonfiguruj credentials (zobacz sekcję poniżej)
# 4. Uzupełnij config/settings.yaml

# 5. Uruchom workflow w Antigravity IDE:
#    Wpisz: /analiza-ads
```

## Konfiguracja Google Cloud

### Krok 1: Utwórz projekt GCP

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Kliknij **Select a project** → **New Project**
3. Nazwa: np. `illuminart-ads-audit`
4. Kliknij **Create**

### Krok 2: Włącz wymagane API

W panelu projektu przejdź do **APIs & Services → Library** i włącz:

1. **Google Analytics Data API** — do GA4
2. **Google Ads API** — do kampanii Ads
3. **Google Search Console API** — do danych SEO

### Krok 3: Utwórz OAuth2 credentials

1. Przejdź do **APIs & Services → Credentials**
2. Kliknij **Create Credentials → OAuth client ID**
3. Jeśli wymaga ekranu zgody: **Configure Consent Screen**
   - User type: **External** (lub Internal jeśli masz Workspace)
   - Nazwa aplikacji: `IlluminArt Ads Audit`
   - Dodaj scopes:
     - `https://www.googleapis.com/auth/analytics.readonly`
     - `https://www.googleapis.com/auth/adwords`
     - `https://www.googleapis.com/auth/webmasters.readonly`
   - Dodaj swój email jako test user
4. Wróć do **Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Nazwa: `IlluminArt Audit CLI`
5. Pobierz plik JSON → zapisz jako `config/credentials.json`

### Krok 4: Developer Token (Google Ads)

1. Zaloguj się do [Google Ads](https://ads.google.com/)
2. Przejdź do **Tools & Settings → Setup → API Center**
3. Jeśli nie masz jeszcze tokenu, kliknij **Apply for access**
4. Skopiuj **Developer Token**
5. Wklej go do `config/settings.yaml` → `google_ads.developer_token`

> **Uwaga:** Nowy token startuje w trybie **Test Account** — to wystarczy, bo masz dostęp do swojego konta. Pełna weryfikacja (Basic/Standard) jest wymagana dopiero przy dostępie do wielu kont.

### Krok 5: Pierwsza autoryzacja

Przy pierwszym uruchomieniu dowolnego skryptu otworzy się przeglądarka z ekranem autoryzacji Google. Zaakceptuj dostępy — token zostanie zapisany w `config/token.json` i będzie automatycznie odświeżany.

```bash
# Test autoryzacji
python scripts/fetch_ga4.py --help
```

## Konfiguracja projektu

Uzupełnij plik `config/settings.yaml`:

```yaml
ga4:
  property_id: "123456789"           # GA4 → Admin → Property Settings

google_ads:
  customer_id: "123-456-7890"        # Prawy górny róg panelu Ads
  developer_token: "xxxxxxxx"        # API Center
  login_customer_id: ""              # Puste (chyba że MCC)

gsc:
  site_url: "https://twojsklep.pl"   # URL z Search Console
```

### Gdzie znaleźć Property ID (GA4)?

1. Otwórz [Google Analytics](https://analytics.google.com/)
2. **Admin** (ikona koła zębatego) → **Property Settings**
3. Skopiuj **Property ID** (same cyfry)

### Gdzie znaleźć Customer ID (Google Ads)?

1. Otwórz [Google Ads](https://ads.google.com/)
2. ID jest w prawym górnym rogu, format: `XXX-XXX-XXXX`

## Uruchamianie

### Przez Antigravity IDE (rekomendowane)

Otwórz projekt w Antigravity IDE i wpisz w czacie:

```
/analiza-ads
```

Agent przeprowadzi cały proces automatycznie i pozwoli Ci zadać dodatkowe pytania.

### Ręczne uruchomienie skryptów

Jeśli chcesz pobrać dane ręcznie:

```bash
# Aktywuj venv
source .venv/bin/activate

# Pobierz dane za ostatnie 14 dni
python scripts/fetch_ga4.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20
python scripts/fetch_ads.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20
python scripts/fetch_gsc.py --start 2026-05-06 --end 2026-05-20 --run-date 2026-05-20

# Dane zostaną zapisane w data/2026-05-20/
```

## Chat Widget (AI Q&A)

Na stronie raportu (GitHub Pages) jest pływający widget czatu, który pozwala wspólnikom zadawać pytania o raport w języku naturalnym. AI odpowiada na podstawie danych z raportu.

**Jak to działa:**
1. Widget na stronie wysyła pytanie do Cloudflare Worker (serverless proxy)
2. Worker dorzuca treść raportu jako kontekst i pyta Gemini API
3. Odpowiedź wraca do przeglądarki

**Setup:** Zobacz szczegółową instrukcję w [`chat-worker/README.md`](chat-worker/README.md)

## Struktura projektu

```
illuminart-ads/
├── scripts/                   # Skrypty Python do pobierania danych
│   ├── fetch_ga4.py           # GA4 Data API
│   ├── fetch_ads.py           # Google Ads API + change history
│   ├── fetch_gsc.py           # Search Console API
│   ├── utils.py               # Wspólne funkcje (auth, I/O)
│   └── requirements.txt       # Zależności Python
├── chat-worker/               # Cloudflare Worker — proxy do Gemini API
│   ├── src/index.js           # Logika Worker
│   ├── wrangler.toml          # Konfiguracja deploy
│   └── README.md              # Instrukcja deploy
├── docs/                      # Assety strony Pages
│   ├── chat-widget.js         # Widget czatu (frontend)
│   └── chat-widget.css        # Style widgetu
├── data/                      # Surowe dane JSON (gitignored)
│   └── YYYY-MM-DD/            # Katalog per uruchomienie
├── reports/
│   ├── current_report.md      # Aktualny raport
│   └── history/               # Archiwum raportów
│       └── YYYY-MM-DD.md
├── .agents/
│   ├── skills/
│   │   └── ads-analyst/
│   │       └── SKILL.md       # Prompt eksperta analityki
│   └── workflows/
│       └── analiza-ads.md     # Orkiestracja workflow
├── config/
│   ├── settings.yaml          # Konfiguracja (IDs, tokens)
│   ├── credentials.json       # OAuth credentials (gitignored)
│   └── token.json             # OAuth token (gitignored)
├── .gitignore
└── README.md
```

## Bezpieczeństwo

- `credentials.json` i `token.json` są w `.gitignore` — **nigdy nie commituj**
- Katalog `data/` jest w `.gitignore` — surowe dane nie trafiają do repo
- Developer Token jest w `settings.yaml` — rozważ przeniesienie do zmiennej środowiskowej w przyszłości
- Skrypty używają OAuth2 z automatycznym odświeżaniem tokenu
- Klucz Gemini API przechowywany jako secret w Cloudflare Worker (nie w kodzie)

### 🔒 Hasło na stronę (TODO)

Strona raportu na GitHub Pages jest obecnie **publiczna**. Planujemy dodać ochronę hasłem za pomocą [staticrypt](https://github.com/robinmoisson/staticrypt) — narzędzia, które szyfruje HTML za pomocą AES-256. Po wdrożeniu:

- Każda strona będzie zaszyfrowana w pipeline CI (`deploy-pages.yml`)
- Wspólnicy podają jedno wspólne hasło, które przeglądarka zapamiętuje na 30 dni
- Bez hasła treść strony jest nieczytelna (prawdziwe szyfrowanie, nie JS overlay)

```bash
# Przykład integracji w workflow:
npx staticrypt _site_build/index.html -p "haslo" --remember 30 --template-title "IlluminArt Raport"
```
