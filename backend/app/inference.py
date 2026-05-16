import torch
import torch.nn.functional as F
import logging
import os
from app.utils import log_flagged_event

logger = logging.getLogger("inference_engine")

# Label mapping based on training schema
LABEL_MAP = {0: "clean", 1: "offensive", 2: "hate_speech"}

def run_transcription(whisper_model, audio_path: str):
    """Executes transcription on a WAV file. Falls back to mock if model is None."""
    if whisper_model is None:
        return {
            "transcript": "[MOCK] This is a simulated transcript because Whisper is not loaded.",
            "language": "en",
            "segments": [{"start": 0.0, "end": 4.0, "text": "Simulated audio content."}]
        }
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = whisper_model.transcribe(audio_path, fp16=(device == "cuda"))
    
    return {
        "transcript": result.get("text", "").strip(),
        "language": result.get("language", "unknown"),
        "segments": [
            {"start": s["start"], "end": s["end"], "text": s["text"].strip()} 
            for s in result.get("segments", [])
        ]
    }

def run_classification(model, tokenizer, text: str, device):
    """
    Executes XLM-RoBERTa classification. 
    If model/tokenizer is None, falls back to Mock Keyword-based logic.
    """
    # --- MOCK FALLBACK ---
    if model is None or tokenizer is None:
        text_lower = text.lower()
        # Simple keywords for testing Sachin's UI/Integration
        hate_keywords = ["stupid", "idiot", "kill", "hate", "फटाहा", "मर्नु"]
        offensive_keywords = ["bad", "shut up", "go away", "नराम्रो"]
        
        if any(w in text_lower for w in hate_keywords):
            label, score = "hate_speech", 0.92
        elif any(w in text_lower for w in offensive_keywords):
            label, score = "offensive", 0.75
        else:
            label, score = "clean", 0.98

        return {
            "label": label,
            "confidence": score,
            "scores": {"clean": 0.0, "offensive": 0.0, "hate_speech": 0.0},
            "flagged": label != "clean",
            "note": "MOCK PREDICTION (Model missing)"
        }
    # --- END MOCK FALLBACK ---

    if not text or len(text.strip()) == 0:
        return {
            "label": "clean", 
            "confidence": 1.0, 
            "scores": {"clean": 1.0, "offensive": 0.0, "hate_speech": 0.0},
            "flagged": False
        }

    # Tokenize
    inputs = tokenizer(
        text, 
        return_tensors="pt", 
        max_length=128, 
        truncation=True, 
        padding=True
    ).to(device)

    # Inference
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = F.softmax(logits, dim=-1).squeeze()

    # Get results using model's own label mapping
    pred_idx = int(torch.argmax(probs).item())
    
    # Use config labels if they exist, otherwise fallback to our map
    if hasattr(model.config, "id2label") and pred_idx in model.config.id2label:
        label = model.config.id2label[pred_idx]
    else:
        label = LABEL_MAP.get(pred_idx, f"label_{pred_idx}")
    
    # Standardize label names for our audit logs and UI
    label = label.lower().replace("label_", "")
    
    # Final Mapping Table (Forces numbers to words)
    friendly_map = {
        "0": "clean", "not_hate": "clean", "clean": "clean",
        "1": "offensive", "offensive": "offensive",
        "2": "hate_speech", "hate": "hate_speech", "hate_speech": "hate_speech"
    }
    
    label = friendly_map.get(label, label)

    # Build probability scores dict
    scores = {}
    for i, p in enumerate(probs.tolist() if probs.dim() > 0 else [probs.item()]):
        name = model.config.id2label.get(i, f"class_{i}") if hasattr(model.config, "id2label") else f"class_{i}"
        scores[name] = float(p)

    return {
        "label": label,
        "confidence": float(torch.max(probs).item()),
        "scores": scores,
        "flagged": label != "clean"
    }
