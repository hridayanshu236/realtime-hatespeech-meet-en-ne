export function MeetIndicator({ dotEl, labelEl }) {
  function setOnMeet(onMeet) {
    dotEl.classList.toggle("on-meet", onMeet);
    labelEl.classList.toggle("on-meet", onMeet);
    labelEl.textContent = onMeet ? "On Meet" : "Not on Meet";
  }

  return { setOnMeet };
}
