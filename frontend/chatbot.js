/**
 * AI Chatbot Widget
 * Pure vanilla JS — no dependencies.
 * 
 * To connect a real backend/API, replace the `getBotReply()` function
 * with a fetch() call to your endpoint.
 */

(function () {
  'use strict';

  /* ===========================
     CONFIG
  =========================== */
  const BOT_NAME = 'AI Assistant';
  const TYPING_DELAY_MIN = 700;  // ms
  const TYPING_DELAY_MAX = 1600; // ms

  // Demo bot responses — replace getBotReply() with real API calls.
  const BOT_RESPONSES = [
    "That's a great question! I'm here to help you with anything you need. Could you tell me a bit more about what you're looking for?",
    "I understand completely. Let me look into that for you and provide the best possible guidance.",
    "Absolutely! Here's what I can help you with: onboarding, billing, technical support, and general product questions. What would you like to explore?",
    "Thanks for reaching out! Our team is dedicated to making your experience seamless. I can assist you right now — just let me know what you need.",
    "Great news — I can help with that directly. Would you like a step-by-step walkthrough or a quick summary?",
    "I've noted your request. For more complex issues, I can also connect you with a human specialist. Would you like that?",
    "That's something I specialize in! Let me walk you through the process clearly and concisely.",
    "Happy to assist! This is actually one of the most common questions I get — here's the clearest answer I can give you.",
  ];

  /* ===========================
     DOM REFS
  =========================== */
  const fab        = document.getElementById('chatFab');
  const popup      = document.getElementById('chatPopup');
  const closeBtn   = document.getElementById('closeBtn');
  const minimizeBtn = document.getElementById('minimizeBtn');
  const messagesEl = document.getElementById('chatMessages');
  const inputEl    = document.getElementById('chatInput');
  const sendBtn    = document.getElementById('sendBtn');
  const charCount  = document.getElementById('charCount');
  const quickRepliesEl = document.getElementById('quickReplies');

  /* ===========================
     STATE
  =========================== */
  let isOpen     = false;
  let isTyping   = false;
  let msgCount   = 0;

  /* ===========================
     HELPERS
  =========================== */
  function getTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function randomBetween(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function scrollToBottom(smooth = true) {
    messagesEl.scrollTo({
      top: messagesEl.scrollHeight,
      behavior: smooth ? 'smooth' : 'instant'
    });
  }

  /**
   * Build an avatar element.
   * @param {'bot'|'user'} type
   */
  function makeAvatar(type) {
    const el = document.createElement('div');
    el.className = 'msg-avatar';
    if (type === 'bot') {
      el.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="8" width="18" height="13" rx="3" fill="url(#av${msgCount})"/>
        <circle cx="9" cy="14" r="2" fill="white" opacity=".9"/>
        <circle cx="15" cy="14" r="2" fill="white" opacity=".9"/>
        <rect x="8" y="4" width="8" height="5" rx="2" fill="url(#av${msgCount})"/>
        <defs><linearGradient id="av${msgCount}" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#06b6d4"/>
        </linearGradient></defs>
      </svg>`;
    } else {
      el.innerHTML = '👤';
      el.style.color = 'white';
    }
    return el;
  }

  /* ===========================
     RENDER MESSAGES
  =========================== */
  /**
   * Append a message bubble to the chat.
   * @param {string} text
   * @param {'bot'|'user'} sender
   * @param {boolean} animate
   */
  function appendMessage(text, sender = 'bot', animate = true) {
    msgCount++;

    const row = document.createElement('div');
    row.className = `message-row ${sender}`;
    if (!animate) row.style.animation = 'none';

    const avatar = makeAvatar(sender);

    const group = document.createElement('div');
    group.className = 'bubble-group';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;

    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = getTime();

    group.appendChild(bubble);
    group.appendChild(time);

    if (sender === 'bot') {
      row.appendChild(avatar);
      row.appendChild(group);
    } else {
      row.appendChild(group);
      row.appendChild(avatar);
    }

    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  /**
   * Show the typing indicator bubble.
   */
  function showTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'message-row bot';
    row.id = 'typingRow';

    const avatar = makeAvatar('bot');

    const group = document.createElement('div');
    group.className = 'bubble-group';

    const typing = document.createElement('div');
    typing.className = 'typing-bubble';
    for (let i = 0; i < 3; i++) {
      const dot = document.createElement('span');
      dot.className = 'typing-dot';
      typing.appendChild(dot);
    }

    group.appendChild(typing);
    row.appendChild(avatar);
    row.appendChild(group);

    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const existing = document.getElementById('typingRow');
    if (existing) existing.remove();
  }

  /**
   * Simulated bot reply — replace with real API call.
   * @param {string} userMessage
   */
async function getBotReply(userMessage) {

  try {

    const response = await fetch("http://127.0.0.1:8000/api/v1/chat", {

      method: "POST",

      headers: {
        "Content-Type": "application/json"
      },

      body: JSON.stringify({
        message: userMessage
      })

    });

    const data = await response.json();

    return data.reply;

  } catch (error) {

    console.error("Backend Error:", error);

    return "Unable to connect to AI server.";

  }

}
  /* ===========================
     SEND FLOW
  =========================== */
  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || isTyping) return;

    // Clear input
    inputEl.value = '';
    updateInputState();
    autoResizeInput();

    // Hide quick replies after first interaction
    quickRepliesEl.style.display = 'none';

    // Append user message
    appendMessage(trimmed, 'user');

    // Show typing indicator
    isTyping = true;
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
      const reply = await getBotReply(trimmed);
      removeTypingIndicator();
      appendMessage(reply, 'bot');
    } catch (err) {
      removeTypingIndicator();
      appendMessage("I'm sorry, something went wrong. Please try again in a moment.", 'bot');
      console.error('[Chatbot] Error fetching reply:', err);
    } finally {
      isTyping = false;
      updateInputState();
    }
  }

  /* ===========================
     INPUT STATE
  =========================== */
  function updateInputState() {
    const len = inputEl.value.length;
    const hasText = inputEl.value.trim().length > 0;

    sendBtn.disabled = !hasText || isTyping;

    // Char counter
    charCount.textContent = `${len}/500`;
    charCount.classList.toggle('near-limit', len >= 400 && len < 480);
    charCount.classList.toggle('at-limit', len >= 480);
  }

  function autoResizeInput() {
    inputEl.style.height = 'auto';
    const max = 110;
    inputEl.style.height = Math.min(inputEl.scrollHeight, max) + 'px';
  }

  /* ===========================
     POPUP OPEN / CLOSE
  =========================== */
  function openChat() {
    isOpen = true;
    popup.classList.add('is-open');
    fab.classList.add('is-open');
    fab.setAttribute('aria-expanded', 'true');
    setTimeout(() => inputEl.focus(), 320);
  }

  function closeChat() {
    isOpen = false;
    popup.classList.remove('is-open');
    fab.classList.remove('is-open');
    fab.setAttribute('aria-expanded', 'false');
  }

  function toggleChat() {
    isOpen ? closeChat() : openChat();
  }

  /* ===========================
     WELCOME MESSAGE
  =========================== */
  function renderWelcome() {
    // Date divider
    const divider = document.createElement('div');
    divider.className = 'date-divider';
    divider.textContent = 'Today';
    messagesEl.appendChild(divider);

    // Welcome bubble (no animation flash on load)
    appendMessage(
      `Hi there! 👋 I'm ${BOT_NAME}. I'm here to help you with any questions or support you need. How can I assist you today?`,
      'bot',
      false
    );
  }

  /* ===========================
     QUICK REPLY CHIPS
  =========================== */
  function bindChips() {
    quickRepliesEl.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const msg = chip.dataset.msg;
        if (msg) sendMessage(msg);
      });
    });
  }

  /* ===========================
     EVENT LISTENERS
  =========================== */
  fab.addEventListener('click', toggleChat);
  closeBtn.addEventListener('click', closeChat);
  minimizeBtn.addEventListener('click', closeChat);

  sendBtn.addEventListener('click', () => {
    sendMessage(inputEl.value);
  });

  inputEl.addEventListener('input', () => {
    updateInputState();
    autoResizeInput();
  });

  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) sendMessage(inputEl.value);
    }
  });

  // Close on Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isOpen) closeChat();
  });

  // Close when clicking outside popup
  document.addEventListener('click', e => {
    if (isOpen && !popup.contains(e.target) && !fab.contains(e.target)) {
      closeChat();
    }
  });

  /* ===========================
     INIT
  =========================== */
  function init() {
    renderWelcome();
    bindChips();
    updateInputState();
  }

  init();

})();

body: JSON.stringify({
  message: userMessage
})