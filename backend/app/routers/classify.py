from fastapi import APIRouter, Request, HTTPException
from app.schemas import ClassifyRequest, ClassifyResponse
from app.inference import run_classification
from app.utils import log_flagged_event, detect_language

router = APIRouter(tags=["Classification"])

@router.post("/classify", response_model=ClassifyResponse)
def classify_text(request: Request, payload: ClassifyRequest):
    """
    Classifies raw text for hate speech or profanity using XLM-RoBERTa.
    """
    try:
        thresholds = getattr(request.app.state, "thresholds", {})

        # Auto-detect language if not strictly provided
        lang = payload.language
        if lang in ["unknown", "en", None]:
            lang = detect_language(payload.text)

        # Run inference
        result = run_classification(
            request.app.state.xlmr_model,
            request.app.state.xlmr_tokenizer,
            payload.text,
            lang,
            request.app.state.device,
            thresholds
        )

        # Log if flagged
        if result["flagged"]:
            log_flagged_event(
                text=payload.text,
                label=result["label"],
                confidence=result["confidence"],
                language=lang,
                source="chat"
            )

        return ClassifyResponse(
            text=payload.text,
            language=lang,
            label=result["label"],
            confidence=result["confidence"],
            scores=result["scores"],
            flagged=result["flagged"],
            status="success"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
