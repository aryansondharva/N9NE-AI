# Day 20: Murf WebSocket Voice Agent

## Overview
This implementation demonstrates streaming LLM responses to Murf's WebSocket API for real-time text-to-speech conversion, with base64 audio output displayed in the console.

## Features
- **Real-time Voice Input**: AssemblyAI transcription via WebSocket
- **LLM Streaming**: Gemini LLM responses streamed in chunks
- **Murf WebSocket Integration**: Text chunks sent to Murf for TTS
- **Base64 Audio Output**: Audio data printed to console and displayed in UI
- **Static Context ID**: Prevents context limit errors

## Files Created/Modified
- `static/day20_murf_websocket.html` - Complete Day 20 UI
- `app/services/murf_websocket.py` - Murf WebSocket service
- `main.py` - Updated with Murf integration
- `requirements.txt` - Added websockets dependency

## Usage
1. Start server: `python main.py`
2. Visit: `http://localhost:8000/day20`
3. Click record button and speak
4. Watch base64 audio output in console and UI

## Flow
User Speech → AssemblyAI → LLM Streaming → Murf WebSocket → Base64 Audio

## Screenshot Instructions
Take screenshot showing base64 audio output for LinkedIn post.
