# GuardMeet Backend

This directory contains the machine learning inference server for the Real-Time Hate Speech Detector.

## Implementation Details
The backend is built using **FastAPI** and **PyTorch**, designed to handle concurrent processing of both audio streams and text chat messages with minimal latency.

* **API Framework:** FastAPI served by Uvicorn.
* **Speech-to-Text:** Utilizes `faster-whisper` (CTranslate2) with INT8 quantization for CPU-friendly, real-time audio transcription and built-in Voice Activity Detection (VAD).
* **Text Classification:** Employs a fine-tuned `XLM-RoBERTa` multilingual model to classify text into five categories (clean, profanity, hate_speech, threat, identity_attack).
* **Dynamic Thresholding:** Applies language-specific sensitivity thresholds to balance false positive rates across English, Nepali, and Code-Switched data.

## How to Run

The backend is fully automated via a Windows batch script. You must have Python 3.10 or newer installed.

1. Double-click the **`start_backend.bat`** file.

**What the script does automatically:**
1. Checks for a Python installation.
2. Creates a `.venv` virtual environment.
3. Installs all required dependencies from `requirements.txt`.
4. Downloads the heavy XLM-RoBERTa model weights from Google Drive (if they are not already present).
5. Starts the FastAPI server on `http://0.0.0.0:8000`.

*Note: The first time the server starts, it will briefly pause to download the `faster-whisper` medium model weights.*
