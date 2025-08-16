"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str
    voice: str = "default"

class TranscriptionResponse(BaseModel):
    transcription: str
    status: str
    icon: str

class UploadResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    message: str
    icon: str

class AudioResponse(BaseModel):
    audio_url: str
