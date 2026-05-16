# 🛡️ Hate Speech Detection Backend

This is the production FastAPI backend for the real-time multilingual hate speech and profanity detection system. It integrates OpenAI Whisper for audio transcription and a fine-tuned XLM-RoBERTa model for text classification.

## 📁 Directory Structure
```text
hatespeech_project/
├── app/                  # Main FastAPI application
│   ├── main.py           # App entry point & lifespan
│   ├── model_loader.py   # Model loading logic
│   ├── inference.py      # Shared inference engine
│   ├── schemas.py        # Pydantic data models
│   ├── utils.py          # Helper functions & logging
│   └── routers/          # API endpoints
├── logs/                 # Flagged event JSONL logs
├── models/               # Trained models directory
└── run.sh                # Local startup script
```

## ⚙️ Installation

1. **Install Dependencies**:
   ```bash
   pip install -r app_requirements.txt
   ```
   *Note: For GPU support, ensure you install the CUDA-enabled version of PyTorch.*

2. **Place Trained Models**:
   Ensure your fine-tuned XLM-RoBERTa model is placed in:
   `models/xlm_roberta/final/`

## 🚀 Running the Server

Start the server locally using the provided script:
```bash
bash run.sh
```
The API will be available at `http://localhost:8000`. You can view the interactive documentation at `http://localhost:8000/docs`.

## 🛣️ API Endpoints

### 1. Transcribe Audio
**POST** `/transcribe`
- **Input**: Multipart `audio_file` (WAV)
- **Output**: JSON transcript and segments.

### 2. Classify Text
**POST** `/classify`
- **Input**: JSON `{"text": "...", "language": "en"}`
- **Output**: Label (clean/offensive/hate_speech) and confidence.

### 3. Unified Pipeline
**POST** `/pipeline`
- **Input**: Multipart `audio_file` and/or Form `chat_text`.
- **Output**: Combined results for both inputs.

## 🐳 Running with Docker
A `Dockerfile` can be added for containerization. Ensure GPU drivers are accessible via `nvidia-container-runtime` if training on CUDA.

## 📊 Event Logging
All flagged events (offensive or hate speech) are automatically logged to `logs/flagged_events.jsonl`. This data can be used for secondary audits and training improvements.

---
