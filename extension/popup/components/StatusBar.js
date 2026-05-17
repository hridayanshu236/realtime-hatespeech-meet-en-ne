export function StatusBar({ dotEl, valueEl }) {
  function setActive(active) {
    if (active) {
      dotEl.classList.add("active");
      valueEl.textContent = "Active";
      valueEl.className   = "value active";
    } else {
      dotEl.classList.remove("active");
      valueEl.textContent = "Inactive";
      valueEl.className   = "value inactive";
    }
  }

  return { setActive };
}
