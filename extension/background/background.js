importScripts("../shared/config.js");

let capturing = false;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === ACTIONS.START_CAPTURE) {
    startCapture(sendResponse);
    return true;
  }
  if (msg.action === ACTIONS.STOP_CAPTURE) {
    stopCapture(sendResponse);
    return true;
  }

  if (
    msg.action === ACTIONS.FLAG_DETECTED ||
    msg.action === ACTIONS.CHUNK_SENT    ||
    msg.action === ACTIONS.BACKEND_STATUS
  ) {
    broadcastToPopup(msg);
  }

  if (msg.action === ACTIONS.SHOW_ALERT) {
    forwardToContentScript(msg);
  }

  if (msg.action === ACTIONS.FLAG_DETECTED && sender.tab) {
    broadcastToPopup(msg);
  }
});

async function startCapture(sendResponse) {
  if (capturing) {
    sendResponse({ ok: false, reason: "Already capturing." });
    return;
  }

  const healthy = await checkBackendHealth();
  if (!healthy) {
    sendResponse({ ok: false, reason: "Backend is not reachable. Is the server running on port 8000?" });
    return;
  }

  let streamId;
  try {
    streamId = await new Promise((resolve, reject) => {
      chrome.tabCapture.getMediaStreamId({}, (id) => {
        if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
        else resolve(id);
      });
    });
  } catch (err) {
    const reason = "tabCapture failed: " + err.message;
    broadcastToPopup({ action: ACTIONS.CAPTURE_ERROR, reason });
    sendResponse({ ok: false, reason });
    return;
  }

  try {
    const exists = await chrome.offscreen.hasDocument();
    if (!exists) {
      await chrome.offscreen.createDocument({
        url:           chrome.runtime.getURL("offscreen/offscreen.html"),
        reasons:       ["USER_MEDIA"],
        justification: "Process tab audio for hate speech detection",
      });
    }
  } catch (err) {
    const reason = "Offscreen init failed: " + err.message;
    broadcastToPopup({ action: ACTIONS.CAPTURE_ERROR, reason });
    sendResponse({ ok: false, reason });
    return;
  }

  chrome.runtime.sendMessage({ action: ACTIONS.INIT_AUDIO, streamId });

  capturing = true;
  sendResponse({ ok: true });
}

async function stopCapture(sendResponse) {
  if (!capturing) {
    sendResponse({ ok: false, reason: "Not capturing." });
    return;
  }

  try {
    await chrome.runtime.sendMessage({ action: ACTIONS.STOP_AUDIO });
  } catch (_) {
    // offscreen may have already closed
  }

  try {
    const exists = await chrome.offscreen.hasDocument();
    if (exists) await chrome.offscreen.closeDocument();
  } catch (err) {
    console.warn("[background] Could not close offscreen document:", err.message);
  }

  capturing = false;
  sendResponse({ ok: true });
}

async function checkBackendHealth() {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), CONFIG.HEALTH_TIMEOUT);

    const res = await fetch(`${CONFIG.BACKEND_URL}/health`, {
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) return false;

    const data = await res.json();

    // Broadcast health info to popup so it can show model status
    broadcastToPopup({
      action:  ACTIONS.BACKEND_STATUS,
      status:  data.status,          // "ok" | "degraded"
      device:  data.device,
      whisper: data.whisper_loaded,
      xlmr:    data.xlmr_loaded,
    });

    return data.status === "ok";
  } catch (_) {
    return false;
  }
}

function broadcastToPopup(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {
    // popup may be closed; ignore
  });
}

async function forwardToContentScript(msg) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;
  chrome.tabs.sendMessage(tab.id, msg).catch(() => {});
}
