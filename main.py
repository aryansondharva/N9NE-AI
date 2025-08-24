"""
===============================================
🌟 30 Days of AI Voice Agents Challenge
🔧 Backend: FastAPI
🧠 Integrations: Murf AI (TTS) + AssemblyAI (Transcription) + Gemini LLM
===============================================
"""
import logging
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from io import BytesIO
import requests
import shutil
import os
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from app.utils.fallback import get_fallback_audio_bytes, FALLBACK_MESSAGE
from app.routers.voice import router as voice_router
from app.utils.audio_converter import convert_audio_chunk_to_pcm
from app.services.llm import GeminiService
from app.services.murf_websocket import MurfStreamingService

# Load environment variables and API keys
load_dotenv()
MURF_API_KEY = os.getenv("MURF_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("voice-agent")

# Initialize AssemblyAI
transcriber = None
if ASSEMBLYAI_API_KEY:
    aai.settings.api_key = ASSEMBLYAI_API_KEY
    try:
        transcriber = aai.RealtimeTranscriber(
            on_data=lambda transcript: logger.debug(f"Partial: {transcript.text}"),
            on_error=lambda error: logger.error(f"AssemblyAI error: {error}"),
            sample_rate=16000,
        )
        logger.info("✅ Initialized AssemblyAI real-time transcriber")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AssemblyAI transcriber: {e}")
else:
    logger.warning("⚠️  ASSEMBLYAI_API_KEY not found. Real-time transcription will be disabled.")

# Verify API keys
logger.info("✅ Loaded Murf API Key: %s", bool(MURF_API_KEY))
logger.info("✅ Loaded AssemblyAI Key: %s", bool(ASSEMBLYAI_API_KEY))
logger.info("✅ Loaded Gemini API Key: %s", bool(GEMINI_API_KEY))

# Initialize FastAPI app
app = FastAPI(title="N9NE AI Voice Agent")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static frontend directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(voice_router)

@app.get("/debug")
async def debug_page():
    return FileResponse("static/debug_transcription.html")

@app.get("/streaming")
async def streaming_page():
    return FileResponse("static/streaming_audio.html")

@app.get("/test-streaming")
async def test_streaming_page():
    return FileResponse("static/test_streaming.html")

@app.get("/turn-detection")
async def turn_detection_demo():
    return FileResponse("static/turn_detection_demo.html")

@app.get("/day20")
async def day20_murf_websocket():
    return FileResponse("static/day20_murf_websocket.html")

@app.get("/day21")
async def day21_streaming_audio():
    return FileResponse("static/day21_streaming_audio.html")

# ============================================================
# 🔹 Day 16: Streaming Audio WebSocket
# ============================================================
import uuid
import time

# Store for streaming audio sessions
streaming_sessions = {}

# Store WebSocket connections
stream_manager = None

# Thread pool for AssemblyAI operations
executor = ThreadPoolExecutor(max_workers=4)

# AssemblyAI Real-time Transcription Setup
class AssemblyAIStreamer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.transcriber = None
        self.websocket = None
        self.session_id = None
        self.current_turn_text: str = ""
        self.turn_start_time: Optional[float] = None
        self.llm_service = GeminiService()
        self.murf_service: Optional[MurfStreamingService] = None
        
    async def start_transcription(self, websocket: WebSocket, session_id: str):
        """Start real-time transcription session"""
        self.websocket = websocket
        self.session_id = session_id
        self.current_turn_text = ""
        self.turn_start_time = time.time()
        
        try:
            # Initialize Murf WebSocket service if API key is available
            if MURF_API_KEY:
                self.murf_service = MurfStreamingService(MURF_API_KEY)
                
                # Set up WebSocket callback to send base64 audio to client (Day 21)
                def websocket_audio_callback(base64_audio):
                    if self.websocket:
                        try:
                            audio_data = {
                                "type": "streaming_audio",
                                "base64_audio": base64_audio,
                                "session_id": self.session_id
                            }
                            asyncio.create_task(self.websocket.send_text(json.dumps(audio_data)))
                            logger.info(f"📤 Sent base64 audio chunk to client: {len(base64_audio)} chars")
                        except Exception as e:
                            logger.error(f"❌ Error sending audio to client: {e}")
                
                # Set the WebSocket callback
                self.murf_service.set_websocket_callback(websocket_audio_callback)
                
                # Set up audio callback to send base64 audio to frontend
                def audio_callback(base64_audio):
                    if self.websocket:
                        try:
                            audio_data = {
                                "type": "murf_audio",
                                "base64_audio": base64_audio,
                                "session_id": self.session_id
                            }
                            asyncio.create_task(self.websocket.send_text(json.dumps(audio_data)))
                        except Exception as e:
                            logger.error(f"❌ Error sending audio to frontend: {e}")
                
                self.murf_service.set_audio_callback(audio_callback)
                
                murf_connected = await self.murf_service.connect()
                if murf_connected:
                    logger.info(f"✅ Murf WebSocket connected for session: {session_id}")
                    # Notify frontend of Murf connection
                    if self.websocket:
                        try:
                            murf_status = {
                                "type": "murf_connected",
                                "context_id": self.murf_service.context_id,
                                "session_id": self.session_id
                            }
                            await self.websocket.send_text(json.dumps(murf_status))
                        except Exception as e:
                            logger.error(f"❌ Error sending Murf status: {e}")
                else:
                    logger.error(f"❌ Failed to connect to Murf WebSocket for session: {session_id}")
                    # Notify frontend of Murf disconnection
                    if self.websocket:
                        try:
                            murf_status = {
                                "type": "murf_disconnected",
                                "session_id": self.session_id
                            }
                            await self.websocket.send_text(json.dumps(murf_status))
                        except Exception as e:
                            logger.error(f"❌ Error sending Murf status: {e}")
            else:
                logger.warning("⚠️ Murf API key not available, audio generation disabled")
            
            # Initialize AssemblyAI Universal-Streaming client
            self.streaming_client = StreamingClient(
                StreamingClientOptions(
                    api_key=self.api_key,
                    api_host="streaming.assemblyai.com",
                )
            )
            
            # Set up event handlers
            self.streaming_client.on(StreamingEvents.Begin, self._on_begin)
            self.streaming_client.on(StreamingEvents.Turn, self._on_turn)
            self.streaming_client.on(StreamingEvents.Termination, self._on_terminated)
            self.streaming_client.on(StreamingEvents.Error, self._on_streaming_error)
            
            # Connect to AssemblyAI Universal-Streaming
            await asyncio.get_event_loop().run_in_executor(
                executor, self.streaming_client.connect,
                StreamingParameters(
                    sample_rate=16000,
                    format_turns=True,
                    end_of_turn_silence_threshold=1000
                )
            )
            
            logger.info(f"🎤 AssemblyAI transcription started for session: {session_id}")
            await websocket.send_text("AssemblyAI transcription session started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start AssemblyAI transcription: {e}")
            await websocket.send_text(f"Transcription setup failed: {str(e)}")
            return False
    
    def _on_begin(self, event: BeginEvent):
        """Called when the Universal-Streaming session begins"""
        logger.info(f"🔌 AssemblyAI Universal-Streaming session started: {event.id}")
    
    def _on_turn(self, event: TurnEvent):
        """Handle incoming turn events from Universal-Streaming"""
        if not event.transcript:
            return

        # Print transcription to terminal
        if event.end_of_turn:
            print(f"[TRANSCRIPTION - FINAL]: {event.transcript}")
            logger.info(f"[Transcript] {event.transcript} (end_of_turn=True)")
            
            # Accumulate text for the current turn
            if self.current_turn_text:
                self.current_turn_text += " " + event.transcript
            else:
                self.current_turn_text = event.transcript
            
            # Process the complete turn
            asyncio.create_task(self._process_complete_turn())
        else:
            print(f"[TRANSCRIPTION - PARTIAL]: {event.transcript}", end="\r")
    
    async def _send_transcription(self, transcript: aai.RealtimeTranscript):
        """Send transcription data to websocket client"""
        try:
            transcription_data = {
                "type": "transcription",
                "message_type": transcript.message_type,
                "text": transcript.text,
                "confidence": getattr(transcript, 'confidence', None),
                "session_id": self.session_id
            }
            
            await self.websocket.send_text(json.dumps(transcription_data))
            logger.info(f"✅ Sent transcription to client: {transcript.message_type}")
        except Exception as e:
            logger.error(f"❌ Error in _send_transcription: {e}")
    
    async def _send_turn_detection(self, final_text: Optional[str] = None):
        """Send turn detection event to websocket client"""
        try:
            turn_data = {
                "type": "turn_detection",
                "event": "turn_end",
                "message": "User stopped speaking - turn detected",
                "session_id": self.session_id,
                "timestamp": time.time(),
                "final_text": final_text,
                "turn_duration": time.time() - self.turn_start_time if self.turn_start_time else None
            }
            
            await self.websocket.send_text(json.dumps(turn_data))
            logger.info(f"✅ Turn detection event sent to client with text: {final_text}")

            # Start LLM streaming in background once we have the final transcript
            if final_text and final_text.strip():
                try:
                    asyncio.create_task(self._start_llm_stream(final_text))
                except Exception as e:
                    logger.error(f"❌ Error starting LLM streaming task: {e}")
            
            # Reset turn state
            self.current_turn_text = ""
            self.turn_start_time = time.time()
            
        except Exception as e:
            logger.error(f"❌ Error in _send_turn_detection: {e}")

    async def _start_llm_stream(self, prompt_text: str):
        """Start streaming LLM response for the given prompt and send to Murf WebSocket."""
        try:
            messages = [{"role": "user", "content": prompt_text}]
            print(f"[LLM STREAM START] prompt: {prompt_text}")
            
            # Stream LLM response and send chunks to Murf
            full_response = ""
            chunk_count = 0
            
            # Send start of LLM response
            if self.websocket:
                await self.websocket.send_json({
                    "type": "llm_response_start",
                    "content": ""
                })
            
            # Stream LLM response
            try:
                async for chunk in self.llm_service.generate_streaming_response(messages):
                    if chunk.strip():
                        chunk_count += 1
                        full_response += chunk
                        
                        # Send chunk to client
                        if self.websocket:
                            await self.websocket.send_json({
                                "type": "llm_chunk",
                                "content": chunk
                            })
                        
                        # If we have Murf service, stream the TTS as well
                        if self.murf_service and self.murf_service.is_connected:
                            await self.murf_service.send_text_chunk(chunk, is_final=False)
                
                # Finalize the response
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "llm_response_end",
                        "content": ""
                    })
                
                # Finalize TTS
                if self.murf_service and self.murf_service.is_connected:
                    await self.murf_service.send_text_chunk("", is_final=True)
                    
                print(f"[LLM STREAM END] Total response: {len(full_response)} characters, {chunk_count} chunks")
                        
            except Exception as e:
                logger.error(f"Error in LLM streaming: {e}")
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "error",
                        "message": f"Error generating response: {str(e)}"
                    })
                    
        except Exception as e:
            logger.error(f"Error in _start_llm_stream: {e}")

    async def _handle_transcript(self, transcript: str, is_final: bool):
        """Handle incoming transcript and generate LLM response"""
        try:
            if not transcript.strip():
                return

            # Update current turn text
            self.current_turn_text = transcript
            
            if is_final:
                # When we have the final transcript, start LLM streaming
                await self._start_llm_stream(transcript)
                    
        except Exception as e:
            logger.error(f"Error handling transcript: {e}")
    
    async def _delayed_turn_detection(self):
        """Send turn detection after a delay to simulate turn end"""
        try:
            await asyncio.sleep(2.0)  # Wait 2 seconds after final transcript
            await self._send_turn_detection(final_text=self.current_turn_text)
        except Exception as e:
            logger.error(f"❌ Error in delayed turn detection: {e}")
    
    def _on_streaming_error(self, error: StreamingError):
        """Called when a Universal-Streaming error occurs"""
        logger.error(f"❌ AssemblyAI Universal-Streaming error: {error}")
    
    def _on_terminated(self, event: TerminationEvent):
        """Called when the Universal-Streaming session is terminated"""
        logger.info(f"🔌 AssemblyAI Universal-Streaming session terminated: {event.audio_duration_seconds}s processed")
    
    async def send_audio_data(self, audio_data: bytes):
        """Send audio data to AssemblyAI for transcription"""
        if self.streaming_client:
            try:
                # Check if audio chunk is valid
                if not audio_data or len(audio_data) == 0:
                    logger.warning("⚠️ Empty audio chunk received, skipping")
                    return
                
                # Send audio data directly to AssemblyAI
                await asyncio.get_event_loop().run_in_executor(
                    executor, self.streaming_client.send_audio, audio_data
                )
                logger.info(f"✅ Successfully sent {len(audio_data)} bytes to AssemblyAI")
                    
            except Exception as e:
                logger.error(f"❌ Error streaming audio to AssemblyAI: {e}")
                # Send error back to websocket
                if self.websocket:
                    try:
                        error_data = {
                            "type": "error",
                            "message": f"Transcription error: {str(e)}"
                        }
                        await self.websocket.send_text(json.dumps(error_data))
                    except:
                        pass
    
    async def close(self):
        """Close the transcription session"""
        if hasattr(self, 'streaming_client'):
            try:
                await asyncio.get_event_loop().run_in_executor(
                    executor, self.streaming_client.close
                )
            except Exception as e:
                logger.error(f"❌ Error closing AssemblyAI streaming client: {e}")
        
        # Close Murf WebSocket connection
        if self.murf_service:
            try:
                await self.murf_service.close()
            except Exception as e:
                logger.error(f"❌ Error closing Murf WebSocket: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming audio data from client to server.
    Receives binary audio chunks, saves them to a file, and transcribes using AssemblyAI.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info(f"🔌 WebSocket connection established - Session: {session_id}")
    
    # Initialize AssemblyAI streamer
    assemblyai_streamer = None
    if ASSEMBLYAI_API_KEY:
        logger.info(f"✅ AssemblyAI API key available, initializing streamer")
        assemblyai_streamer = AssemblyAIStreamer(ASSEMBLYAI_API_KEY)
    else:
        logger.error(f"❌ AssemblyAI API key missing!")
    
    # Initialize Murf WebSocket service if API key is available
    murf_service = None
    if MURF_API_KEY:
        logger.info(f"✅ Murf API key available, initializing WebSocket service")
        murf_service = MurfStreamingService(MURF_API_KEY)
        
        # Set up audio callback to send base64 audio to frontend
        async def audio_callback(base64_audio):
            try:
                audio_data = {
                    "type": "murf_audio",
                    "base64_audio": base64_audio,
                    "session_id": session_id
                }
                await websocket.send_text(json.dumps(audio_data))
                logger.debug(f"✅ Sent audio chunk to client - {len(base64_audio)} chars")
            except Exception as e:
                logger.error(f"❌ Error sending audio to frontend: {e}")
        
        murf_service.set_audio_callback(audio_callback)
        
        # Connect to Murf WebSocket
        murf_connected = await murf_service.connect()
        if murf_connected:
            logger.info(f"✅ Murf WebSocket connected for session: {session_id}")
            await websocket.send_text(json.dumps({
                "type": "murf_status",
                "status": "connected",
                "message": "Murf WebSocket connected successfully"
            }))
    
    # Initialize session data
    streaming_sessions[session_id] = {
        "audio_chunks": [],
        "start_time": time.time(),
        "chunk_count": 0,
        "assemblyai_streamer": assemblyai_streamer,
        "murf_service": murf_service
    }
    
    try:
        while True:
            # Receive binary audio data from client
            message = await websocket.receive()
            
            if "bytes" in message:
                # Handle binary audio data
                audio_chunk = message["bytes"]
                logger.info(f"📨 Received audio chunk: {len(audio_chunk)} bytes - Session: {session_id}")
                
                # Store the audio chunk
                streaming_sessions[session_id]["audio_chunks"].append(audio_chunk)
                streaming_sessions[session_id]["chunk_count"] += 1
                
                # Send audio to AssemblyAI for real-time transcription
                if assemblyai_streamer and assemblyai_streamer.transcriber:
                    try:
                        # Send audio chunk to AssemblyAI
                        await assemblyai_streamer.send_audio_data(audio_chunk)
                        logger.info(f"🎤 Sent {len(audio_chunk)} bytes to AssemblyAI")
                    except Exception as e:
                        logger.error(f"❌ Error sending audio to AssemblyAI: {e}")
                        await websocket.send_text(f"Transcription error: {str(e)}")
                else:
                    logger.warning(f"⚠️ AssemblyAI streamer not available for session: {session_id}")
                
                # Send acknowledgment back to client
                await websocket.send_text(f"Chunk {streaming_sessions[session_id]['chunk_count']} received ({len(audio_chunk)} bytes)")
                
            elif "text" in message:
                # Handle text messages (could be commands or JSON)
                try:
                    data = json.loads(message["text"])
                    
                    # Handle generate_tts message
                    if data.get("type") == "generate_tts" and "text" in data:
                        logger.info(f"🎙️  TTS request received: {data['text'][:50]}...")
                        if murf_service and murf_service.connected:
                            await murf_service.send_tts(data["text"])
                            await websocket.send_text(json.dumps({
                                "type": "tts_status",
                                "status": "sending",
                                "message": f"Generating TTS for: {data['text'][:50]}..."
                            }))
                        else:
                            logger.error("❌ Murf service not available or not connected")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "TTS service not available"
                            }))
                        continue
                    
                    # Handle text commands (legacy)
                    command = message["text"]
                    logger.info(f"📨 Received command: {command} - Session: {session_id}")
                    
                    if command == "stop_recording":
                        # Stop AssemblyAI transcription
                        if assemblyai_streamer:
                            await assemblyai_streamer.close()
                        
                        # Save the complete audio file
                        await save_streaming_audio(session_id, websocket)
                    
                    elif command == "start_recording":
                        # Reset session for new recording
                        streaming_sessions[session_id] = {
                            "audio_chunks": [],
                            "start_time": time.time(),
                            "chunk_count": 0,
                            "assemblyai_streamer": assemblyai_streamer,
                            "murf_service": murf_service
                        }
                except json.JSONDecodeError:
                    # Not a JSON message, treat as plain text command
                    command = message["text"]
                    logger.info(f"📨 Received non-JSON command: {command} - Session: {session_id}")
                    
                    if command == "stop_recording":
                        # Stop AssemblyAI transcription
                        if assemblyai_streamer:
                            await assemblyai_streamer.close()
                        
                        # Save the complete audio file
                        await save_streaming_audio(session_id, websocket)
                    
                    elif command == "start_recording":
                        # Reset session for new recording
                        streaming_sessions[session_id] = {
                            "audio_chunks": [],
                            "start_time": time.time(),
                            "chunk_count": 0,
                            "assemblyai_streamer": assemblyai_streamer,
                            "murf_service": murf_service
                        }
                    
                    # Start AssemblyAI transcription
                    if assemblyai_streamer:
                        logger.info(f"🎤 Starting AssemblyAI transcription for session: {session_id}")
                        transcription_started = await assemblyai_streamer.start_transcription(websocket, session_id)
                        if transcription_started:
                            await websocket.send_text("Recording started - ready to receive audio chunks with real-time transcription")
                            logger.info(f"✅ Transcription started successfully for session: {session_id}")
                        else:
                            await websocket.send_text("Recording started - transcription unavailable")
                            logger.error(f"❌ Failed to start transcription for session: {session_id}")
                    else:
                        await websocket.send_text("Recording started - AssemblyAI not configured")
                        logger.error(f"❌ AssemblyAI not configured for session: {session_id}")
                        
                else:
                    # Echo other text messages
                    response = f"Server echo: {command}"
                    await websocket.send_text(response)
                    logger.info(f"📤 Sent echo response: {response}")
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket connection closed - Session: {session_id}")
        # Clean up AssemblyAI session
        if assemblyai_streamer:
            await assemblyai_streamer.close()
        # Clean up session data
        if session_id in streaming_sessions:
            del streaming_sessions[session_id]
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e} - Session: {session_id}")
        # Clean up AssemblyAI session
        if assemblyai_streamer:
            await assemblyai_streamer.close()
        try:
            await websocket.close()
        except:
            pass
        # Clean up session data
        if session_id in streaming_sessions:
            del streaming_sessions[session_id]

