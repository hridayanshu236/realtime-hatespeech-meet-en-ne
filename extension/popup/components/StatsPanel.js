export function StatsPanel({ chunkEl, flagEl }) {
  function setChunks(n) { chunkEl.textContent = n; }
  function setFlags(n)  { flagEl.textContent  = n; }

  return { setChunks, setFlags };
}
