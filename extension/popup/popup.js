// State
let isMonitoring = false;
let chunkCount   = 0;
let flagCount    = 0;
let isOnMeet     = false;

// DOM refs
const mainBtn     = document.getElementById("mainBtn");
const btnLabel    = document.getElementById("btnLabel");
const statusDot   = document.getElementById("statusDot");
const statusValue = document.getElementById("statusValue");
const chunkEl     = document.getElementById("chunkCount");
const flagEl      = document.getElementById("flagCount");
const logBox      = document.getElementById("logBox");
const logEmpty    = document.getElementById("logEmpty");
const clearLogBtn = document.getElementById("clearLog");
const meetDot     = document.getElementById("meetDot");
const meetLabel   = document.getElementById("meetLabel");

// On popup open, restore state from chrome.storage and check active tab
document.addEventListener("DOMContentLoaded", () => {
  restoreState();
  checkIfOnMeet();
});

// Restore persisted state (counts, monitoring flag, log entries)
function restoreState() {
  chrome.storage.local.get(
    ["isMonitoring", "chunkCount", "flagCount", "logEntries"],
    (data) => {
      isMonitoring = data.isMonitoring ?? false;
      chunkCount   = data.chunkCount   ?? 0;
      flagCount    = data.flagCount    ?? 0;

      chunkEl.textContent = chunkCount;
      flagEl.textContent  = flagCount;

      // Restore log
      if (data.logEntries?.length) {
        logEmpty.style.display = "none";
        data.logEntries.forEach(entry => renderLogEntry(entry, false));
      }

      // Restore button/status UI
      if (isMonitoring) setMonitoringUI(true);
    }
  );
}

// Check whether the currently active tab is a Google Meet session
function checkIfOnMeet() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url = tabs[0]?.url ?? "";
    isOnMeet = url.includes("meet.google.com");

    meetDot.classList.toggle("on-meet", isOnMeet);
    meetLabel.classList.toggle("on-meet", isOnMeet);
    meetLabel.textContent = isOnMeet ? "On Meet" : "Not on Meet";

    // Only enable the button when on a Meet tab
    mainBtn.disabled = !isOnMeet;

    if (!isOnMeet) {
      addLog("warn", "No active Meet tab detected.");
    }
  });
}

// Button handler
mainBtn.addEventListener("click", () => {
  if (!isMonitoring) {
    startMonitoring();
  } else {
    stopMonitoring();
  }
});

function startMonitoring() {
  chrome.runtime.sendMessage({ action: "START_CAPTURE" }, (response) => {
    if (chrome.runtime.lastError) {
      addLog("warn", "Failed to start: " + chrome.runtime.lastError.message);
      return;
    }
    if (response && response.status === "error") {
      addLog("warn", "Capture Error: " + response.error);
      return;
    }
    isMonitoring = true;
    chrome.storage.local.set({ isMonitoring: true });
    setMonitoringUI(true);
    addLog("info", "Monitoring started.");
  });
}

function stopMonitoring() {
  chrome.runtime.sendMessage({ action: "STOP_CAPTURE" }, (response) => {
    if (chrome.runtime.lastError) {
      addLog("warn", "Failed to stop: " + chrome.runtime.lastError.message);
      return;
    }
    if (response && response.status === "error") {
      addLog("warn", "Stop Error: " + response.error);
    }
    isMonitoring = false;
    chrome.storage.local.set({ isMonitoring: false });
    setMonitoringUI(false);
    addLog("info", "Monitoring stopped.");
  });
}

// UI state helpers
function setMonitoringUI(active) {
  if (active) {
    mainBtn.className    = "main-btn stop";
    btnLabel.textContent = "Stop Monitoring";
    statusDot.classList.add("active");
    statusValue.textContent = "Active";
    statusValue.className   = "value active";
  } else {
    mainBtn.className    = "main-btn start";
    btnLabel.textContent = "Start Monitoring";
    statusDot.classList.remove("active");
    statusValue.textContent = "Inactive";
    statusValue.className   = "value inactive";
  }
}

// Listen for messages from background.
// background.js can push CHUNK_SENT and FLAG events to update the popup live
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "CHUNK_SENT") {
    chunkCount++;
    chunkEl.textContent = chunkCount;
    chrome.storage.local.set({ chunkCount });
  }

  if (msg.action === "FLAG_DETECTED") {
    flagCount++;
    flagEl.textContent = flagCount;
    chrome.storage.local.set({ flagCount });
    const src  = msg.source   ?? "unknown";
    const lang = msg.language ?? "?";
    const lbl  = msg.label    ?? "harmful";
    addLog("warn", `[${src}][${lang}] ${lbl}`);
  }

  if (msg.action === "CAPTURE_ERROR") {
    addLog("warn", "Capture error: " + (msg.reason ?? "unknown"));
    isMonitoring = false;
    setMonitoringUI(false);
    chrome.storage.local.set({ isMonitoring: false });
  }
});

// Log helpers
// Keeps a max of 50 entries in storage to avoid unbounded growth
const MAX_LOG = 50;

function addLog(type, message) {
  const entry = {
    type,
    message,
    time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  };

  // Persist
  chrome.storage.local.get(["logEntries"], (data) => {
    const entries = data.logEntries ?? [];
    entries.push(entry);
    if (entries.length > MAX_LOG) entries.splice(0, entries.length - MAX_LOG);
    chrome.storage.local.set({ logEntries: entries });
  });

  // Render immediately in the open popup
  logEmpty.style.display = "none";
  renderLogEntry(entry, true);
}

function renderLogEntry(entry, scrollToBottom) {
  const el = document.createElement("div");
  el.className = `log-entry ${entry.type}`;
  el.innerHTML = `
    <span class="log-time">${entry.time}</span>
    <span class="log-msg">${entry.message}</span>
  `;
  logBox.appendChild(el);
  if (scrollToBottom) logBox.scrollTop = logBox.scrollHeight;
}

// Clear log
clearLogBtn.addEventListener("click", () => {
  logBox.innerHTML = "";
  logEmpty.style.display = "";
  logBox.appendChild(logEmpty);
  chrome.storage.local.set({ logEntries: [] });
});