async def save_streaming_audio(session_id: str, websocket: WebSocket):
    """
    Save the streamed audio chunks to a file.
    """
    if session_id not in streaming_sessions:
        await websocket.send_text("Error: Session not found")
        return
    
    session_data = streaming_sessions[session_id]
    audio_chunks = session_data["audio_chunks"]
    
    if not audio_chunks:
        await websocket.send_text("Error: No audio data to save")
        return
    
    try:
        # Create filename with timestamp
        timestamp = int(time.time())
        filename = f"streaming_audio_{session_id[:8]}_{timestamp}.webm"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        # Combine all audio chunks into a single file
        with open(filepath, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        
        # Get file stats
        file_size = os.path.getsize(filepath)
        duration = time.time() - session_data["start_time"]
        
        logger.info(f"💾 Saved streaming audio: {filepath} ({file_size} bytes, {len(audio_chunks)} chunks, {duration:.2f}s)")
        
        # Send success response to client
        response = {
            "status": "success",
            "message": "Audio saved successfully",
            "filename": filename,
            "file_size": file_size,
            "chunk_count": len(audio_chunks),
            "duration": round(duration, 2)
        }
        
        await websocket.send_text(json.dumps(response))
        
        # Clear the session data
        streaming_sessions[session_id]["audio_chunks"] = []
        streaming_sessions[session_id]["chunk_count"] = 0
        
    except Exception as e:
        logger.error(f"❌ Error saving streaming audio: {e}")
        await websocket.send_text(f"Error saving audio: {str(e)}")

# Keep uploads dir available for streaming saves
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# 🔹 Day 9: Full Non-Streaming Pipeline (with fallback)
# ============================================================
@app.post("/llm/query")
async def llm_query(file: UploadFile = File(...), voice: str = Form("default")):
    """
    Full pipeline: audio -> transcription -> LLM -> Murf TTS -> audio response
    """
    if not GEMINI_API_KEY or not MURF_API_KEY or not ASSEMBLYAI_API_KEY:
        # Directly return fallback audio when missing keys
        audio_bytes = get_fallback_audio_bytes()
        return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")

    try:
        audio_bytes = await file.read()
        transcript = transcriber.transcribe(audio_bytes)
        user_text = transcript.text
        if not user_text.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")

        # Gemini call
        gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}
        payload = {"contents": [{"parts": [{"text": user_text}]}]}

        gemini_response = requests.post(gemini_url, headers=headers, params=params, json=payload, timeout=60)
        gemini_response.raise_for_status()
        data = gemini_response.json()

        if "candidates" not in data or not data["candidates"]:
            raise RuntimeError("No response from Gemini API")

        llm_text = data["candidates"][0]["content"]["parts"][0]["text"]
        if len(llm_text) > 3000:
            llm_text = llm_text[:3000]

        # Murf TTS
        voice_map = {
            "default": "en-US-natalie",
            "narrator": "en-US-terrell",
            "support": "en-US-miles",
            "sergeant": "en-US-ken",
            "game": "en-US-paul"
        }
        voice_id = voice_map.get(voice.lower(), "en-US-natalie")

        murf_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": MURF_API_KEY or ""
        }
        murf_payload = {"text": llm_text, "voice_id": voice_id, "format": "mp3"}

        murf_response = requests.post(
            "https://api.murf.ai/v1/speech/generate",
            headers=murf_headers,
            json=murf_payload,
            timeout=60,
        )
        murf_response.raise_for_status()
        murf_data = murf_response.json()

        audio_url = murf_data.get("audioFile")
        if not audio_url:
            raise RuntimeError("Murf API did not return audioFile")

        audio_file = requests.get(audio_url, timeout=60)
        audio_file.raise_for_status()

        return StreamingResponse(BytesIO(audio_file.content), media_type="audio/mpeg")

    except Exception:
        audio_bytes = get_fallback_audio_bytes()
        return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")

