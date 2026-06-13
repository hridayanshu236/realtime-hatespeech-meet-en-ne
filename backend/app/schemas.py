from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ClassifyRequest(BaseModel):
    text: str = Field(..., description="The text content to be classified for hate speech or profanity.")
    language: Optional[str] = Field("unknown", description="Optional language tag (e.g., 'en', 'ne').")

class ClassifyResponse(BaseModel):
    text: str
    language: str
    label: str = Field(..., description="Classification result: 'clean', 'offensive', or 'hate_speech'")
    confidence: float = Field(..., description="The probability score of the predicted label.")
    scores: Dict[str, float] = Field(..., description="Full probability distribution across all classes.")
    flagged: bool = Field(..., description="True if the content is not 'clean'.")
    status: str = "success"

class AudioSegment(BaseModel):
    start: float
    end: float
    text: str

class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    segments: List[AudioSegment]
    status: str = "success"

class PipelineResponse(BaseModel):
    audio_result: Optional[Dict] = Field(None, description="Result of audio transcription and classification.")
    chat_result: Optional[ClassifyResponse] = Field(None, description="Result of chat text classification.")
    any_flagged: bool = Field(..., description="True if either audio or chat results are flagged.")
    status: str = "success"

class HealthResponse(BaseModel):
    status: str
    whisper_loaded: bool
    xlmr_loaded: bool
    device: str
    version: str

class WhisperConfigRequest(BaseModel):
    size: str = Field(..., description="The Whisper model size (e.g., 'small', 'medium')")
