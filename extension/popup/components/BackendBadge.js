export function BackendBadge({ badgeEl, deviceEl }) {
  function set(status, device) {
    if (!badgeEl) return;

    const ok = status === "ok";
    badgeEl.textContent = ok ? "Backend OK" : "Backend degraded";
    badgeEl.className   = "backend-badge " + (ok ? "ok" : "degraded");

    if (deviceEl && device) {
      deviceEl.textContent = device.toUpperCase(); // "CPU" or "CUDA"
    }
  }

  return { set };
}