# ==========================================================
# 🔹 Day 10 + 11: Chat History with Permanent Storage + Fallbacks
# ============================================================
# File storage for chat history
CHAT_HISTORY_FILE = "chat_history.json"
chat_history_store = {}

def load_chat_history():
    """Load chat history from JSON file"""
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Loaded chat history: {len(data)} sessions")
                return data
        else:
            print("📝 No existing chat history file found, starting fresh")
            return {}
    except Exception as e:
        print(f"⚠️ Error loading chat history: {e}")
        return {}

def save_chat_history():
    """Save chat history to JSON file"""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_history_store, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved chat history: {len(chat_history_store)} sessions")
    except Exception as e:
        print(f"❌ Error saving chat history: {e}")

# Load existing chat history on startup
chat_history_store = load_chat_history()

@app.post("/agent/chat/{session_id}")
async def chat_with_history(session_id: str, file: UploadFile = File(...), voice: str = Form("default")):
    # If any critical key is missing, return fallback immediately
    if not ASSEMBLYAI_API_KEY or not GEMINI_API_KEY or not MURF_API_KEY:
        # Append fallback assistant message to history for transparency
        if session_id not in chat_history_store:
            chat_history_store[session_id] = []
        chat_history_store[session_id].append({"role": "assistant", "content": FALLBACK_MESSAGE})
        save_chat_history()
        audio_bytes = get_fallback_audio_bytes()
        return StreamingResponse(BytesIO(audio_bytes), media_type="audio/mpeg")

    try:
        # Read audio
        audio_bytes = await file.read()

        # Transcribe using AssemblyAI
        try:
            transcript = transcriber.transcribe(audio_bytes)
            user_text = transcript.text
        except Exception:
            # Transcription failed → fallback
            if session_id not in chat_history_store:
                chat_history_store[session_id] = []
            chat_history_store[session_id].append({"role": "assistant", "content": FALLBACK_MESSAGE})
            save_chat_history()
            fb = get_fallback_audio_bytes()
            return StreamingResponse(BytesIO(fb), media_type="audio/mpeg")

        if not user_text or not user_text.strip():
            raise HTTPException(status_code=400, detail="No speech detected in audio")

        # Get or create history
        if session_id not in chat_history_store:
            chat_history_store[session_id] = []
        history = chat_history_store[session_id]

        # Append user message
        history.append({"role": "user", "content": user_text})
        save_chat_history()

        # Prepare Gemini request with full history
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})

        gemini_payload = {"contents": gemini_history}
        gemini_url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}

        try:
            gemini_response = requests.post(
                gemini_url, headers=headers, params=params, json=gemini_payload, timeout=60
            )
            gemini_response.raise_for_status()
            data = gemini_response.json()
            if "candidates" not in data or not data["candidates"]:
                raise RuntimeError("No response from Gemini API")
            llm_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            # LLM failure → fallback
            history.append({"role": "assistant", "content": FALLBACK_MESSAGE})
            save_chat_history()
            fb = get_fallback_audio_bytes()
            return StreamingResponse(BytesIO(fb), media_type="audio/mpeg")

        if len(llm_text) > 3000:
            llm_text = llm_text[:3000]

        # Append assistant reply
        history.append({"role": "assistant", "content": llm_text})
        save_chat_history()

        # Murf TTS
        voice_map = {
            "default": "en-US-natalie",
            "narrator": "en-US-terrell",
            "support": "en-US-miles",
            "sergeant": "en-US-ken",
            "game": "en-US-paul"
        }
        voice_id = voice_map.get(voice.lower(), "en-US-natalie")

        murf_headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": MURF_API_KEY or ""
        }
        murf_payload = {"text": llm_text, "voice_id": voice_id, "format": "mp3"}

        try:
            murf_response = requests.post(
                "https://api.murf.ai/v1/speech/generate",
                headers=murf_headers,
                json=murf_payload,
                timeout=60,
            )
            murf_response.raise_for_status()
            murf_data = murf_response.json()
            audio_url = murf_data.get("audioFile")
            if not audio_url:
                raise RuntimeError("Murf API did not return audioFile")
            audio_file = requests.get(audio_url, timeout=60)
            audio_file.raise_for_status()
            return StreamingResponse(BytesIO(audio_file.content), media_type="audio/mpeg")
        except Exception:
            fb = get_fallback_audio_bytes()
            return StreamingResponse(BytesIO(fb), media_type="audio/mpeg")

    except HTTPException as e:
        raise e
    except Exception as e:
        fb = get_fallback_audio_bytes()
        return StreamingResponse(BytesIO(fb), media_type="audio/mpeg")

