"""
Speech-to-Text service using AssemblyAI
"""
import os
import assemblyai as aai
from fastapi import UploadFile
from fastapi.responses import JSONResponse

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Initialize AssemblyAI
aai.settings.api_key = ASSEMBLYAI_API_KEY
transcriber = aai.Transcriber()

async def transcribe_audio_file(file: UploadFile) -> dict:
    """
    Transcribe audio file using AssemblyAI
    """
    try:
        audio_bytes = await file.read()
        if not ASSEMBLYAI_API_KEY:
            raise RuntimeError("AssemblyAI key missing")
            
        transcript = transcriber.transcribe(audio_bytes)
        return {
            "transcription": transcript.text,
            "status": "🔊 Transcription complete!",
            "icon": "🔊"
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Transcription failed. Please try again.",
        }
