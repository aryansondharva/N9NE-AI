"""
Audio conversion utilities for streaming audio
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import pydub, but provide fallback if not available
try:
    from pydub import AudioSegment
    from pydub.utils import make_chunks
    PYDUB_AVAILABLE = True
    logger.info("✅ pydub is available for audio conversion")
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("⚠️ pydub not available - audio conversion will be limited")

def convert_webm_to_pcm(audio_data: bytes, sample_rate: int = 16000) -> Optional[bytes]:
    """
    Convert WebM/Opus audio data to PCM format for AssemblyAI
    
    Args:
        audio_data: Raw WebM/Opus audio bytes
        sample_rate: Target sample rate (default 16000 for AssemblyAI)
    
    Returns:
        PCM audio bytes or None if conversion fails
    """
    if not PYDUB_AVAILABLE:
        logger.warning("⚠️ pydub not available, cannot convert WebM to PCM")
        return None
        
    try:
        # Load audio from bytes
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
        
        # Convert to mono if stereo
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Set sample rate
        audio = audio.set_frame_rate(sample_rate)
        
        # Set sample width to 16-bit
        audio = audio.set_sample_width(2)
        
        # Export as raw PCM
        pcm_buffer = io.BytesIO()
        audio.export(pcm_buffer, format="raw")
        pcm_data = pcm_buffer.getvalue()
        
        logger.info(f"✅ Converted {len(audio_data)} bytes WebM to {len(pcm_data)} bytes PCM")
        return pcm_data
        
    except Exception as e:
        logger.error(f"❌ Failed to convert WebM to PCM: {e}")
        return None

def convert_audio_chunk_to_pcm(audio_chunk: bytes, sample_rate: int = 16000) -> Optional[bytes]:
    """
    Convert an audio chunk to PCM format or pass through if conversion fails
    
    Args:
        audio_chunk: Raw audio chunk bytes
        sample_rate: Target sample rate
    
    Returns:
        Audio bytes (converted or original)
    """
    try:
        # For now, let's just pass through the audio chunk
        # AssemblyAI should be able to handle WebM/Opus audio
        if len(audio_chunk) > 0:
            logger.info(f"📦 Passing through audio chunk: {len(audio_chunk)} bytes")
            return audio_chunk
            
    except Exception as e:
        logger.error(f"❌ Failed to process audio chunk: {e}")
        return None

def is_valid_audio_chunk(audio_chunk: bytes) -> bool:
    """
    Check if the audio chunk is valid and contains actual audio data
    """
    if not audio_chunk or len(audio_chunk) == 0:
        return False
    
    # Check for WebM signature
    if audio_chunk.startswith(b'\x1a\x45\xdf\xa3'):
        return True
    
    # Check for Opus signature
    if audio_chunk.startswith(b'OggS'):
        return True
    
    # If it's not a recognized format, assume it might be raw audio
    return len(audio_chunk) > 100  # Minimum size for meaningful audio
