"""
API routes for the voice agent
"""
import os
import shutil
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from io import BytesIO

from ..models.schemas import TextRequest, TranscriptionResponse, UploadResponse
from ..services.tts import generate_speech
from ..services.stt import transcribe_audio_file
from ..utils.fallback import get_fallback_audio_bytes

router = APIRouter()

# Set up upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/")
async def root():
    """Serve the main page"""
    return FileResponse("static/index.html")

@router.get("/fallback/audio")
async def fallback_audio():
    """Serve fallback audio"""
    audio_bytes = get_fallback_audio_bytes()
    if not audio_bytes:
        return JSONResponse(status_code=503, content={"error": "No fallback audio available"})
    return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")

@router.post("/generate")
async def generate_voice(data: TextRequest):
    """Generate voice from text"""
    return await generate_speech(data.text, data.voice)

@router.post("/upload")
async def upload_audio(file: UploadFile = File(...)) -> UploadResponse:
    """Upload audio file"""
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file_stat = os.stat(file_location)
    
    return UploadResponse(
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=file_stat.st_size,
        message="🎤 Recording uploaded successfully!",
        icon="🎤"
    )

@router.post("/transcribe/file")
async def transcribe_audio(file: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe audio file"""
    result = await transcribe_audio_file(file)
    if "error" in result:
        return JSONResponse(status_code=500, content=result)
    return TranscriptionResponse(**result)

@router.get("/logo/start")
async def get_start_logo():
    """Serve start recording logo"""
    return FileResponse("static/logos/start_recording.png")

@router.get("/logo/microphone")
async def get_microphone_logo():
    """Serve microphone logo"""
    return FileResponse("static/logos/microphone.png")
