import os
import torch
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.model_loader import load_whisper, load_xlmroberta, load_thresholds
from app.routers import transcribe, classify, pipeline, health, config
from app.utils import get_device

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events.
    Models are loaded once on startup and shared across the application.
    """
    # STARTUP
    logger.info("Starting up FastAPI Backend...")
    device = get_device()
    app.state.device = device
    
    try:
        # Set default Whisper model size
        whisper_size = "medium"
        
        # Load Models
        app.state.whisper_model = load_whisper(whisper_size)
        xlmr_model, xlmr_tokenizer = load_xlmroberta()
        app.state.xlmr_model = xlmr_model
        app.state.xlmr_tokenizer = xlmr_tokenizer
        app.state.thresholds = load_thresholds()
        
        logger.info("All models loaded successfully.")
    except Exception as e:
        logger.error(f"Critical failure during model loading: {e}")
        # We don't exit here so health checks can still report the error
        app.state.whisper_model = None
        app.state.xlmr_model = None
        app.state.xlmr_tokenizer = None

    yield
    
    # SHUTDOWN
    logger.info("Shutting down FastAPI Backend...")
    # Clear GPU memory if using CUDA
    if str(device) == "cuda":
        torch.cuda.empty_cache()
    logger.info("Shutdown complete.")

# Initialize FastAPI
app = FastAPI(
    title="Hate Speech Detection API",
    description="Real-time Multilingual Hate Speech and Profanity Detection for Virtual Meetings",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
# Allowed origins set to "*" for Chrome Extension compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "status": "failed"}
    )

# Include Routers
app.include_router(transcribe.router)
app.include_router(classify.router)
app.include_router(pipeline.router)
app.include_router(health.router)
app.include_router(config.router)

@app.get("/")
async def root():
    return {"message": "Hate Speech Detection API is running. Visit /docs for documentation."}
