export function MainButton({ btnEl, labelEl }) {
  function setActive(active) {
    if (active) {
      btnEl.className    = "main-btn stop";
      labelEl.textContent = "Stop Monitoring";
    } else {
      btnEl.className    = "main-btn start";
      labelEl.textContent = "Start Monitoring";
    }
  }

  function setEnabled(enabled) {
    btnEl.disabled = !enabled;
  }

  function onClick(handler) {
    btnEl.addEventListener("click", handler);
  }

  return { setActive, setEnabled, onClick };
}
