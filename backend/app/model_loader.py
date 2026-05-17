import os
import torch
import whisper
import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger("model_loader")

def load_whisper(model_size: str = "small") -> whisper.Whisper:
    """Loads OpenAI Whisper model onto the best available device."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Loading Whisper model '{model_size}' on {device}...")
    
    # download_root can be specified if needed
    model = whisper.load_model(model_size, device=device)
    logger.info(f"Whisper '{model_size}' loaded successfully.")
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
