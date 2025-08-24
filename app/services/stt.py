"""
Speech-to-Text service using AssemblyAI
"""
import os
import assemblyai as aai
from fastapi import UploadFile
from fastapi.responses import JSONResponse

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Initialize AssemblyAI settings but not the transcriber yet
if ASSEMBLYAI_API_KEY:
    aai.settings.api_key = ASSEMBLYAI_API_KEY

def get_transcriber():
    """
    Get AssemblyAI transcriber instance, initializing it if needed
    """
    if not ASSEMBLYAI_API_KEY:
        raise RuntimeError("AssemblyAI API key not found")
    
    # Initialize transcriber only when needed
    if not hasattr(get_transcriber, '_transcriber'):
        get_transcriber._transcriber = aai.Transcriber()
    
    return get_transcriber._transcriber

async def transcribe_audio_file(file: UploadFile) -> dict:
    """
    Transcribe audio file using AssemblyAI
    """
    try:
        audio_bytes = await file.read()
        if not ASSEMBLYAI_API_KEY:
            raise RuntimeError("AssemblyAI key missing")
            
        transcriber = get_transcriber()
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
