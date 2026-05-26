"""
services/memory_service.py — Conversation Memory Manager
=========================================================
Keeps track of each user's conversation history so the chatbot
can remember what was said earlier in the same session.

Without memory:
  User: "My name is Sarah."
  Bot:  "Hello Sarah!"
  User: "What's my name?"
  Bot:  "I don't know your name."  ← broken experience

With memory:
  User: "My name is Sarah."
  Bot:  "Hello Sarah!"
  User: "What's my name?"
  Bot:  "Your name is Sarah!"  ← natural, correct

Current storage: Python dictionary (in-process, zero dependencies).
  ✅ Fast (microsecond reads)
  ✅ No setup required
  ❌ Lost on server restart
  ❌ Not shared across multiple server instances

Production upgrade path:
  Phase 2 → Redis (TTL-based, survives restarts, multi-instance safe)
  Phase 3 → PostgreSQL (persistent, queryable conversation logs)
  Phase 4 → Vector DB + RAG (semantic memory, retrieval-augmented generation)

The interface is designed so upgrading storage requires only editing THIS file.
All other files use the same memory_service.add_turn() / .get_history() API.
"""

import time
import uuid
from typing import Dict, List, Optional

from app.models.chat_models import ConversationTurn, MessageRole
from app.core.config import settings
from app.utils.helpers import log_info, log_warning


# ---------------------------------------------------------------------------
# Memory Service Class
# ---------------------------------------------------------------------------

class MemoryService:
    """
    Session-based conversation memory manager.

    A 'session' is one user's ongoing conversation.
    Each session stores:
      - A list of ConversationTurn objects (the chat history)
      - The timestamp of the last activity (for TTL expiry)

    Internal data structure:
        {
            "session-id-abc": {
                "turns": [ConversationTurn, ConversationTurn, ...],
                "last_active": 1720000000.0   ← Unix timestamp
            }
        }
    """

    def __init__(self):
        # The main storage dictionary: { session_id: { turns, last_active } }
        self._store: Dict[str, dict] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def get_history(self, session_id: str) -> List[ConversationTurn]:
        """
        Return the full conversation history for a session.

        Also refreshes the session's last-active timestamp (keeps it alive).
        Returns an empty list if the session doesn't exist or has expired.

        Args:
            session_id: The unique session identifier.

        Returns:
            List of ConversationTurn objects, ordered oldest-first.
        """
        self._evict_expired_sessions()

        if session_id not in self._store:
            return []

        # Refresh last-active time
        self._store[session_id]["last_active"] = time.time()
        return list(self._store[session_id]["turns"])   # Return a copy

    def add_turn(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
    ) -> None:
        """
        Append a single message turn to a session's history.

        Automatically:
          - Creates the session if it doesn't exist
          - Refreshes the TTL
          - Trims history to MAX_MEMORY_TURNS to prevent unbounded growth

        Args:
            session_id: The session identifier.
            role:       MessageRole.USER or MessageRole.MODEL
            content:    The message text.
        """
        # Create session if first message
        if session_id not in self._store:
            self._store[session_id] = {
                "turns": [],
                "last_active": time.time(),
            }
            log_info(f"Memory: new session created | session_id={session_id}")

        session = self._store[session_id]
        session["turns"].append(ConversationTurn(role=role, content=content))
        session["last_active"] = time.time()

        # Trim: keep only the most recent N turns
        max_turns = settings.MAX_MEMORY_TURNS
        if len(session["turns"]) > max_turns:
            removed = len(session["turns"]) - max_turns
            session["turns"] = session["turns"][-max_turns:]
            log_info(
                f"Memory: trimmed {removed} old turn(s) | "
                f"session_id={session_id} | kept={max_turns}"
            )

    def add_exchange(
        self,
        session_id: str,
        user_message: str,
        model_reply: str,
    ) -> None:
        """
        Convenience method: add a complete user→model exchange at once.

        This is the most common operation — after every AI response,
        we save both the user's message and the AI's reply.

        Args:
            session_id:   The session identifier.
            user_message: What the user said.
            model_reply:  What the AI replied.
        """
        self.add_turn(session_id, MessageRole.USER, user_message)
        self.add_turn(session_id, MessageRole.MODEL, model_reply)

    def session_exists(self, session_id: str) -> bool:
        """Return True if the session has any stored history."""
        return session_id in self._store

    def get_turn_count(self, session_id: str) -> int:
        """Return the number of turns stored for a session."""
        if session_id not in self._store:
            return 0
        return len(self._store[session_id]["turns"])

    def clear_session(self, session_id: str) -> bool:
        """
        Delete all memory for a session.

        Returns True if the session existed and was cleared.
        Returns False if the session didn't exist.

        Call this when a user clicks "New Chat" or logs out.
        """
        if session_id in self._store:
            turn_count = len(self._store[session_id]["turns"])
            del self._store[session_id]
            log_info(
                f"Memory: session cleared | session_id={session_id} | "
                f"turns_deleted={turn_count}"
            )
            return True

        log_warning(f"Memory: clear requested for non-existent session | session_id={session_id}")
        return False

    def get_active_session_count(self) -> int:
        """Return the number of currently active sessions (for monitoring)."""
        return len(self._store)

    def generate_session_id(self) -> str:
        """
        Generate a new unique session ID.

        Uses UUID4 (random) — virtually no collision risk.
        Format: "sess-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

        The frontend should store this and send it with every subsequent request.
        """
        return f"sess-{uuid.uuid4()}"

    # ── Internal TTL Cleanup ────────────────────────────────────────────────

    def _evict_expired_sessions(self) -> None:
        """
        Remove sessions that haven't been active within the TTL window.

        Called automatically on every get_history() call — lazy eviction.
        This avoids the need for a background task while still preventing
        unbounded memory growth.

        Production note: In Redis, this is handled natively with key TTLs.
        """
        ttl = settings.SESSION_TTL_SECONDS
        now = time.time()
        cutoff = now - ttl

        expired_ids = [
            sid
            for sid, data in self._store.items()
            if data["last_active"] < cutoff
        ]

        for sid in expired_ids:
            del self._store[sid]
            log_info(f"Memory: session expired and evicted | session_id={sid} | ttl={ttl}s")


# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------
# Import this everywhere memory is needed — it's the same object every time.
#
# Usage:
#   from app.services.memory_service import memory_service
#   memory_service.add_exchange(session_id, user_msg, ai_reply)
#   history = memory_service.get_history(session_id)

memory_service = MemoryService()