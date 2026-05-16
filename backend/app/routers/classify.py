from fastapi import APIRouter, Request, HTTPException
from app.schemas import ClassifyRequest, ClassifyResponse
from app.inference import run_classification
from app.utils import log_flagged_event

router = APIRouter(tags=["Classification"])

@router.post("/classify", response_model=ClassifyResponse)
async def classify_text(request: Request, payload: ClassifyRequest):
    """
    Classifies raw text for hate speech or profanity using XLM-RoBERTa.
    """
    try:
        model = request.app.state.xlmr_model
        tokenizer = request.app.state.xlmr_tokenizer
        device = request.app.state.device

        # Run inference
        result = run_classification(model, tokenizer, payload.text, device)

        # Log if flagged
        if result["flagged"]:
            log_flagged_event(
                text=payload.text,
                label=result["label"],
                confidence=result["confidence"],
                language=payload.language,
                source="chat"
            )

        return ClassifyResponse(
            text=payload.text,
            language=payload.language,
            label=result["label"],
            confidence=result["confidence"],
            scores=result["scores"],
            flagged=result["flagged"],
            status="success"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
