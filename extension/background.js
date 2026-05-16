// Service Worker

// Called from popup when user clicks "Start Monitoring"
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "START_CAPTURE") {
    startCapture()
      .then(() => sendResponse({status: "started"}))
      .catch((err) => {
        console.error("startCapture error:", err);
        sendResponse({status: "error", error: err.message});
      });
    return true; // Keep port open for async response
  }
  if (msg.action === "STOP_CAPTURE") {
    stopCapture()
      .then(() => sendResponse({status: "stopped"}))
      .catch((err) => {
        console.error("stopCapture error:", err);
        sendResponse({status: "error", error: err.message});
      });
    return true; // Keep port open for async response
  }
  if (msg.action === "CHUNK_SENT") {
    chrome.storage.local.get(["chunkCount"], (data) => {
      chrome.storage.local.set({ chunkCount: (data.chunkCount || 0) + 1 });
    });
  }
  if (msg.action === "FLAG_DETECTED") {
    chrome.storage.local.get(["flagCount"], (data) => {
      chrome.storage.local.set({ flagCount: (data.flagCount || 0) + 1 });
    });
  }
});

async function startCapture() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs || tabs.length === 0) {
    throw new Error("No active tab found");
  }
  const activeTab = tabs[0];

  const streamId = await new Promise(resolve =>
    chrome.tabCapture.getMediaStreamId({ targetTabId: activeTab.id }, resolve)
  );

  if (!streamId) {
    throw new Error("tabCapture failed — is a Meet tab active?");
  }

  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["USER_MEDIA"],
      justification: "Process tab audio for hate speech detection"
    });
  } catch (err) {
    if (!err.message.includes("Only a single offscreen document may be created")) {
      throw err;
    }
  }

  // Pass the stream ID to the offscreen context so IT can get the actual stream
  chrome.runtime.sendMessage({
    action: "INIT_AUDIO",
    streamId: streamId
  });
}

async function stopCapture() {
  try {
    await chrome.offscreen.closeDocument();
  } catch (err) {
    // Ignore errors if document was already closed
  }
}