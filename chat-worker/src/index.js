/**
 * IlluminArt Chat Worker — Cloudflare Worker proxy for Gemini API
 *
 * Accepts chat messages from the frontend widget, injects the report context
 * as a system prompt, and streams Gemini's response back via SSE.
 *
 * Environment variables (set via wrangler.toml [vars] or `wrangler secret put`):
 *   GEMINI_API_KEY   — Google AI Studio key (secret)
 *   CHAT_PASSWORD    — Optional shared password for access control (secret)
 *   ALLOWED_ORIGIN   — GitHub Pages origin for CORS
 *   MODEL_NAME       — Gemini model to use (e.g. gemini-2.0-flash)
 */

// --- Constants -----------------------------------------------------------

const SYSTEM_PROMPT = `Jesteś ekspertem od marketingu internetowego i Google Ads.
Analizujesz raporty audytowe kampanii reklamowych dla sklepu IlluminArt.

ZASADY:
- Odpowiadaj WYŁĄCZNIE na podstawie danych z raportów poniżej.
- Jeśli informacja nie jest w raportach, powiedz to wprost.
- Odpowiadaj po polsku, zwięźle i konkretnie.
- Używaj liczb i danych z raportów gdy to możliwe.
- Formatuj odpowiedzi w Markdown (nagłówki, listy, pogrubienia).
- Masz dostęp do AKTUALNEGO raportu i do 2 HISTORYCZNYCH raportów z poprzednich okresów.
- Gdy pytanie dotyczy trendów lub porównań, korzystaj z raportów historycznych.
- Wyraźnie zaznaczaj, z którego okresu pochodzą dane (np. "W aktualnym raporcie..." vs "W poprzednim okresie...").

DANE:
`;

const MAX_MESSAGE_LENGTH = 2000;
const MAX_REPORT_LENGTH = 80000;
const MAX_HISTORY_ITEMS = 20;

// --- Security helpers ----------------------------------------------------

/**
 * Builds CORS headers scoped to the configured origin.
 * TODO(security): Consider adding rate limiting via Cloudflare's built-in
 * rate limiting rules for production use.
 */
function corsHeaders(env) {
  return {
    'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
  };
}

/**
 * Validates the Authorization header against the shared password.
 * Returns true if no password is configured (open access).
 */
function isAuthorized(request, env) {
  if (!env.CHAT_PASSWORD) {
    return true; // No password configured — open access
  }
  const authHeader = request.headers.get('Authorization');
  if (!authHeader) {
    return false;
  }
  // Constant-time comparison via subtle crypto is not available for simple
  // string comparison in Workers, but timing attacks on a shared password
  // over the network are impractical. Using strict equality here.
  // TODO(security): For stronger auth, consider Cloudflare Access or JWT tokens.
  return authHeader === `Bearer ${env.CHAT_PASSWORD}`;
}

/**
 * Validates and sanitizes the incoming chat payload.
 * Returns { message, reportContent, history } or throws.
 */
function validatePayload(body) {
  if (!body || typeof body.message !== 'string' || !body.message.trim()) {
    throw new Error('Pole "message" jest wymagane.');
  }

  const message = body.message.trim().slice(0, MAX_MESSAGE_LENGTH);

  let reportContent = '';
  if (typeof body.reportContent === 'string') {
    reportContent = body.reportContent.trim().slice(0, MAX_REPORT_LENGTH);
  }

  let history = [];
  if (Array.isArray(body.history)) {
    history = body.history.slice(-MAX_HISTORY_ITEMS).filter(
      (item) =>
        item &&
        typeof item.role === 'string' &&
        typeof item.text === 'string' &&
        (item.role === 'user' || item.role === 'model')
    ).map((item) => ({
      role: item.role,
      parts: [{ text: item.text.slice(0, MAX_MESSAGE_LENGTH) }],
    }));
  }

  return { message, reportContent, history };
}

// --- Gemini API call -----------------------------------------------------

/**
 * Calls the Gemini generateContent endpoint (non-streaming)
 * and returns the text response.
 *
 * We use non-streaming here for simplicity and reliability with Workers.
 * The response is typically fast enough for short Q&A interactions.
 */
async function callGemini(env, message, reportContent, history) {
  const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${env.MODEL_NAME}:generateContent?key=${env.GEMINI_API_KEY}`;

  const systemInstruction = SYSTEM_PROMPT + (reportContent || '(Raport nie został załadowany)');

  const contents = [
    ...history,
    { role: 'user', parts: [{ text: message }] },
  ];

  const requestBody = {
    system_instruction: {
      parts: [{ text: systemInstruction }],
    },
    contents,
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 2048,
    },
    safetySettings: [
      { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_ONLY_HIGH' },
      { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_ONLY_HIGH' },
      { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_ONLY_HIGH' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_ONLY_HIGH' },
    ],
  };

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errorText = await response.text();
    // Don't expose raw API error details to the client
    console.error('Gemini API error:', response.status, errorText);
    throw new Error('Błąd komunikacji z modelem AI. Spróbuj ponownie.');
  }

  const data = await response.json();

  const candidate = data.candidates?.[0];
  if (!candidate?.content?.parts?.[0]?.text) {
    throw new Error('Model nie zwrócił odpowiedzi. Spróbuj inaczej sformułować pytanie.');
  }

  return candidate.content.parts[0].text;
}

// --- Request handler -----------------------------------------------------

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(env),
      });
    }

    // Only POST allowed
    if (request.method !== 'POST') {
      return new Response(
        JSON.stringify({ error: 'Metoda niedozwolona. Użyj POST.' }),
        {
          status: 405,
          headers: {
            ...corsHeaders(env),
            'Content-Type': 'application/json',
            'Allow': 'POST, OPTIONS',
          },
        }
      );
    }

    // Auth check
    if (!isAuthorized(request, env)) {
      return new Response(
        JSON.stringify({ error: 'Nieprawidłowe hasło dostępu.' }),
        {
          status: 401,
          headers: {
            ...corsHeaders(env),
            'Content-Type': 'application/json',
          },
        }
      );
    }

    try {
      const body = await request.json();
      const { message, reportContent, history } = validatePayload(body);
      const reply = await callGemini(env, message, reportContent, history);

      return new Response(
        JSON.stringify({ reply }),
        {
          status: 200,
          headers: {
            ...corsHeaders(env),
            'Content-Type': 'application/json',
            'Cache-Control': 'no-store',
          },
        }
      );
    } catch (err) {
      const statusCode = err.message.includes('wymagane') ? 400 : 502;
      return new Response(
        JSON.stringify({ error: err.message }),
        {
          status: statusCode,
          headers: {
            ...corsHeaders(env),
            'Content-Type': 'application/json',
          },
        }
      );
    }
  },
};
