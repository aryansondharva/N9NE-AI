"""
Gemini LLM service with streaming support
"""
import os
import json
import logging
import requests
import asyncio
from typing import Dict, List, AsyncGenerator, Optional, Union

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No Gemini API key provided")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert messages to Gemini format"""
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        return gemini_messages

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_length: int = 3000,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate a response using the Gemini API with optional streaming
        
        Args:
            messages: List of messages with role and content
            max_length: Maximum length of the response
            stream: Whether to stream the response
            
        Returns:
            str: Complete response text if stream=False
            AsyncGenerator: Generator yielding response chunks if stream=True
        """
        if not self.api_key:
            raise RuntimeError("Gemini API key missing")

        gemini_messages = await self._convert_messages(messages)
        
        if stream:
            return self._stream_response_requests(messages, max_length)
        else:
            return await self._get_complete_response_requests(messages, max_length)

    async def _get_complete_response_requests(
        self,
        messages: List[Dict[str, str]],
        max_length: int
    ) -> str:
        """Get complete response using requests library"""
        gemini_messages = await self._convert_messages(messages)
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "maxOutputTokens": max_length,
                "temperature": 0.7,
            }
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("candidates"):
                raise RuntimeError("No response from Gemini API")
                
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Error in Gemini API request: {e}")
            raise RuntimeError(f"Failed to generate response: {str(e)}")

    async def _stream_response_requests(
        self,
        messages: List[Dict[str, str]],
        max_length: int
    ) -> AsyncGenerator[str, None]:
        """Stream response using requests library"""
        gemini_messages = await self._convert_messages(messages)
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "maxOutputTokens": max_length,
                "temperature": 0.7,
            }
        }
        
        try:
            # Use requests in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def make_request():
                return requests.post(url, headers=headers, params=params, json=payload, stream=True, timeout=60)
            
            response = await loop.run_in_executor(None, make_request)
            response.raise_for_status()
            
            buffer = ""
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                    
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        break
                        
                    try:
                        data = json.loads(chunk_data)
                        if "candidates" in data and data["candidates"]:
                            parts = data["candidates"][0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"]
                                if text.startswith(buffer):
                                    new_content = text[len(buffer):]
                                    if new_content:
                                        yield new_content
                                        buffer = text
                                else:
                                    yield text
                                    buffer = text
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error in streaming Gemini API request: {e}")
            raise RuntimeError(f"Failed to stream response: {str(e)}")

    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        max_length: int = 3000
    ) -> AsyncGenerator[str, None]:
        """Convenience method for streaming responses"""
        return await self.generate_response(messages, max_length, stream=True)

    async def stream_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Stream a response using the Gemini streaming API.
        Yields incremental text chunks as they arrive.
        """
        if not self.api_key:
            raise RuntimeError("Gemini API key missing")

        # Convert messages to Gemini format
        gemini_messages = await self._convert_messages(messages)
        url = f"{self.base_url}/models/gemini-1.5-flash:streamGenerateContent"
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        payload = {"contents": gemini_messages}

        try:
            with requests.post(url, headers=headers, params=params, json=payload, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    try:
                        data = json.loads(raw_line)
                    except json.JSONDecodeError:
                        # Some transports may prefix lines; try to strip known prefixes
                        line = raw_line.strip()
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[len("data: "):])
                            except Exception:
                                continue
                        else:
                            continue

                    # Extract text chunks from streaming events
                    try:
                        candidates = data.get("candidates") or []
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            text: Optional[str] = part.get("text")
                            if text:
                                yield text
                    except Exception:
                        # Ignore malformed events and continue streaming
                        continue
        except Exception as e:
            logger.error("Error in Gemini streaming service: %s", str(e))
            raise
