# 💬 IlluminArt Chat Worker

Cloudflare Worker proxy — łączy widget czatu na stronie raportu z Gemini API.

## Szybki deploy (jednorazowy setup)

### 1. Konto Cloudflare (darmowe)

Jeśli nie masz konta: [https://dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up)

### 2. Klucz Gemini API

1. Przejdź do [Google AI Studio](https://aistudio.google.com/apikey)
2. Kliknij **Create API key**
3. Skopiuj klucz

### 3. Deploy Worker

```bash
cd chat-worker

# Zaloguj się do Cloudflare
npx wrangler login

# Dodaj sekretny klucz Gemini API
npx wrangler secret put GEMINI_API_KEY
# (wklej klucz po promptcie)

# OPCJONALNIE: Dodaj hasło dostępu do czatu
# Jeśli chcesz, żeby widget wymagał hasła:
npx wrangler secret put CHAT_PASSWORD
# (wklej hasło po promptcie)

# Deploy!
npx wrangler deploy
```

Po deploy dostaniesz URL, np.:
```
https://illuminart-chat.<twój-subdomain>.workers.dev
```

### 4. Skonfiguruj widget

Otwórz `docs/chat-widget.js` i zamień placeholder:

```js
// ZAMIEŃ:
const WORKER_URL = '%%WORKER_URL%%';

// NA twój URL z kroku 3:
const WORKER_URL = 'https://illuminart-chat.twoj-subdomain.workers.dev';
```

### 5. Zaktualizuj ALLOWED_ORIGIN

W `wrangler.toml` upewnij się, że `ALLOWED_ORIGIN` pasuje do Twojej domeny GitHub Pages:

```toml
[vars]
ALLOWED_ORIGIN = "https://wales86.github.io"
```

### 6. Push & Deploy Pages

```bash
git add .
git commit -m "feat: chat widget for report Q&A"
git push
```

GitHub Actions automatycznie zbuduje stronę z widgetem.

## Koszty

- **Cloudflare Worker**: Darmowy tier = **100,000 requestów/dzień** (wystarczy)
- **Gemini API**: `gemini-2.0-flash` ma darmowy tier z limitami per minutę

## Zarządzanie

```bash
# Podgląd logów
npx wrangler tail

# Aktualizacja sekretów
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put CHAT_PASSWORD

# Zmiana modelu — edytuj wrangler.toml → MODEL_NAME
```
