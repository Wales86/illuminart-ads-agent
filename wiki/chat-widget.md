# Chat Widget — Cloudflare Worker

Widget czatu na stronie raportu (GitHub Pages) pozwala zadawać pytania o raport w języku naturalnym.

## Jak działa

```
Przeglądarka → Cloudflare Worker (proxy) → Gemini API → odpowiedź
```

1. Widget na stronie wysyła pytanie do Cloudflare Worker
2. Worker dorzuca treść raportu jako kontekst i pyta Gemini API
3. Odpowiedź wraca do przeglądarki

## Setup

Szczegółowa instrukcja deploy: [`chat-worker/README.md`](../chat-worker/README.md)

**Klucz Gemini API** przechowywany jako secret w Cloudflare Worker (nie w kodzie).

## Pliki

| Plik | Rola |
|---|---|
| `chat-worker/src/index.js` | Logika Worker |
| `chat-worker/wrangler.toml` | Konfiguracja deploy |
| `docs/chat-widget.js` | Widget czatu (frontend) |
| `docs/chat-widget.css` | Style widgetu |

## Bezpieczeństwo strony (TODO)

Strona raportu na GitHub Pages jest obecnie **publiczna**. Planujemy dodać ochronę hasłem za pomocą [staticrypt](https://github.com/robinmoisson/staticrypt):

- Każda strona będzie zaszyfrowana w pipeline CI (`deploy-pages.yml`)
- Wspólnicy podają jedno wspólne hasło, które przeglądarka zapamiętuje na 30 dni
- Bez hasła treść strony jest nieczytelna (AES-256, nie JS overlay)

```bash
# Przykład integracji w workflow:
npx staticrypt _site_build/index.html -p "haslo" --remember 30 --template-title "IlluminArt Raport"
```
