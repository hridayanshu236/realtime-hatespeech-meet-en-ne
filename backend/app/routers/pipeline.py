from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from typing import Optional
from app.schemas import PipelineResponse, ClassifyResponse
from app.utils import save_temp_wav, delete_file, log_flagged_event, detect_language
from app.inference import run_transcription, run_classification

router = APIRouter(tags=["Pipeline"])

@router.post("/pipeline", response_model=PipelineResponse)
async def unified_pipeline(
    request: Request,
    audio_file: UploadFile = File(None),
    chat_text: str = Form(None)
):
    """
    Unified endpoint for handling both live audio chunks and chat messages simultaneously.
    Useful for minimizing round-trips from the Chrome extension.
    """
    if not audio_file and not chat_text:
        raise HTTPException(status_code=422, detail="At least one of 'audio_file' or 'chat_text' must be provided.")

    audio_result = None
    chat_result = None
    any_flagged = False

    # 1. Process Audio if provided
    if audio_file:
        temp_path = None
        try:
            audio_bytes = await audio_file.read()
            if len(audio_bytes) > 0:
                temp_path = save_temp_wav(audio_bytes)
                
                # Transcribe
                whisper_model = request.app.state.whisper_model
                trans_res = run_transcription(whisper_model, temp_path)
                
                # Classify transcript
                model = request.app.state.xlmr_model
                tokenizer = request.app.state.xlmr_tokenizer
                device = request.app.state.device
                thresholds = getattr(request.app.state, "thresholds", {})
                
                class_res = run_classification(
                    model, 
                    tokenizer, 
                    trans_res["transcript"], 
                    trans_res["language"], 
                    device, 
                    thresholds
                )
                
                audio_result = {
                    "transcript": trans_res["transcript"],
                    "language": trans_res["language"],
                    "label": class_res["label"],
                    "confidence": class_res["confidence"],
                    "flagged": class_res["flagged"]
                }
                
                if class_res["flagged"]:
                    any_flagged = True
                    log_flagged_event(
                        text=trans_res["transcript"],
                        label=class_res["label"],
                        confidence=class_res["confidence"],
                        language=trans_res["language"],
                        source="audio"
                    )
        finally:
            if temp_path:
                delete_file(temp_path)

    # 2. Process Chat Text if provided
    if chat_text:
        model = request.app.state.xlmr_model
        tokenizer = request.app.state.xlmr_tokenizer
        device = request.app.state.device
        thresholds = getattr(request.app.state, "thresholds", {})
        
        # Auto-detect language
        detected_lang = detect_language(chat_text)
        
        class_res = run_classification(model, tokenizer, chat_text, detected_lang, device, thresholds)
        
        chat_result = ClassifyResponse(
            text=chat_text,
            language=detected_lang,
            label=class_res["label"],
            confidence=class_res["confidence"],
            scores=class_res["scores"],
            flagged=class_res["flagged"]
        )
        
        if class_res["flagged"]:
            any_flagged = True
            log_flagged_event(
                text=chat_text,
                label=class_res["label"],
                confidence=class_res["confidence"],
                language=detected_lang,
                source="chat"
            )

    # Note: For production scale, transcription should ideally be moved to 
    # a background task queue (e.g., Celery/Redis) to avoid blocking the API worker.
    
    return PipelineResponse(
        audio_result=audio_result,
        chat_result=chat_result,
        any_flagged=any_flagged,
        status="success"
    )
