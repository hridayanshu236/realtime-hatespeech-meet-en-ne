let audioContext = null;
let workletNode  = null;
let mediaStream  = null;

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === ACTIONS.INIT_AUDIO) {
    initAudio(msg.streamId).catch((err) => {
      console.error("[offscreen] initAudio:", err);
      chrome.runtime.sendMessage({ action: ACTIONS.CAPTURE_ERROR, reason: err.message });
    });
  }

  if (msg.action === ACTIONS.STOP_AUDIO) {
    teardown();
    sendResponse({ ok: true });
    return true;
  }
});


async function initAudio(streamId) {
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource:   "tab",
        chromeMediaSourceId: streamId,
      },
    },
    video: false,
  });

  audioContext = new AudioContext({ sampleRate: CONFIG.SAMPLE_RATE });
  const source = audioContext.createMediaStreamSource(mediaStream);

  // Worklet must be loaded via extension URL, not a bare relative path,
  // because the offscreen page's base URL is its own HTML file.
  const workletUrl = chrome.runtime.getURL("assets/worklet/audioProcessor.js");
  await audioContext.audioWorklet.addModule(workletUrl);

  workletNode = new AudioWorkletNode(audioContext, "chunk-processor", {
    processorOptions: {
      chunkSeconds: CONFIG.CHUNK_SECONDS,
      sampleRate:   CONFIG.SAMPLE_RATE,
    },
  });

  // Each message = one completed PCM chunk (4 seconds of audio)
  workletNode.port.onmessage = async (e) => {
    const wavBlob = encodeToWAV(e.data.pcmBuffer, CONFIG.SAMPLE_RATE);
    await sendToPipeline(wavBlob);
  };

  source.connect(workletNode);
  
}

function teardown() {
  try { workletNode?.disconnect(); } catch (_) {}
  try { audioContext?.close();     } catch (_) {}
  mediaStream?.getTracks().forEach(t => t.stop());
  audioContext = null;
  workletNode  = null;
  mediaStream  = null;
}
async function sendToPipeline(wavBlob) {
  const formData = new FormData();
  // Field name must be "audio_file" — matches UploadFile = File(...) param in pipeline.py
  formData.append("audio_file", wavBlob, "chunk.wav");

  try {
    const res = await fetch(`${CONFIG.BACKEND_URL}/pipeline`, {
      method: "POST",
      body:   formData,
    });

    if (!res.ok) {
      console.warn("[offscreen] /pipeline returned", res.status);
      return;
    }

    const data = await res.json();

    // Notify popup: one more chunk was processed
    chrome.runtime.sendMessage({ action: ACTIONS.CHUNK_SENT });

    // audio_result is null if the audio was silent / empty
    const audio = data.audio_result;
    if (!audio) return;

    if (data.any_flagged && audio.flagged) {
      // Tell background → content script to show the overlay
      chrome.runtime.sendMessage({
        action:     ACTIONS.SHOW_ALERT,
        transcript: audio.transcript,
        language:   audio.language,
        label:      audio.label,
        confidence: audio.confidence,
        source:     "audio",
      });

      // Tell popup to bump the flag counter and add a log entry
      chrome.runtime.sendMessage({
        action:   ACTIONS.FLAG_DETECTED,
        source:   "audio",
        language: audio.language,
        label:    audio.label,
        confidence: audio.confidence,
      });
    }
  } catch (err) {
    console.error("[offscreen] /pipeline error:", err);
  }
}

function encodeToWAV(float32Array, sampleRate) {
  const numChannels   = 1;
  const bitsPerSample = 16;
  const byteRate      = sampleRate * numChannels * (bitsPerSample / 8);
  const blockAlign    = numChannels * (bitsPerSample / 8);

  // Convert Float32 → Int16 PCM
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    pcm16[i] = Math.max(-32768, Math.min(32767, Math.round(float32Array[i] * 32767)));
  }

  const buffer = new ArrayBuffer(44 + pcm16.byteLength);
  const view   = new DataView(buffer);

  writeStr(view,  0, "RIFF");
  view.setUint32( 4, 36 + pcm16.byteLength, true);
  writeStr(view,  8, "WAVE");
  writeStr(view, 12, "fmt ");
  view.setUint32(16, 16,            true);  // PCM chunk size
  view.setUint16(20,  1,            true);  // PCM format = 1
  view.setUint16(22, numChannels,   true);
  view.setUint32(24, sampleRate,    true);
  view.setUint32(28, byteRate,      true);
  view.setUint16(32, blockAlign,    true);
  view.setUint16(34, bitsPerSample, true);
  writeStr(view, 36, "data");
  view.setUint32(40, pcm16.byteLength, true);
  new Int16Array(buffer, 44).set(pcm16);

  return new Blob([buffer], { type: "audio/wav" });
}

function writeStr(view, offset, str) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}
