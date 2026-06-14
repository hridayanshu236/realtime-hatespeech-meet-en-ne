# GuardMeet Chrome Extension

This directory contains the frontend component for the Real-Time Hate Speech Detector, built as a Manifest V3 Chrome Extension.

## Implementation Details
The extension acts as the bridge between Google Meet and the local ML backend, capturing live media streams and manipulating the DOM to alert users.

* **Manifest V3 Architecture:** Utilizes a modern, secure service worker (`background.js`) to manage state and extension lifecycle.
* **Audio Capture:** Leverages `chrome.tabCapture` combined with an `offscreen` document. This allows the extension to continuously capture the Google Meet tab's audio (`USER_MEDIA`), slice it into manageable 4-second chunk blobs, and post them to the backend API without freezing the browser.
* **Text Capture:** A `content.js` script is injected directly into the active Google Meet tab. It uses a `MutationObserver` to monitor the DOM for newly sent chat messages in real time.
* **Visual Alerts:** When the backend flags an utterance or chat message as hate speech, the content script renders a highly visible, non-intrusive warning overlay directly over the Meet UI.

## How to Run

1. Open Google Chrome and type `chrome://extensions/` into the URL bar.
2. Toggle the **Developer mode** switch in the top right corner to the ON position.
3. Click the **Load unpacked** button in the top left.
4. Select this `extension` directory.

Once loaded, join a Google Meet session, click the GuardMeet icon in your browser toolbar, and click **Start Monitoring**. Ensure the FastAPI backend is running simultaneously.
