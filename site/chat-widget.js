/**
 * IlluminArt Chat Widget
 *
 * Pływający widget czatu umożliwiający rozmowę z AI na temat raportu
 * audytowego. Komunikuje się z Cloudflare Worker proxy do Gemini API.
 *
 * Security notes:
 * - Uses textContent / createElement exclusively (no innerHTML).
 * - API key is never exposed client-side — stored in Worker env.
 * - Optional password auth via Authorization header.
 * - Chat history stored in sessionStorage (cleared on tab close).
 *   No sensitive tokens stored client-side.
 */

(function () {
  'use strict';

  // --- Configuration -----------------------------------------------------
  // IMPORTANT: Update WORKER_URL after deploying the Cloudflare Worker.
  // You'll get it from `npx wrangler deploy` output, e.g.:
  //   https://illuminart-chat.<your-subdomain>.workers.dev
  const WORKER_URL = '%%WORKER_URL%%';

  const STORAGE_KEY = 'illuminart-chat-history';
  const STORAGE_PWD_KEY = 'illuminart-chat-pwd';

  // --- State -------------------------------------------------------------
  let isOpen = false;
  let isLoading = false;
  let chatHistory = []; // { role: 'user'|'model', text: string }
  let reportContent = '';
  let password = '';

  // --- DOM Building (secure — no innerHTML) ------------------------------

  /**
   * Creates a DOM element with attributes and children.
   * All text is set via textContent — safe from XSS.
   */
  function el(tag, attrs, children) {
    const element = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (key === 'textContent') {
          element.textContent = value;
        } else if (key.startsWith('on')) {
          element.addEventListener(key.slice(2).toLowerCase(), value);
        } else {
          element.setAttribute(key, value);
        }
      }
    }
    if (children) {
      for (const child of children) {
        if (typeof child === 'string') {
          element.appendChild(document.createTextNode(child));
        } else if (child) {
          element.appendChild(child);
        }
      }
    }
    return element;
  }

  /**
   * Converts a subset of Markdown to DOM nodes (safe — no innerHTML).
   * Supports: **bold**, headers (#), lists (- and 1.), code (`), paragraphs.
   */
  function markdownToNodes(text) {
    const fragment = document.createDocumentFragment();
    const lines = text.split('\n');
    let currentList = null;
    let currentListType = null;

    function processInline(line) {
      const span = document.createElement('span');
      // Split on **bold** patterns
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      for (const part of parts) {
        if (part.startsWith('**') && part.endsWith('**')) {
          const strong = document.createElement('strong');
          strong.textContent = part.slice(2, -2);
          span.appendChild(strong);
        } else {
          // Handle inline `code`
          const codeParts = part.split(/(`[^`]+`)/g);
          for (const cp of codeParts) {
            if (cp.startsWith('`') && cp.endsWith('`')) {
              const code = document.createElement('code');
              code.textContent = cp.slice(1, -1);
              span.appendChild(code);
            } else {
              span.appendChild(document.createTextNode(cp));
            }
          }
        }
      }
      return span;
    }

    function flushList() {
      if (currentList) {
        fragment.appendChild(currentList);
        currentList = null;
        currentListType = null;
      }
    }

    for (const line of lines) {
      const trimmed = line.trim();

      // Empty line — flush list
      if (!trimmed) {
        flushList();
        continue;
      }

      // Headers
      const headerMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (headerMatch) {
        flushList();
        const level = Math.min(headerMatch[1].length, 6);
        const h = document.createElement('h' + level);
        h.appendChild(processInline(headerMatch[2]));
        fragment.appendChild(h);
        continue;
      }

      // Unordered list
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (currentListType !== 'ul') {
          flushList();
          currentList = document.createElement('ul');
          currentListType = 'ul';
        }
        const li = document.createElement('li');
        li.appendChild(processInline(trimmed.slice(2)));
        currentList.appendChild(li);
        continue;
      }

      // Ordered list
      const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
      if (olMatch) {
        if (currentListType !== 'ol') {
          flushList();
          currentList = document.createElement('ol');
          currentListType = 'ol';
        }
        const li = document.createElement('li');
        li.appendChild(processInline(olMatch[1]));
        currentList.appendChild(li);
        continue;
      }

      // Paragraph
      flushList();
      const p = document.createElement('p');
      p.appendChild(processInline(trimmed));
      fragment.appendChild(p);
    }

    flushList();
    return fragment;
  }

  // --- Extract report content from page ----------------------------------

  let reportLoaded = false;

  async function extractReportContent() {
    if (reportLoaded) return;

    // Current report from DOM
    const reportEl = document.getElementById('report-content');
    if (reportEl) {
      reportContent = '=== AKTUALNY RAPORT ===\n' + reportEl.textContent.trim();
    } else {
      // Fallback: grab main body text, limited to prevent huge payloads
      const body = document.body.textContent || '';
      reportContent = '=== AKTUALNY RAPORT ===\n' + body.trim().slice(0, 50000);
    }

    // Fetch historical reports (non-blocking — chat works even if this fails)
    try {
      const response = await fetch('report-history.json');
      if (response.ok) {
        const history = await response.json();
        if (Array.isArray(history) && history.length > 0) {
          for (const report of history) {
            if (report && typeof report.content === 'string' && report.content.trim()) {
              reportContent += '\n\n=== RAPORT HISTORYCZNY (' + (report.date || 'brak daty') + ') ===\n';
              reportContent += report.content.trim();
            }
          }
        }
      }
    } catch (_e) {
      // Historical reports unavailable — continue with current report only
    }

    // Limit total context size
    reportContent = reportContent.slice(0, 80000);
    reportLoaded = true;
  }

  // --- Session storage for chat history ----------------------------------

  function saveHistory() {
    try {
      // sessionStorage only — cleared when tab closes
      // No sensitive tokens here, just conversation text
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory));
    } catch (_e) {
      // Storage full or unavailable — silently continue
    }
  }

  function loadHistory() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        chatHistory = JSON.parse(saved);
      }
    } catch (_e) {
      chatHistory = [];
    }
  }

  function loadPassword() {
    try {
      password = sessionStorage.getItem(STORAGE_PWD_KEY) || '';
    } catch (_e) {
      password = '';
    }
  }

  function savePassword(pwd) {
    password = pwd;
    try {
      sessionStorage.setItem(STORAGE_PWD_KEY, pwd);
    } catch (_e) {
      // Silently continue
    }
  }

  // --- Build Widget UI ---------------------------------------------------

  function buildWidget() {
    // --- FAB Button ---
    const fabIcon = '\u{1F4AC}'; // 💬
    const fab = el('button', {
      class: 'chat-fab',
      'aria-label': 'Otwórz czat z AI o raporcie',
      'aria-expanded': 'false',
      id: 'chat-fab',
      textContent: fabIcon,
      onClick: togglePanel,
    });

    // --- Panel ---
    const panel = el('div', {
      class: 'chat-panel',
      'data-open': 'false',
      id: 'chat-panel',
      role: 'dialog',
      'aria-label': 'Czat z AI o raporcie',
    });

    // Header
    const headerDot = el('div', { class: 'chat-header-dot' });
    const headerTitleText = el('div', { class: 'chat-header-title', textContent: 'Asystent Raportu' });
    const headerSubtitle = el('div', { class: 'chat-header-subtitle', textContent: 'AI · Gemini' });
    const headerTitleWrap = el('div', null, [headerTitleText, headerSubtitle]);
    const headerInfo = el('div', { class: 'chat-header-info' }, [headerDot, headerTitleWrap]);
    const closeBtn = el('button', {
      class: 'chat-close-btn',
      'aria-label': 'Zamknij czat',
      textContent: '\u{2715}', // ✕
      onClick: togglePanel,
    });
    const header = el('div', { class: 'chat-header' }, [headerInfo, closeBtn]);
    panel.appendChild(header);

    // Password gate (hidden by default, shown if Worker returns 401)
    const pwdGate = el('div', {
      class: 'chat-password-gate',
      id: 'chat-password-gate',
      style: 'display: none;',
    });
    const pwdIcon = el('div', { textContent: '\u{1F512}', style: 'font-size: 32px;' }); // 🔒
    const pwdText = el('p', { textContent: 'Podaj hasło dostępu do czatu:' });
    const pwdInput = el('input', {
      class: 'chat-password-input',
      type: 'password',
      id: 'chat-password-input',
      placeholder: 'Hasło...',
      autocomplete: 'off',
    });
    const pwdError = el('div', {
      class: 'chat-password-error',
      id: 'chat-password-error',
      textContent: 'Nieprawidłowe hasło',
    });
    const pwdSubmit = el('button', {
      class: 'chat-password-submit',
      textContent: 'Wejdź',
      onClick: handlePasswordSubmit,
    });
    pwdGate.appendChild(pwdIcon);
    pwdGate.appendChild(pwdText);
    pwdGate.appendChild(pwdInput);
    pwdGate.appendChild(pwdError);
    pwdGate.appendChild(pwdSubmit);
    panel.appendChild(pwdGate);

    // Messages area
    const messages = el('div', {
      class: 'chat-messages',
      id: 'chat-messages',
      'aria-live': 'polite',
    });

    // Welcome message
    const welcomeIcon = el('span', { class: 'chat-msg-welcome-icon', textContent: '\u{1F4CA}' }); // 📊
    const welcomeText = document.createTextNode(
      'Cześć! Jestem asystentem raportu audytowego. Zapytaj mnie o wyniki kampanii, ROAS, rekomendacje — cokolwiek z raportu.'
    );
    const welcomeMsg = el('div', { class: 'chat-msg chat-msg-welcome' }, [welcomeIcon, welcomeText]);
    messages.appendChild(welcomeMsg);
    panel.appendChild(messages);

    // Typing indicator
    const typingDot1 = el('div', { class: 'chat-typing-dot' });
    const typingDot2 = el('div', { class: 'chat-typing-dot' });
    const typingDot3 = el('div', { class: 'chat-typing-dot' });
    const typing = el('div', {
      class: 'chat-typing',
      id: 'chat-typing',
      'data-visible': 'false',
    }, [typingDot1, typingDot2, typingDot3]);
    messages.appendChild(typing);

    // Error display
    const errorEl = el('div', { class: 'chat-error', id: 'chat-error' });
    panel.appendChild(errorEl);

    // Input area
    const input = el('textarea', {
      class: 'chat-input',
      id: 'chat-input',
      placeholder: 'Zapytaj o raport...',
      rows: '1',
      'aria-label': 'Wiadomość do AI',
    });
    input.addEventListener('keydown', handleInputKeydown);
    input.addEventListener('input', autoResizeInput);

    // Send button — use SVG created safely via DOMParser
    const sendSvgStr = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';
    const sendSvgDoc = new DOMParser().parseFromString(sendSvgStr, 'image/svg+xml');
    const sendBtn = el('button', {
      class: 'chat-send-btn',
      id: 'chat-send-btn',
      'aria-label': 'Wyślij wiadomość',
      onClick: handleSend,
    });
    sendBtn.appendChild(sendSvgDoc.documentElement);

    const inputArea = el('div', { class: 'chat-input-area' }, [input, sendBtn]);
    panel.appendChild(inputArea);

    // Append to body
    document.body.appendChild(fab);
    document.body.appendChild(panel);

    // Restore history
    loadHistory();
    loadPassword();
    renderHistoryMessages();
  }

  // --- Render saved history messages into DOM ----------------------------

  function renderHistoryMessages() {
    const messagesEl = document.getElementById('chat-messages');
    for (const msg of chatHistory) {
      appendMessageToDOM(msg.role === 'user' ? 'user' : 'ai', msg.text);
    }
    scrollToBottom();
  }

  // --- Panel toggle ------------------------------------------------------

  function togglePanel() {
    isOpen = !isOpen;
    const panel = document.getElementById('chat-panel');
    const fab = document.getElementById('chat-fab');
    panel.setAttribute('data-open', String(isOpen));
    fab.setAttribute('aria-expanded', String(isOpen));

    if (isOpen) {
      // Fire-and-forget — loads report context in background
      extractReportContent();
      const input = document.getElementById('chat-input');
      setTimeout(function () { input.focus(); }, 300);
    }
  }

  // --- Password handling -------------------------------------------------

  function showPasswordGate() {
    const gate = document.getElementById('chat-password-gate');
    const messages = document.getElementById('chat-messages');
    const inputArea = document.querySelector('.chat-input-area');
    gate.style.display = 'flex';
    messages.style.display = 'none';
    if (inputArea) inputArea.style.display = 'none';
  }

  function hidePasswordGate() {
    const gate = document.getElementById('chat-password-gate');
    const messages = document.getElementById('chat-messages');
    const inputArea = document.querySelector('.chat-input-area');
    gate.style.display = 'none';
    messages.style.display = 'flex';
    if (inputArea) inputArea.style.display = 'flex';
  }

  function handlePasswordSubmit() {
    const input = document.getElementById('chat-password-input');
    const errorEl = document.getElementById('chat-password-error');
    const pwd = input.value.trim();
    if (!pwd) {
      errorEl.style.display = 'block';
      errorEl.textContent = 'Podaj hasło';
      return;
    }
    savePassword(pwd);
    errorEl.style.display = 'none';
    hidePasswordGate();
    // Retry last send if there's a pending message
    const chatInput = document.getElementById('chat-input');
    if (chatInput.dataset.pendingRetry) {
      const msg = chatInput.dataset.pendingRetry;
      delete chatInput.dataset.pendingRetry;
      sendMessage(msg);
    }
  }

  // --- Auto-resize textarea ---------------------------------------------

  function autoResizeInput() {
    const input = document.getElementById('chat-input');
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
  }

  // --- Input keyboard handling -------------------------------------------

  function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // --- Send message ------------------------------------------------------

  function handleSend() {
    if (isLoading) return;
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    autoResizeInput();
    sendMessage(message);
  }

  async function sendMessage(message) {
    if (isLoading) return;

    // Add user message to UI and history
    appendMessageToDOM('user', message);
    chatHistory.push({ role: 'user', text: message });
    saveHistory();

    // Show typing indicator
    isLoading = true;
    setTyping(true);
    setError('');
    setSendEnabled(false);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (password) {
        headers['Authorization'] = 'Bearer ' + password;
      }

      const response = await fetch(WORKER_URL, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          message: message,
          reportContent: reportContent,
          history: chatHistory.slice(0, -1), // exclude current message
        }),
      });

      if (response.status === 401) {
        // Password required or incorrect
        savePassword('');
        const input = document.getElementById('chat-input');
        input.dataset.pendingRetry = message;
        // Remove the user message we just added (will retry after password)
        chatHistory.pop();
        saveHistory();
        removeLastUserMessage();
        showPasswordGate();
        return;
      }

      if (!response.ok) {
        const errData = await response.json().catch(function () { return {}; });
        throw new Error(errData.error || 'Błąd serwera (' + response.status + ')');
      }

      const data = await response.json();
      const reply = data.reply || 'Brak odpowiedzi.';

      // Add AI message
      appendMessageToDOM('ai', reply);
      chatHistory.push({ role: 'model', text: reply });
      saveHistory();
    } catch (err) {
      setError(err.message || 'Nie udało się połączyć z asystentem.');
    } finally {
      isLoading = false;
      setTyping(false);
      setSendEnabled(true);
      scrollToBottom();
    }
  }

  // --- DOM helpers -------------------------------------------------------

  function appendMessageToDOM(type, text) {
    const messagesEl = document.getElementById('chat-messages');
    const typing = document.getElementById('chat-typing');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'chat-msg chat-msg-' + type;

    if (type === 'ai') {
      // Render markdown safely
      msgDiv.appendChild(markdownToNodes(text));
    } else {
      msgDiv.textContent = text;
    }

    // Insert before typing indicator
    messagesEl.insertBefore(msgDiv, typing);
    scrollToBottom();
  }

  function removeLastUserMessage() {
    const messagesEl = document.getElementById('chat-messages');
    const msgs = messagesEl.querySelectorAll('.chat-msg-user');
    if (msgs.length > 0) {
      msgs[msgs.length - 1].remove();
    }
  }

  function setTyping(visible) {
    const typing = document.getElementById('chat-typing');
    typing.setAttribute('data-visible', String(visible));
    if (visible) scrollToBottom();
  }

  function setError(msg) {
    const errorEl = document.getElementById('chat-error');
    errorEl.textContent = msg;
    errorEl.style.display = msg ? 'block' : 'none';
  }

  function setSendEnabled(enabled) {
    const btn = document.getElementById('chat-send-btn');
    btn.disabled = !enabled;
  }

  function scrollToBottom() {
    const messagesEl = document.getElementById('chat-messages');
    requestAnimationFrame(function () {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  // --- Initialize --------------------------------------------------------

  function init() {
    if (WORKER_URL === '%%WORKER_URL%%') {
      // Worker URL not configured — skip widget initialization
      // This prevents the widget from appearing before the Worker is deployed
      return;
    }
    buildWidget();
  }

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
