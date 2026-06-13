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

  function extractMessagesFromNode(root) {
    if (!root || root.nodeType !== Node.ELEMENT_NODE) return;

    // Try each selector to find chat message elements
    for (const selector of CHAT_SELECTORS) {
      let matches = [];
      try {
        if (root.matches && root.matches(selector)) matches.push(root);
        matches = matches.concat(Array.from(root.querySelectorAll(selector)));
      } catch(e) { /* ignore invalid selectors */ }

      for (const el of matches) {
        const text = el.innerText?.trim();
        if (text && text.length >= MIN_TEXT_LENGTH && !processedTexts.has(text)) {
          processedTexts.add(text);
          console.log("[HateSpeech] Chat detected (selector):", text.slice(0, 60));
          classifyText(text);
        }
      }
    }
  }

  // --- Strategy 2: Generic text-node watcher ---
  // Google Meet chat messages typically appear as new <div> subtrees.
  // We watch for any new element that contains visible text and sits inside 
  // a container that looks like a chat panel (side panel, popup, etc.)
  function processGenericNode(node) {
    if (!node || node.nodeType !== Node.ELEMENT_NODE) return;

    // Skip our own overlay elements
    if (node.dataset && node.dataset.hatespeechOverlay) return;

    // Check if this node (or its children) has meaningful text
    const text = node.innerText?.trim();
    if (!text || text.length < MIN_TEXT_LENGTH) return;

    // Skip if it looks like a UI control (buttons, menus, etc.)
    const tag = node.tagName?.toLowerCase();
    if (['script', 'style', 'input', 'textarea', 'button', 'svg', 'img', 'video', 'canvas'].includes(tag)) return;

    // Skip nodes with too many children (likely a layout container, not a message)
    if (node.children && node.children.length > 20) return;

    // Skip text we've already processed
    if (processedTexts.has(text)) return;

    // Check if this node is plausibly inside a chat area
    // We look for ancestor elements that look like side panels or chat containers
    const isChatLike = isInsideChatPanel(node);
    if (isChatLike) {
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
      // Send as "en" by default, the backend will auto-detect Romanized/Devanagari Nepali
      body: JSON.stringify({ text, language: "en" })
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

// OVERLAY UI
function showOverlay(text, label, language, source) {
  // Notify the popup to update its flag count
  chrome.runtime.sendMessage({ action: "FLAG_DETECTED", source, language, label });

  const overlay = document.createElement("div");
  overlay.style.cssText = `
    position: fixed;
    top: 16px; right: 16px;
    background: #c0392b;
    color: white;
    padding: 12px 16px; 
    border-radius: 8px;
    font-family: sans-serif;
    font-size: 14px;
    z-index: 99999;
    max-width: 320px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    animation: slideIn 0.3s ease;
  `;

  overlay.innerHTML = `
    <strong>⚠️ Harmful Content Detected</strong><br/>
    <small>Source: ${source} | Language: ${language} | Label: ${label}</small><br/>
    <em style="font-size:12px">"${text.slice(0, 80)}${text.length > 80 ? "…" : ""}"</em>
    <button style="float:right;background:transparent;border:none;color:white;cursor:pointer;font-size:16px">✕</button>
  `;

  const btn = overlay.querySelector("button");
  if (btn) {
    btn.addEventListener("click", () => overlay.remove());
  }

  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 8000); // auto-dismiss after 8s
}