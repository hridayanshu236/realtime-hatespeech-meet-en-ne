// content.js — injected into meet.google.com

// CHAT WATCHER
const BACKEND_URL = "http://localhost:8000";

function observeChat() {
  // Google Meet chat messages land inside this aria role
  const chatContainer = document.querySelector('[aria-label="Chat with everyone"]')
                     || document.querySelector('[data-message-id]')?.parentElement;

  if (!chatContainer) {
    // Meet's DOM loads lazily — retry
    setTimeout(observeChat, 2000);
    return;
  }

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const text = node.innerText?.trim();
        if (text) classifyText(text);
      }
    }
  });

  observer.observe(chatContainer, { childList: true, subtree: true });
}

async function classifyText(text) {
  try {
    const res = await fetch(`${BACKEND_URL}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const { is_harmful, label, language } = await res.json();
    if (is_harmful) showOverlay(text, label, language, "chat");
  } catch (err) {
    console.error("Classify error:", err);
  }
}

observeChat();

// RECEIVE AUDIO ALERTS FROM BACKGROUND
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "SHOW_ALERT") {
    showOverlay(msg.transcript, msg.label, msg.language, "audio");
  }
});

// OVERLAY UI
function showOverlay(text, label, language, source) {
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
    <button onclick="this.parentElement.remove()" 
      style="float:right;background:transparent;border:none;color:white;cursor:pointer;font-size:16px">✕</button>
  `;

  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 8000); // auto-dismiss after 8s
}