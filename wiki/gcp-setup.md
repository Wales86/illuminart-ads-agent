# Konfiguracja Google Cloud Platform

Jednorazowy setup wymagany przed pierwszym uruchomieniem agenta.

## Krok 1: Utwórz projekt GCP

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Kliknij **Select a project** → **New Project**
3. Nazwa: np. `illuminart-ads-audit`
4. Kliknij **Create**

## Krok 2: Włącz wymagane API

W panelu projektu przejdź do **APIs & Services → Library** i włącz:

1. **Google Analytics Data API** — do GA4
2. **Google Ads API** — do kampanii Ads
3. **Google Search Console API** — do danych SEO

## Krok 3: Utwórz OAuth2 credentials

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

## Krok 4: Developer Token (Google Ads)

1. Zaloguj się do [Google Ads](https://ads.google.com/)
2. Przejdź do **Tools & Settings → Setup → API Center**
3. Jeśli nie masz jeszcze tokenu, kliknij **Apply for access**
4. Skopiuj **Developer Token**
5. Wklej go do `config/settings.yaml` → `google_ads.developer_token`

> **Uwaga:** Nowy token startuje w trybie **Test Account** — to wystarczy, bo masz dostęp do swojego konta. Pełna weryfikacja (Basic/Standard) jest wymagana dopiero przy dostępie do wielu kont.
>
> **Uwaga 2:** Uzyskanie tokenu może zająć kilka dni. Możesz zacząć od testowania GA4 i GSC — te działają od razu po OAuth2 setup.

## Krok 5: Pierwsza autoryzacja (OAuth flow)

Przy pierwszym uruchomieniu dowolnego skryptu otworzy się przeglądarka z ekranem autoryzacji Google. Zaakceptuj dostępy — token zostanie zapisany w `config/token.json` i będzie automatycznie odświeżany.

```bash
# Test autoryzacji
python scripts/fetch_ga4.py --help
```

## Krok 6: Uzupełnij config/settings.yaml

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

## Bezpieczeństwo

- `credentials.json` i `token.json` są w `.gitignore` — **nigdy nie commituj**
- Katalog `data/` jest w `.gitignore` — surowe dane nie trafiają do repo
- Developer Token jest w `settings.yaml` — rozważ przeniesienie do zmiennej środowiskowej
- OAuth token jest automatycznie odświeżany przez skrypty
