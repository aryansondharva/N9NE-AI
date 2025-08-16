"""
Fallback utilities for audio responses
"""
import os
from pathlib import Path

FALLBACK_AUDIO_CANDIDATES = [
    "static/audio/fallback.mp3",  # optional if you add one
    "static/audio/282ee83b-dfa3-4c52-8a7d-5113884c9b17.mp3",
    "static/audio/4dd33907-e332-4435-8289-f427f527e783.mp3",
    "static/audio/61e566e2-c60c-4111-a37b-6ac40ea92ea7.mp3",
    "static/audio/6e4c10a8-6cd6-4d76-9246-1a2001aea43d.mp3",
    "static/audio/897f3d65-908e-41f6-afb7-b6f8021cc5a9.mp3",
    "static/audio/8ea6a778-4a56-4fc5-9132-16aae5032f8a.mp3",
    "static/audio/db2a9484-a00c-4acd-a26a-08870cbd3d7f.mp3",
    "static/audio/e4e571f4-d615-4c64-b8c2-aaf3de318ba3.mp3",
    "static/audio/f32daac2-5143-4513-a1e6-ec8cf7fb8e53.mp3",
    "static/audio/f67ae3f4-5c99-4458-a40f-4119a23ea130.mp3",
    "static/audio/fa69592b-d854-42e8-a40c-6ce1d568fb86.mp3",
    "sample_voice.mp3",
]

FALLBACK_MESSAGE = "I'm having trouble connecting right now. Please try again in a moment."

def get_fallback_audio_bytes() -> bytes:
    """
    Get fallback audio bytes from the first available audio file
    """
    base_path = Path(__file__).parent.parent.parent
    
    for path in FALLBACK_AUDIO_CANDIDATES:
        try:
            full_path = base_path / path
            if full_path.exists():
                with open(full_path, "rb") as f:
                    return f.read()
        except Exception:
            continue
    # As a last resort, return empty bytes (client should handle)
    return b""
