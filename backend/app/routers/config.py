from fastapi import APIRouter, Request, HTTPException
import gc
import torch
import logging
from app.schemas import WhisperConfigRequest
from app.model_loader import load_whisper

router = APIRouter(tags=["Config"])
logger = logging.getLogger("config_router")

@router.post("/config/whisper")
async def update_whisper_model(request: Request, payload: WhisperConfigRequest):
    """
    Dynamically unloads the current Whisper model and loads the requested one.
    """
    valid_sizes = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if payload.size not in valid_sizes:
        raise HTTPException(status_code=400, detail=f"Invalid size. Must be one of {valid_sizes}")

    try:
        logger.info(f"Received request to change Whisper model to: {payload.size}")
        
        # 1. Unload old model to free memory
        if hasattr(request.app.state, "whisper_model") and request.app.state.whisper_model is not None:
            del request.app.state.whisper_model
            request.app.state.whisper_model = None
            gc.collect()  # Force Python garbage collection to free faster-whisper's memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Old Whisper model unloaded from memory.")

        # 2. Load new model
        logger.info("Loading new Whisper model. This may take a moment if it needs downloading...")
        new_model = load_whisper(payload.size)
        request.app.state.whisper_model = new_model
        
        logger.info("Successfully switched Whisper model!")
        return {"status": "success", "message": f"Whisper model updated to '{payload.size}'"}

    except Exception as e:
        logger.error(f"Failed to change Whisper model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to change model: {str(e)}")
