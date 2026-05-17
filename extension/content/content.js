const BACKEND_URL = "http://localhost:8000";

const CHAT_SELECTORS = [
  '[data-message-id]',
  '[aria-label="Chat with everyone"]',
  '[aria-label="In-call messages"]',
  'div[jscontroller][data-is-muted]',
];

let chatObserver = null;
let observedRoot = null;

function findChatRoot() {
  for (const sel of CHAT_SELECTORS) {
    const el = document.querySelector(sel);
    if (el) return sel === '[data-message-id]' ? el.parentElement : el;
  }
  return null;
}

function startChatObserver() {
  const root = findChatRoot();
  if (!root) {
    setTimeout(startChatObserver, 2000);
    return;
  }
  if (root === observedRoot) return;
  observedRoot = root;

  chatObserver?.disconnect();
  chatObserver = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const text = (node.dataset?.text || node.innerText || "").trim();
        if (text) classifyText(text);
      }
    }
    const newRoot = findChatRoot();
    if (newRoot && newRoot !== observedRoot) startChatObserver();
  });

  chatObserver.observe(root, { childList: true, subtree: true });
}

startChatObserver();

async function classifyText(text) {
  try {
    const res = await fetch(`${BACKEND_URL}/classify`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ text, language: "unknown" }),
    });

    if (!res.ok) return;

    const { flagged, label, language, confidence } = await res.json();

    if (flagged) {
      showOverlay(text, label, language, "chat", confidence);

      // Notify the popup so it bumps the flag counter and logs the event
      chrome.runtime.sendMessage({
        action:     ACTIONS.FLAG_DETECTED,
        source:     "chat",
        language:   language ?? "unknown",
        label:      label    ?? "harmful",
        confidence: confidence ?? null,
      });
    }
  } catch (err) {
    console.warn("[content] /classify error:", err.message);
  }
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === ACTIONS.SHOW_ALERT) {
    showOverlay(msg.transcript, msg.label, msg.language, msg.source ?? "audio", msg.confidence);
  }
});

const OVERLAY_BASE_STYLE = `
  position: fixed;
  top: 16px;
  right: 16px;
  background: #1a0608;
  border: 1.5px solid #be46ff;
  color: #f5d0d3;
  padding: 12px 14px;
  border-radius: 10px;
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  z-index: 2147483647;
  max-width: 340px;
  box-shadow: 0 6px 24px rgba(255,70,85,0.25);
  animation: __hsd_slide 0.25s ease forwards;
`;

// Inject slide-in keyframe once
(function injectStyles() {
  if (document.getElementById("__hsd_styles")) return;
  const style = document.createElement("style");
  style.id = "__hsd_styles";
  style.textContent = `
    @keyframes __hsd_slide {
      from { opacity:0; transform:translateX(20px); }
      to   { opacity:1; transform:translateX(0);    }
    }
  `;
  document.head.appendChild(style);
})();

function showOverlay(text, label, language, source, confidence) {
  const overlay = document.createElement("div");
  overlay.style.cssText = OVERLAY_BASE_STYLE;

  // Header
  const header = document.createElement("div");
  header.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;";

  const title = document.createElement("strong");
  title.style.color = "#ff4655";
  title.textContent = "⚠️ Harmful Content Detected";

  const closeBtn = document.createElement("button");
  closeBtn.textContent = "✕";
  closeBtn.style.cssText = "background:none;border:none;color:#f5d0d3;cursor:pointer;font-size:15px;padding:0 0 0 10px;line-height:1;";
  closeBtn.addEventListener("click", () => overlay.remove());

  header.appendChild(title);
  header.appendChild(closeBtn);

  // Confidence bar
  const pct = confidence != null ? Math.round(confidence * 100) : null;

  // Meta
  const meta = document.createElement("div");
  meta.style.cssText = "font-size:11px;color:#a07880;margin-bottom:5px;";
  meta.textContent = [
    `Source: ${source}`,
    `Language: ${language ?? "?"}`,
    `Label: ${label ?? "harmful"}`,
    pct != null ? `Confidence: ${pct}%` : null,
  ].filter(Boolean).join("  ·  ");

  // Snippet
  const snippet = document.createElement("div");
  snippet.style.cssText = "font-size:12px;font-style:italic;color:#c9a0a5;word-break:break-word;";
  const preview = text && text.length > 100 ? text.slice(0, 100) + "…" : (text ?? "");
  snippet.textContent = `"${preview}"`;

  overlay.appendChild(header);
  overlay.appendChild(meta);
  overlay.appendChild(snippet);
  document.body.appendChild(overlay);

  setTimeout(() => overlay.remove(), 8000);
}
