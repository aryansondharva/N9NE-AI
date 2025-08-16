"""
Chat history management
"""
import json
import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self, history_file: str = "chat_history.json"):
        self.history_file = history_file
        self.chat_store: Dict[str, List[dict]] = {}
        self.load_history()
    
    def load_history(self) -> None:
        """Load chat history from JSON file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.chat_store = json.load(f)
                logger.info("✅ Loaded chat history: %d sessions", len(self.chat_store))
            else:
                logger.info("📝 No existing chat history file found, starting fresh")
        except Exception as e:
            logger.error("⚠️ Error loading chat history: %s", e)
            self.chat_store = {}

    def save_history(self) -> None:
        """Save chat history to JSON file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_store, f, indent=2, ensure_ascii=False)
            logger.info("💾 Saved chat history: %d sessions", len(self.chat_store))
        except Exception as e:
            logger.error("❌ Error saving chat history: %s", e)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to a chat session"""
        if session_id not in self.chat_store:
            self.chat_store[session_id] = []
        self.chat_store[session_id].append({
            "role": role,
            "content": content
        })
        self.save_history()

    def get_session_history(self, session_id: str) -> List[dict]:
        """Get chat history for a session"""
        return self.chat_store.get(session_id, [])

    def delete_session(self, session_id: str) -> bool:
        """Delete a specific chat session"""
        if session_id in self.chat_store:
            del self.chat_store[session_id]
            self.save_history()
            return True
        return False

    def clear_all_sessions(self) -> int:
        """Delete all chat sessions"""
        session_count = len(self.chat_store)
        self.chat_store.clear()
        self.save_history()
        return session_count

    def list_sessions(self) -> List[dict]:
        """List all active chat sessions"""
        sessions = []
        for session_id, messages in self.chat_store.items():
            sessions.append({
                "session_id": session_id,
                "message_count": len(messages),
                "last_message": messages[-1]["content"][:100] + "..." if messages else "No messages"
            })
        return sessions
