import os
import json
import torch
import logging
import tempfile
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backend_utils")

def get_device() -> torch.device:
    """Returns CUDA device if available, otherwise CPU."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return device

def save_temp_wav(audio_bytes: bytes) -> str:
    """Saves uploaded audio bytes to a temporary WAV file and returns the path."""
    # suffix=".wav" ensures libraries like Whisper/Soundfile identify the format
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        return tmp.name

def delete_file(path: str):
    """Safely deletes a file if it exists."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"Failed to delete temp file {path}: {e}")

def log_flagged_event(text: str, label: str, confidence: float, language: str, source: str):
    """
    Appends a JSON-formatted line to the flagged events log.
    Source should be 'audio' or 'chat'.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "flagged_events.jsonl")
    
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "text": text,
        "label": label,
        "confidence": round(confidence, 4),
        "language": language
    }
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to log flagged event: {e}")