@app.get("/agent/chat/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get chat history for a session (for debugging)"""
    if session_id not in chat_history_store:
        return {"messages": [], "session_id": session_id}
    
    return {
        "messages": chat_history_store[session_id],
        "session_id": session_id,
        "message_count": len(chat_history_store[session_id])
    }

@app.delete("/agent/chat/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a specific chat session"""
    if session_id in chat_history_store:
        del chat_history_store[session_id]
        save_chat_history()
        return {"message": f"Session {session_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@app.delete("/agent/chat/all")
async def delete_all_chat_sessions():
    """Delete all chat sessions"""
    session_count = len(chat_history_store)
    chat_history_store.clear()
    save_chat_history()
    return {"message": f"All {session_count} sessions deleted successfully"}

@app.get("/agent/chat/sessions/list")
async def list_all_sessions():
    """List all active chat sessions"""
    sessions = []
    for session_id, messages in chat_history_store.items():
        sessions.append({
            "session_id": session_id,
            "message_count": len(messages),
            "last_message": messages[-1]["content"][:100] + "..." if messages else "No messages",
            "created": "N/A"
        })
    return {"sessions": sessions, "total_sessions": len(sessions)}

@app.get("/agent/chat/test")
async def test_chat_endpoint():
    """Test endpoint to verify chat history processing works"""
    return {
        "status": "working",
        "message": "Chat history endpoint is functional",
        "chat_history_file": CHAT_HISTORY_FILE,
        "sessions_count": len(chat_history_store),
        "api_keys": {
            "gemini": bool(GEMINI_API_KEY),
            "murf": bool(MURF_API_KEY),
            "assemblyai": bool(ASSEMBLYAI_API_KEY)
        }
    }


# Graceful shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    """Save chat history when server shuts down"""
    print("🔄 Server shutting down, saving chat history...")
    save_chat_history()
    print("✅ Chat history saved successfully")

# WebSocket endpoint for audio streaming
@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    if stream_manager is None:
        await websocket.close(code=1008, reason="Stream manager not initialized")
        return
    await websocket.accept()
    await stream_manager.connect(websocket)

# TTS endpoint that triggers streaming
@app.post("/tts")
async def generate_speech(tts_request: dict):
    """
    Generate speech from text using Murf AI and stream it back to the client.
    
    Request body should be a JSON object with the following fields:
    - text: The text to convert to speech
    - voice: (optional) The voice to use for TTS
    """
    if stream_manager is None:
        raise HTTPException(status_code=503, detail="Stream manager not initialized")
    
    # Validate request
    if not tts_request or "text" not in tts_request:
        raise HTTPException(status_code=400, detail="Missing required field: text")
    
    # Start streaming in the background
    text = tts_request.get("text")
    voice = tts_request.get("voice", "default")
    
    # Create a task to handle the streaming
    asyncio.create_task(stream_manager.stream_audio_to_client(text, voice))
    
    return {
        "message": "Audio streaming started.", 
        "status": "processing",
        "text": text,
        "voice": voice
    }

# Initialize stream manager when the app starts
@app.on_event("startup")
async def startup_event():
    global stream_manager
    try:
        if MURF_API_KEY:
            stream_manager = MurfStreamingService(api_key=MURF_API_KEY)
            logger.info("✅ Initialized Murf WebSocket service")
        else:
            logger.warning("⚠️  Murf API key not found. Murf WebSocket service will not be available.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Murf WebSocket service: {str(e)}")
        stream_manager = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)