const MAX_LOG = 50;

export function EventLog({ logBoxEl, logEmptyEl, clearBtnEl }) {

  //  Render a single entry into the DOM 
  function renderEntry(entry, scroll = true) {
    logEmptyEl.style.display = "none";

    const el = document.createElement("div");
    el.className = `log-entry ${entry.type}`;

    const time = document.createElement("span");
    time.className   = "log-time";
    time.textContent = entry.time;

    const msg = document.createElement("span");
    msg.className   = "log-msg";
    msg.textContent = entry.message; // textContent — no XSS risk

    el.appendChild(time);
    el.appendChild(msg);
    logBoxEl.appendChild(el);

    if (scroll) logBoxEl.scrollTop = logBoxEl.scrollHeight;
  }

  // Add a new entry, persist to storage 
  function addEntry(type, message) {
    const entry = {
      type,
      message,
      time: new Date().toLocaleTimeString([], {
        hour:   "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }),
    };

    chrome.storage.local.get(["logEntries"], (data) => {
      const entries = data.logEntries ?? [];
      entries.push(entry);
      if (entries.length > MAX_LOG) entries.splice(0, entries.length - MAX_LOG);
      chrome.storage.local.set({ logEntries: entries });
    });

    renderEntry(entry, true);
  }

  function restore(entries = []) {
    if (!entries.length) return;
    logEmptyEl.style.display = "none";
    entries.forEach(e => renderEntry(e, false));
    logBoxEl.scrollTop = logBoxEl.scrollHeight;
  }
//clear
  function clear() {
    // Remove all children except the empty-state placeholder
    while (logBoxEl.firstChild) logBoxEl.removeChild(logBoxEl.firstChild);
    logEmptyEl.style.display = "";
    logBoxEl.appendChild(logEmptyEl);
    chrome.storage.local.set({ logEntries: [] });
  }

  clearBtnEl.addEventListener("click", clear);

  return { addEntry, restore };
}
