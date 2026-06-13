import os
import json
import torch
import logging

# Suppress HuggingFace symlink warning on Windows (cosmetic only, no effect on functionality)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
from faster_whisper import WhisperModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger("model_loader")

def load_whisper(model_size: str = "medium") -> WhisperModel:
    """
    Loads a faster-whisper model. It is 4x faster than openai-whisper on CPU
    with identical accuracy. Automatically uses CUDA if available, with INT8 quantization.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # INT8 quantization on CPU is the secret sauce — it halves the computation time
    # with virtually zero accuracy loss.
    compute_type = "float16" if device == "cuda" else "int8"

    logger.info(f"Loading faster-whisper model '{model_size}' on {device} (compute_type={compute_type})...")
    if model_size in ["medium", "large", "large-v2", "large-v3"]:
        logger.warning(f"Using a larger Whisper model ('{model_size}'). It may take a few minutes to download on first run.")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info(f"faster-whisper '{model_size}' loaded successfully.")
    return model

def load_xlmroberta(model_path: str = "./models/xlm_roberta/final"):
    """
    Loads fine-tuned XLM-RoBERTa model and tokenizer.
    Returns (model, tokenizer).
    """
    # Check both potential paths to be robust
    alt_path = "./models/xlmroberta_finetuned/"
    if not os.path.exists(model_path) and os.path.exists(alt_path):
        model_path = alt_path

    if not os.path.exists(model_path):
        msg = f"Model path not found: {model_path}. Please run training first or ensure model files are placed there."
        logger.error(msg)
        raise FileNotFoundError(msg)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Loading XLM-RoBERTa from {model_path} on {device}...")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path).to(device)
    model.eval()
    
    logger.info("XLM-RoBERTa loaded and set to eval mode.")
    return model, tokenizer

def load_thresholds(model_path: str = "./models/xlm_roberta/final"):
    """
    Loads language-specific thresholds from thresholds.json if available.
    """
    alt_path = "./models/xlmroberta_finetuned/"
    if not os.path.exists(model_path) and os.path.exists(alt_path):
        model_path = alt_path

    thresholds_file = os.path.join(model_path, "thresholds.json")
    if os.path.exists(thresholds_file):
        try:
            with open(thresholds_file, "r") as f:
                thresholds = json.load(f)
            logger.info(f"Loaded language thresholds: {thresholds}")
            return thresholds
        except Exception as e:
            logger.warning(f"Failed to load thresholds.json: {e}. Using default 0.5")
    else:
        logger.warning("thresholds.json not found in model directory. Using default 0.5")
    
    return {}
