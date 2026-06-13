// Injected into meet.google.com
console.log("[HateSpeech] Content script loaded on", location.href);

// CHAT WATCHER
const BACKEND_URL = "http://localhost:8000";

// Store all text we've already sent to the backend, to avoid duplicates
const processedTexts = new Set();

// Minimum length for text to be worth classifying (skip tiny UI labels)
const MIN_TEXT_LENGTH = 3;

function observeChat() {
  console.log("[HateSpeech] Chat observer starting...");

  // --- Strategy 1: Attribute-based (try multiple known Meet selectors) ---
  const CHAT_SELECTORS = [
    '[data-message-id]',           // Classic Meet
    '[data-message-text]',         // Some Meet versions
    '[data-messageid]',            // Alternate casing
    '[jsname="dTKtvb"]',           // Known chat message jsname
    '[jsname="YSxPC"]',            // Another known variant
    '[data-sender-id]',            // Messages with sender info
  ];

  function cleanMeetText(rawText) {
    if (!rawText) return "";
    let text = rawText;
    // Strip common Google Meet UI text that gets caught in innerText
    text = text.replace(/keep\s*Pin Message/gi, "");
    text = text.replace(/Pin Message/gi, "");
    text = text.replace(/\nkeep\n/gi, "\n");
    // Strip sender timestamps (e.g. "You\n10:05 AM\n")
    text = text.replace(/.*?\n\d{1,2}:\d{2}\s*(AM|PM)\n/i, "");
    return text.trim();
  }

  function extractMessagesFromNode(root) {
    if (!root || root.nodeType !== Node.ELEMENT_NODE) return;

    for (const selector of CHAT_SELECTORS) {
      let matches = [];
      try {
        if (root.matches && root.matches(selector)) matches.push(root);
        matches = matches.concat(Array.from(root.querySelectorAll(selector)));
      } catch(e) { }

      for (const el of matches) {
        const text = cleanMeetText(el.innerText);
        if (text && text.length >= MIN_TEXT_LENGTH && !processedTexts.has(text)) {
          processedTexts.add(text);
          console.log("[HateSpeech] Chat detected (selector):", text.slice(0, 60));
          classifyText(text);
        }
      }
    }
  }

  function processGenericNode(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return;
    if (node.dataset && node.dataset.hatespeechOverlay) return;

    const text = cleanMeetText(node.innerText);
    if (!text || text.length < MIN_TEXT_LENGTH) return;

    const tag = node.tagName?.toLowerCase();
    if (['script', 'style', 'input', 'textarea', 'button', 'svg', 'img', 'video', 'canvas'].includes(tag)) return;
    if (node.children && node.children.length > 20) return;
    if (processedTexts.has(text)) return;

    if (isInsideChatPanel(node)) {
      processedTexts.add(text);
      console.log("[HateSpeech] Chat detected (generic):", text.slice(0, 60));
      classifyText(text);
    }
  }

  function isInsideChatPanel(node) {
    // Walk up the DOM tree looking for signals that this is a chat panel
    let el = node;
    let depth = 0;
    while (el && depth < 15) {
      // Check aria roles that indicate chat/messaging
      const role = el.getAttribute?.('role');
      const ariaLabel = el.getAttribute?.('aria-label')?.toLowerCase() || '';
      
      if (role === 'log' || role === 'list' || role === 'complementary') return true;
      if (ariaLabel.includes('chat') || ariaLabel.includes('message') || ariaLabel.includes('in-call')) return true;
      
      // Check common data attributes
      if (el.hasAttribute?.('data-message-id') || el.hasAttribute?.('data-messageid')) return true;
      
      // Check if it's a side panel (Meet uses these classes/structures)
      const className = el.className?.toLowerCase?.() || '';
      if (className.includes('chat') || className.includes('message')) return true;
      
      el = el.parentElement;
      depth++;
    }
    return false;
  }

  // --- Combined MutationObserver ---
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (!m.addedNodes) continue;
      for (const node of m.addedNodes) {
        extractMessagesFromNode(node);
        processGenericNode(node);
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // --- Polling fallback: scan every 3 seconds ---
  // This catches messages that were rendered without triggering a mutation
  setInterval(() => {
    extractMessagesFromNode(document.body);
  }, 3000);

  console.log("[HateSpeech] Chat observer active (selectors + generic + polling).");
}

async function classifyText(text) {
  console.log("[HateSpeech] Sending to /classify:", text.slice(0, 60));
  try {
    const res = await fetch(`${BACKEND_URL}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    console.log("[HateSpeech] /classify response:", data);
    if (data.flagged) showOverlay(text, data.label, data.language, "chat");
  } catch (err) {
    console.error("[HateSpeech] Classify error:", err);
  }
}

observeChat();

// RECEIVE AUDIO ALERTS FROM BACKGROUND
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "SHOW_ALERT") {
    showOverlay(msg.transcript, msg.label, msg.language, "audio");
  }
  if (msg.action === "PIPELINE_LOG") {
    console.log("[HateSpeech Audio] /pipeline response:", msg.data);
  }
});

// OVERLAY UI (Premium Toast Notification System)
let toastContainer = null;

function initToastContainer() {
  if (toastContainer) return;

  // Create a style element for the toast animations and aesthetics
  const style = document.createElement("style");
  style.textContent = `
    #hs-toast-container {
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 2147483647; /* Max z-index to stay above Google Meet UI */
      display: flex;
      flex-direction: column;
      gap: 12px;
      pointer-events: none; /* Let clicks pass through empty space */
    }

    .hs-toast {
      pointer-events: auto;
      width: 340px;
      background: rgba(20, 20, 25, 0.85);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 60, 60, 0.3);
      border-left: 4px solid #ef4444;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
      color: #f8fafc;
      font-family: 'Segoe UI', Roboto, system-ui, sans-serif;
      overflow: hidden;
      position: relative;
      animation: hs-slideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      opacity: 0;
      transform: translateX(100%);
    }

    .hs-toast.hs-hiding {
      animation: hs-slideOut 0.3s ease-in forwards;
    }

    .hs-toast-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px 8px;
    }

    .hs-toast-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      font-size: 14px;
      color: #ef4444;
      margin: 0;
    }
    
    .hs-toast-title svg {
      width: 18px;
      height: 18px;
    }

    .hs-toast-close {
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 4px;
      border-radius: 4px;
      transition: all 0.2s;
    }

    .hs-toast-close:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #f1f5f9;
    }

    .hs-toast-body {
      padding: 0 16px 16px;
    }

    .hs-badges {
      display: flex;
      gap: 6px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }

    .hs-badge {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.05);
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 500;
      color: #cbd5e1;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .hs-quote {
      margin: 0;
      padding: 8px 12px;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 6px;
      font-size: 13px;
      line-height: 1.5;
      color: #e2e8f0;
      font-style: italic;
      border-left: 2px solid #64748b;
    }

    .hs-progress {
      position: absolute;
      bottom: 0;
      left: 0;
      height: 3px;
      background: #ef4444;
      width: 100%;
      transform-origin: left;
      animation: hs-shrink 8s linear forwards;
    }

    @keyframes hs-slideIn {
      from { opacity: 0; transform: translateX(100%); }
      to { opacity: 1; transform: translateX(0); }
    }

    @keyframes hs-slideOut {
      from { opacity: 1; transform: translateX(0); }
      to { opacity: 0; transform: translateX(100%); }
    }

    @keyframes hs-shrink {
      from { transform: scaleX(1); }
      to { transform: scaleX(0); }
    }
  `;
  document.head.appendChild(style);

  toastContainer = document.createElement("div");
  toastContainer.id = "hs-toast-container";
  document.body.appendChild(toastContainer);
}

function showOverlay(text, label, language, source) {
  // Notify the popup to update its flag count
  chrome.runtime.sendMessage({ action: "FLAG_DETECTED", source, language, label });

  initToastContainer();

  const toast = document.createElement("div");
  toast.className = "hs-toast";
  
  // Create safe display text
  const safeText = text.length > 120 ? text.slice(0, 120) + "..." : text;

  // SVG Icons
  const warningIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
  const closeIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

  toast.innerHTML = `
    <div class="hs-toast-header">
      <h4 class="hs-toast-title">${warningIcon} Harmful Content</h4>
      <button class="hs-toast-close" aria-label="Close">${closeIcon}</button>
    </div>
    <div class="hs-toast-body">
      <div class="hs-badges">
        <span class="hs-badge">${source}</span>
        <span class="hs-badge">${language}</span>
        <span class="hs-badge">${label.replace(/_/g, ' ')}</span>
      </div>
      <blockquote class="hs-quote">"${safeText}"</blockquote>
    </div>
    <div class="hs-progress"></div>
  `;

  const btn = toast.querySelector(".hs-toast-close");
  let removed = false;

  const removeToast = () => {
    if (removed) return;
    removed = true;
    toast.classList.add("hs-hiding");
    // Wait for the exit animation to finish before removing from DOM
    setTimeout(() => {
      toast.remove();
    }, 300);
  };

  if (btn) {
    btn.addEventListener("click", removeToast);
  }

  toastContainer.appendChild(toast);
  setTimeout(removeToast, 8000); // auto-dismiss after 8s
}