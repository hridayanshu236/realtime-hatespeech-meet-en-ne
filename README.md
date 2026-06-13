# Real-Time Multilingual Hate Speech Detector for Google Meet

A full-stack, real-time hate speech detection system built specifically for Google Meet. It captures live audio and chat text, transcribes speech, detects languages (English, Nepali, and Code-Switched), and classifies content using a fine-tuned XLM-RoBERTa model with language-specific thresholds.

## Architecture

1. **Chrome Extension (Frontend)**
   - Automatically captures Google Meet tab audio using `chrome.tabCapture`.
   - Uses an `AudioWorklet` to chop streaming audio into 4-second WAV chunks.
   - Monitors the Google Meet DOM to capture chat messages.
   - Overlays a non-intrusive warning on the screen when harmful content is detected.

2. **FastAPI Server (Backend)**
   - **Speech-to-Text**: Uses `faster-whisper` (CTranslate2, INT8 quantization) for near-instant, CPU-friendly transcription and Voice Activity Detection (VAD).
   - **Classification Engine**: Fine-tuned XLM-RoBERTa model.
   - **Dynamic Thresholding**: Uses statistically derived `thresholds.json` to adjust classification sensitivity based on the detected language (e.g., highly sensitive for low-resource Nepali/Code-Switched text).

3. **ML Pipeline (Training)**
   - Jupyter notebooks containing the entire data pipeline (cleaning, merging, unifying labels).
   - Training scripts for XLM-RoBERTa.

## Setup Instructions

### 1. Start the Backend
You must have Python 3.10+ installed.
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*Note: The first run will automatically download the `faster-whisper` medium model weights (~1.5GB).*

### 2. Install the Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Turn on **Developer mode** (top right corner).
3. Click **Load unpacked**.
4. Select the `extension/` folder from this repository.

### 3. Usage
1. Open a Google Meet session.
2. Click the extension icon in your Chrome toolbar.
3. Click **Start Monitoring**.
4. Any flagged audio or chat messages will trigger a red alert overlay in your Meet window.

## Important Note on Git
The `models/` folder (which contains the heavy PyTorch `xlm-roberta` weights) and any generated `.wav` files are intentionally excluded via `.gitignore` to prevent exceeding GitHub's file size limits.
