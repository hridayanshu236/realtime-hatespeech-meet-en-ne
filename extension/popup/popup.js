import { StatusBar }     from "./components/StatusBar.js";
import { MainButton }    from "./components/MainButton.js";
import { StatsPanel }    from "./components/StatsPanel.js";
import { EventLog }      from "./components/EventLog.js";
import { MeetIndicator } from "./components/MeetIndicator.js";
import { BackendBadge }  from "./components/BackendBadge.js";

//State

let isMonitoring = false;
let chunkCount   = 0;
let flagCount    = 0;

//Component Instances

const statusBar = StatusBar({
  dotEl:   document.getElementById("statusDot"),
  valueEl: document.getElementById("statusValue"),
});

const mainBtn = MainButton({
  btnEl:   document.getElementById("mainBtn"),
  labelEl: document.getElementById("btnLabel"),
});

const stats = StatsPanel({
  chunkEl: document.getElementById("chunkCount"),
  flagEl:  document.getElementById("flagCount"),
});

const log = EventLog({
  logBoxEl:   document.getElementById("logBox"),
  logEmptyEl: document.getElementById("logEmpty"),
  clearBtnEl: document.getElementById("clearLog"),
});

const meetIndicator = MeetIndicator({
  dotEl:   document.getElementById("meetDot"),
  labelEl: document.getElementById("meetLabel"),
});

const backendBadge = BackendBadge({
  badgeEl:  document.getElementById("backendBadge"),
  deviceEl: document.getElementById("backendDevice"),
});

//Boot 

document.addEventListener("DOMContentLoaded", () => {
  restoreState();
  checkIfOnMeet();
});

function restoreState() {
  chrome.storage.local.get(
    ["isMonitoring", "chunkCount", "flagCount", "logEntries", "backendStatus"],
    (data) => {
      isMonitoring = data.isMonitoring ?? false;
      chunkCount   = data.chunkCount   ?? 0;
      flagCount    = data.flagCount    ?? 0;

      stats.setChunks(chunkCount);
      stats.setFlags(flagCount);
      log.restore(data.logEntries ?? []);

      if (data.backendStatus) {
        backendBadge.set(data.backendStatus.status, data.backendStatus.device);
      }

      if (isMonitoring) applyMonitoringUI(true);
    }
  );
}

function checkIfOnMeet() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url    = tabs[0]?.url ?? "";
    const onMeet = url.includes("meet.google.com");

    meetIndicator.setOnMeet(onMeet);
    mainBtn.setEnabled(onMeet);

    if (!onMeet) log.addEntry("warn", "No active Meet tab detected.");
  });
}

mainBtn.onClick(() => {
  isMonitoring ? sendStop() : sendStart();
});

function sendStart() {
  mainBtn.setEnabled(false);

  chrome.runtime.sendMessage({ action: "START_CAPTURE" }, (response) => {
    mainBtn.setEnabled(true);

    if (chrome.runtime.lastError || !response?.ok) {
      const reason = response?.reason ?? chrome.runtime.lastError?.message ?? "unknown error";
      log.addEntry("warn", "Failed to start: " + reason);
      return;
    }

    isMonitoring = true;
    chrome.storage.local.set({ isMonitoring: true });
    applyMonitoringUI(true);
    log.addEntry("info", "Monitoring started.");
  });
}

function sendStop() {
  mainBtn.setEnabled(false);

  chrome.runtime.sendMessage({ action: "STOP_CAPTURE" }, (response) => {
    mainBtn.setEnabled(true);

    if (chrome.runtime.lastError || !response?.ok) {
      const reason = response?.reason ?? chrome.runtime.lastError?.message ?? "unknown error";
      log.addEntry("warn", "Failed to stop: " + reason);
      return;
    }

    isMonitoring = false;
    chrome.storage.local.set({ isMonitoring: false });
    applyMonitoringUI(false);
    log.addEntry("info", "Monitoring stopped.");
  });
}

function applyMonitoringUI(active) {
  statusBar.setActive(active);
  mainBtn.setActive(active);
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const onMeet = (tabs[0]?.url ?? "").includes("meet.google.com");
    mainBtn.setEnabled(onMeet);
  });
}

// Live Messages from Background  

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "CHUNK_SENT") {
    chunkCount++;
    stats.setChunks(chunkCount);
    chrome.storage.local.set({ chunkCount });
  }

  if (msg.action === "FLAG_DETECTED") {
    flagCount++;
    stats.setFlags(flagCount);
    chrome.storage.local.set({ flagCount });

    const src  = msg.source     ?? "unknown";
    const lang = msg.language   ?? "?";
    const lbl  = msg.label      ?? "harmful";
    const conf = msg.confidence != null ? ` (${Math.round(msg.confidence * 100)}%)` : "";
    log.addEntry("warn", `[${src}][${lang}] ${lbl}${conf}`);
  }

  if (msg.action === "BACKEND_STATUS") {
    backendBadge.set(msg.status, msg.device);
    chrome.storage.local.set({
      backendStatus: { status: msg.status, device: msg.device },
    });
    if (msg.status === "degraded") {
      log.addEntry("warn", `Backend degraded — whisper:${msg.whisper} xlmr:${msg.xlmr}`);
    } else {
      log.addEntry("info", `Backend OK — device: ${msg.device}`);
    }
  }

  if (msg.action === "CAPTURE_ERROR") {
    log.addEntry("warn", "Capture error: " + (msg.reason ?? "unknown"));
    isMonitoring = false;
    applyMonitoringUI(false);
    chrome.storage.local.set({ isMonitoring: false });
  }
});
