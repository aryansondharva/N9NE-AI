"""
Text-to-Speech service using Murf AI
"""
import os
import requests
from fastapi.responses import JSONResponse, StreamingResponse
from io import BytesIO
from ..utils.fallback import get_fallback_audio_bytes

MURF_API_KEY = os.getenv("MURF_API_KEY")

VOICE_MAP = {
    "default": "en-US-natalie",
    "narrator": "en-US-terrell",
    "support": "en-US-miles",
    "sergeant": "en-US-ken",
    "game": "en-US-paul"
}

async def generate_speech(text: str, voice: str = "default") -> StreamingResponse | JSONResponse:
    """
    Generate speech from text using Murf AI
    """
    voice_id = VOICE_MAP.get(voice.lower(), "en-US-natalie")

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": MURF_API_KEY or ""
    }
    payload = {"text": text, "voice_id": voice_id}

    try:
        response = requests.post(
            "https://api.murf.ai/v1/speech/generate",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code == 200:
            result = response.json()
            return JSONResponse(content={"audio_url": result.get("audioFile")})
        else:
            # Fallback on error
            audio_bytes = get_fallback_audio_bytes()
            return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")
    except Exception:
        audio_bytes = get_fallback_audio_bytes()
        return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")
