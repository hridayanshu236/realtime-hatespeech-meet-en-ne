// Runs in a hidden page, has full Web Audio access

let audioContext, workletNode;
const CHUNK_SECONDS = 4;
const BACKEND_URL = "http://localhost:8000";

async function init() {
  const params = new URLSearchParams(location.search);
  const streamId = params.get("streamId");
  if (!streamId) {
    console.error("No streamId provided in URL query parameters");
    return;
  }

  // Reconstruct the MediaStream from the tab capture stream ID
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId
      }
    }
  });

  audioContext = new AudioContext({ sampleRate: 16000 }); // Whisper expects 16kHz
  const source = audioContext.createMediaStreamSource(stream);

  // Load your AudioWorklet for chunking
  await audioContext.audioWorklet.addModule("audioProcessor.js");
  workletNode = new AudioWorkletNode(audioContext, "chunk-processor", {
    processorOptions: { chunkSeconds: CHUNK_SECONDS, sampleRate: 16000 }
  });

  // When the worklet has a full 4-second chunk, send to backend
  workletNode.port.onmessage = async (e) => {
    chrome.runtime.sendMessage({ action: "CHUNK_SENT" });
    const wavBlob = encodeToWAV(e.data.pcmBuffer, 16000);
    await sendAudioToBackend(wavBlob);
  };

  source.connect(workletNode);
  source.connect(audioContext.destination); // Route audio to speakers so user can still hear the meeting
}

init().catch(err => {
  console.error("Initialization failed:", err);
});

async function sendAudioToBackend(wavBlob) {
  const formData = new FormData();
  formData.append("audio_file", wavBlob, "chunk.wav");

  try {
    const res = await fetch(`${BACKEND_URL}/pipeline`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    
    // Relay log to content script so user can see it in Meet DevTools
    chrome.runtime.sendMessage({ action: "PIPELINE_LOG", data: data });

    if (data.any_flagged && data.audio_result && data.audio_result.flagged) {
      // Tell the content script to show a warning overlay
      chrome.runtime.sendMessage({
        action: "SHOW_ALERT",
        transcript: data.audio_result.transcript,
        language: data.audio_result.language,
        label: data.audio_result.label
      });
    }
  } catch (err) {
    console.error("Backend error:", err);
  }
}

// Minimal WAV encoder — wraps raw PCM Float32 in a WAV header
function encodeToWAV(float32Array, sampleRate) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * bitsPerSample / 8;

  // Convert Float32 → Int16
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    pcm16[i] = Math.max(-32768, Math.min(32767, float32Array[i] * 32768));
  }

  const buffer = new ArrayBuffer(44 + pcm16.byteLength);
  const view = new DataView(buffer);
  // RIFF header
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + pcm16.byteLength, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);  // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, numChannels * bitsPerSample / 8, true);
  view.setUint16(34, bitsPerSample, true);
  writeString(view, 36, "data");
  view.setUint32(40, pcm16.byteLength, true);
  new Int16Array(buffer, 44).set(pcm16);

  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++)
    view.setUint8(offset + i, str.charCodeAt(i));
}