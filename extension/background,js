// Service Worker

let mediaStream = null;
let audioContext = null;

// Called from popup when user clicks "Start Monitoring"
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "START_CAPTURE") startCapture();
  if (msg.action === "STOP_CAPTURE")  stopCapture();
});

async function startCapture() {
  mediaStream = await new Promise(resolve =>
    chrome.tabCapture.capture({ audio: true, video: false }, resolve)
  );

  if (!mediaStream) {
    console.error("tabCapture failed — is a Meet tab active?");
    return;
  }

  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Process tab audio for hate speech detection"
  });

  // Pass the stream to offscreen context via message
  chrome.runtime.sendMessage({
    action: "INIT_AUDIO",
    streamId: mediaStream.id   // Transfer stream by ID
  });
}