from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from app.schemas import TranscribeResponse
from app.utils import save_temp_wav, delete_file
from app.inference import run_transcription

router = APIRouter(tags=["Transcription"])

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: Request, audio_file: UploadFile = File(...)):
    """
    Transcribes a WAV audio chunk using the pre-loaded Whisper model.
    """
    if not audio_file.filename.endswith(('.wav', '.WAV')):
        raise HTTPException(status_code=400, detail="Invalid file format. Only WAV files are supported.")

    temp_path = None
    try:
        # 1. Read bytes and save to temp file
        audio_bytes = await audio_file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
            
        temp_path = save_temp_wav(audio_bytes)

        # 2. Transcribe
        whisper_model = request.app.state.whisper_model
        result = run_transcription(whisper_model, temp_path)

        return TranscribeResponse(
            transcript=result["transcript"],
            language=result["language"],
            segments=result["segments"],
            status="success"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    finally:
        # 3. Clean up
        if temp_path:
            delete_file(temp_path)
