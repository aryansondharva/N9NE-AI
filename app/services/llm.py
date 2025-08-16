"""
Gemini LLM service
"""
import os
import requests
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No Gemini API key provided")

    async def generate_response(self, messages: List[Dict[str, str]], max_length: int = 3000) -> str:
        """
        Generate a response using the Gemini API
        messages: List of messages with role and content
        max_length: Maximum length of the response
        """
        try:
            if not self.api_key:
                raise RuntimeError("Gemini API key missing")

            # Convert messages to Gemini format
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

            # Prepare request
            url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": self.api_key}
            payload = {"contents": gemini_messages}

            # Make request
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            # Extract response text
            if "candidates" not in data or not data["candidates"]:
                raise RuntimeError("No response from Gemini API")

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            if len(text) > max_length:
                text = text[:max_length]

            return text

        except Exception as e:
            logger.error("Error in Gemini service: %s", str(e))
            raise
