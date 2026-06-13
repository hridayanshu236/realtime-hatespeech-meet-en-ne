// Service Worker

// Track which tab we're capturing so we can relay alerts to it
let captureTabId = null;

// Called from popup when user clicks "Start Monitoring"
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "START_CAPTURE") {
    startCapture()
      .then(() => sendResponse({ status: "started" }))
      .catch((err) => {
        console.error("startCapture error:", err);
        sendResponse({ status: "error", error: err.message });
      });
    return true; // Keep port open for async response
  }
  if (msg.action === "STOP_CAPTURE") {
    stopCapture()
      .then(() => sendResponse({ status: "stopped" }))
      .catch((err) => {
        console.error("stopCapture error:", err);
        sendResponse({ status: "error", error: err.message });
      });
    return true; // Keep port open for async response
  }
  if (msg.action === "CHUNK_SENT") {
    chrome.storage.local.get(["chunkCount"], (data) => {
      chrome.storage.local.set({ chunkCount: (data.chunkCount || 0) + 1 });
    });
  }
  if (msg.action === "FLAG_DETECTED") {
    chrome.storage.local.get(["flagCount", "logEntries"], (data) => {
      const newCount = (data.flagCount || 0) + 1;
      const entries = data.logEntries || [];
      const src  = msg.source   || "unknown";
      const lang = msg.language || "?";
      const lbl  = msg.label    || "harmful";
      
      entries.push({
        type: "warn",
        message: `[${src}][${lang}] ${lbl}`,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      });
      if (entries.length > 50) entries.splice(0, entries.length - 50);
      
      chrome.storage.local.set({ flagCount: newCount, logEntries: entries });
    });
  }

  // Relay SHOW_ALERT from offscreen document to the Meet content script.
  // chrome.runtime.sendMessage does NOT deliver to content scripts —
  // we must use chrome.tabs.sendMessage to reach them.
  if (msg.action === "SHOW_ALERT" || msg.action === "PIPELINE_LOG") {
    if (captureTabId) {
      chrome.tabs.sendMessage(captureTabId, msg, () => {
        // Suppress "Could not establish connection" if content script isn't loaded
        void chrome.runtime.lastError;
      });
    }
  }
});

async function startCapture() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs || tabs.length === 0) {
    throw new Error("No active tab found");
  }
  const activeTab = tabs[0];
  captureTabId = activeTab.id;

  const streamId = await new Promise(resolve =>
    chrome.tabCapture.getMediaStreamId({ targetTabId: activeTab.id }, resolve)
  );

  if (!streamId) {
    throw new Error("tabCapture failed — is a Meet tab active?");
  }

  // Close any existing offscreen document first
  try {
    await chrome.offscreen.closeDocument();
  } catch (err) {
    // Ignore — no document to close
  }

  // Create offscreen document with streamId in the URL so it can initialize
  // immediately on load — no race condition with message passing.
  await chrome.offscreen.createDocument({
    url: `offscreen.html?streamId=${encodeURIComponent(streamId)}`,
    reasons: ["USER_MEDIA"],
    justification: "Process tab audio for hate speech detection"
  });
}

async function stopCapture() {
  captureTabId = null;
  try {
    await chrome.offscreen.closeDocument();
  } catch (err) {
    // Ignore errors if document was already closed
  }
}