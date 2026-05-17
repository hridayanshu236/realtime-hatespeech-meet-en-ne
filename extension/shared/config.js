const CONFIG = {
  BACKEND_URL:    "http://localhost:8000",
  CHUNK_SECONDS:  4,
  SAMPLE_RATE:    16000,   // Whisper expects 16 kHz
  MAX_LOG:        50,
  HEALTH_TIMEOUT: 5000,    // ms to wait for /health before warning
};

const ACTIONS = {
  // popup ↔ background
  START_CAPTURE:   "START_CAPTURE",
  STOP_CAPTURE:    "STOP_CAPTURE",
  // background ↔ offscreen
  INIT_AUDIO:      "INIT_AUDIO",
  STOP_AUDIO:      "STOP_AUDIO",
  // offscreen / content → background → popup
  CHUNK_SENT:      "CHUNK_SENT",
  FLAG_DETECTED:   "FLAG_DETECTED",
  CAPTURE_ERROR:   "CAPTURE_ERROR",
  BACKEND_STATUS:  "BACKEND_STATUS",
  // background → content script
  SHOW_ALERT:      "SHOW_ALERT",
};