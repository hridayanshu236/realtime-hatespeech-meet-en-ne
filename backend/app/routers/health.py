from fastapi import APIRouter, Request
from app.schemas import HealthResponse
import torch

router = APIRouter(tags=["System"])

@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Checks the status of model loading and the available hardware device.
    """
    whisper_loaded = hasattr(request.app.state, "whisper_model") and request.app.state.whisper_model is not None
    xlmr_loaded = (
        hasattr(request.app.state, "xlmr_model") and request.app.state.xlmr_model is not None and
        hasattr(request.app.state, "xlmr_tokenizer") and request.app.state.xlmr_tokenizer is not None
    )
    
    device = str(request.app.state.device) if hasattr(request.app.state, "device") else "unknown"
    
    status = "ok" if (whisper_loaded and xlmr_loaded) else "degraded"
    
    return HealthResponse(
        status=status,
        whisper_loaded=whisper_loaded,
        xlmr_loaded=xlmr_loaded,
        device=device,
        version="1.0.0"
    )
