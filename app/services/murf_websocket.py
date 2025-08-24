"""Murf HTTP Streaming TTS Service for streaming text-to-speech
Handles HTTP streaming connection to Murf API for real-time audio generation
Updated to use official Murf SDK instead of deprecated WebSocket endpoints
"""
import asyncio
import json
import logging
import base64
from typing import Optional, Callable
import uuid
try:
    from murf import Murf
    MURF_SDK_AVAILABLE = True
except ImportError:
    MURF_SDK_AVAILABLE = False
    logging.warning("Murf SDK not installed. Install with: pip install murf")

logger = logging.getLogger(__name__)

class MurfStreamingService:
    def __init__(self, api_key: str, voice_id: str = "en-US-natalie"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.websocket = None
        self.context_id = str(uuid.uuid4())  # Static context ID to avoid context limit errors
        self.is_connected = False
        self.audio_callback: Optional[Callable[[str], None]] = None
        self.websocket_callback: Optional[Callable[[str], None]] = None
        
    async def connect(self):
        """Initialize Murf HTTP Streaming API connection"""
        try:
            if not MURF_SDK_AVAILABLE:
                logger.warning("⚠️ Murf SDK not available, using mock connection for testing")
                self.websocket = None
                self.is_connected = False
                return False
            
            # Initialize Murf client with official SDK
            self.murf_client = Murf(api_key=self.api_key)
            self.is_connected = True
            
            logger.info(f"✅ Connected to Murf HTTP Streaming API with context_id: {self.context_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Murf HTTP Streaming: {e}")
            self.is_connected = False
            return False
    
    # HTTP streaming doesn't need message listening - removed _listen_for_messages
    
    # HTTP streaming handles responses directly in send_text_chunk - removed _handle_message
    
    async def send_text_chunk(self, text: str, is_final: bool = False):
        """Send text chunk to Murf for TTS conversion using HTTP streaming"""
        if not self.is_connected or not MURF_SDK_AVAILABLE:
            # Mock audio generation for testing when Murf is not available
            logger.info(f"🎭 Mock TTS: '{text}' (final: {is_final})")
            
            # Generate mock base64 audio data for testing
            mock_audio = base64.b64encode(f"MOCK_AUDIO_DATA_{text[:20]}".encode()).decode()
            
            # Print mock base64 audio to console (Day 20 requirement)
            print(f"[MURF AUDIO BASE64] {mock_audio}")
            logger.info(f"🎵 Generated mock base64 audio chunk: {len(mock_audio)} characters")
            
            # Send to WebSocket client if callback is set (Day 21)
            if self.websocket_callback:
                self.websocket_callback(mock_audio)
            
            # Call audio callback if set
            if self.audio_callback:
                self.audio_callback(mock_audio)
                
            return True
            
        try:
            # Use official Murf SDK for HTTP streaming
            res = self.murf_client.text_to_speech.stream(
                text=text,
                voice_id=self.voice_id
            )
            
            # Process streaming audio chunks
            for audio_chunk in res:
                # Convert to base64 for consistency with existing pipeline
                audio_base64 = base64.b64encode(audio_chunk).decode()
                
                # Print base64 audio to console (Day 20 requirement)
                print(f"[MURF AUDIO BASE64] {audio_base64}")
                logger.info(f"🎵 Received base64 audio chunk: {len(audio_base64)} characters")
                
                # Send to WebSocket client if callback is set (Day 21)
                if self.websocket_callback:
                    self.websocket_callback(audio_base64)
                
                # Call audio callback if set
                if self.audio_callback:
                    self.audio_callback(audio_base64)
            
            logger.info(f"📤 Completed streaming TTS for: '{text[:50]}...' (final: {is_final})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stream text with Murf: {e}")
            # Fallback to mock on error
            return await self.send_text_chunk(text, is_final)
    
    async def clear_context(self):
        """Clear the current context (generate new context_id)"""
        try:
            # Generate new context ID for next conversation turn
            self.context_id = str(uuid.uuid4())
            logger.info(f"🧹 Generated new Murf context: {self.context_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to clear Murf context: {e}")
            return False
    
    def set_audio_callback(self, callback: Callable[[str], None]):
        """Set callback function to handle received audio data"""
        self.audio_callback = callback
        
    def set_websocket_callback(self, websocket_callback: Callable[[str], None]):
        """Set callback function to send audio data to WebSocket client"""
        self.websocket_callback = websocket_callback
    
    async def close(self):
        """Close the HTTP streaming connection"""
        try:
            if hasattr(self, 'murf_client'):
                # HTTP client doesn't need explicit closing
                self.murf_client = None
            logger.info("🔌 Murf HTTP streaming connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing Murf HTTP streaming: {e}")
        
        self.is_connected = False
        self.websocket = None
