"""
services/gemini_service.py — Gemini AI Integration Layer
==========================================================
Uses the NEW Google Gen AI SDK: google-genai (not google-generativeai)

Install with:
    pip install google-genai

The old package (google-generativeai) is deprecated.
The new package (google-genai) has a cleaner async-native API.

This is the ONLY file that talks to Gemini.
All other files call get_gemini_response() — they never touch the SDK directly.
"""

import asyncio
from typing import List, Optional, Tuple

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.chat_models import ConversationTurn, MessageRole
from app.utils.helpers import log_info, log_error, log_warning


# ---------------------------------------------------------------------------
# Module-level client (created once at startup, reused for all requests)
# ---------------------------------------------------------------------------
_client: Optional[genai.Client] = None


# ---------------------------------------------------------------------------
# Configuration — called once at startup from main.py
# ---------------------------------------------------------------------------

def configure_gemini() -> None:
    """
    Initialize the Gemini client using the new google-genai SDK.
    Called once at startup. Raises clearly if the API key is missing.
    """
    global _client

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your-"):
        raise ValueError(
            "GEMINI_API_KEY is missing or still set to the placeholder value.\n"
            "Add your real key to the .env file.\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )

    # Create the client — this is the new SDK pattern
    _client = genai.Client(api_key=settings.GEMINI_API_KEY)

    log_info(f"Gemini client ready | model={settings.GEMINI_MODEL}")


def _get_client() -> genai.Client:
    """Return the initialized client, or raise if startup was skipped."""
    if _client is None:
        raise RuntimeError(
            "Gemini client not initialized. "
            "configure_gemini() must be called at app startup."
        )
    return _client


# ---------------------------------------------------------------------------
# Main Response Function
# ---------------------------------------------------------------------------

async def get_gemini_response(
    user_message: str,
    history: Optional[List[ConversationTurn]] = None,
) -> Tuple[str, str]:
    """
    Send a message to Gemini and return (reply_text, model_name).

    Uses asyncio.to_thread() to run the synchronous SDK call without
    blocking FastAPI's async event loop.

    Args:
        user_message: The cleaned user message.
        history:      Optional prior conversation turns for memory context.

    Returns:
        Tuple of (ai_reply_string, model_name_string)

    Raises:
        HTTPException on all failure modes (quota, auth, API errors).
    """
    client = _get_client()

    # Build conversation history in the new SDK's Content format
    gemini_history = _build_history(history)

    log_info(
        f"Gemini request | model={settings.GEMINI_MODEL} | "
        f"history_turns={len(gemini_history)} | msg_len={len(user_message)}"
    )

    try:
        reply_text = await asyncio.to_thread(
            _call_gemini_sync,
            client,
            gemini_history,
            user_message,
        )
        log_info(f"Gemini response received | reply_len={len(reply_text)}")
        return reply_text, settings.GEMINI_MODEL

    except HTTPException:
        raise  # Already formatted — pass through

    except Exception as exc:
        log_error(f"Unexpected Gemini error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )


# ---------------------------------------------------------------------------
# Synchronous Gemini Call (runs inside asyncio.to_thread)
# ---------------------------------------------------------------------------

def _call_gemini_sync(
    client: genai.Client,
    history: list,
    user_message: str,
) -> str:
    """
    The actual blocking Gemini API call.

    New SDK pattern:
      - Use client.chats.create() to open a chat session with history
      - Call chat.send_message() with the current user message
      - Read response.text for the reply

    Args:
        client:       The initialized genai.Client instance.
        history:      Conversation history as a list of genai Content objects.
        user_message: The user's current message string.

    Returns:
        The AI reply as a plain string.
    """
    try:
        # Build generation config
        config = types.GenerateContentConfig(
            system_instruction=settings.SYSTEM_INSTRUCTION,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            temperature=settings.GEMINI_TEMPERATURE,
            top_p=settings.GEMINI_TOP_P,
            top_k=settings.GEMINI_TOP_K,
        )

        # Create a chat session with history preloaded
        chat = client.chats.create(
            model=settings.GEMINI_MODEL,
            config=config,
            history=history,
        )

        # Send the current message
        response = chat.send_message(user_message)

        # Extract reply text
        reply = response.text

        if not reply or not reply.strip():
            log_warning("Gemini returned empty response")
            return "I received your message but couldn't generate a response. Please try again."

        return reply.strip()

    # ── Error handling ─────────────────────────────────────────────────────

    except ClientError as exc:
        error_msg = str(exc).lower()
        log_error(f"Gemini ClientError: {exc}")

        if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service is temporarily busy. Please try again in a moment.",
            )
        if "api key" in error_msg or "permission" in error_msg or "403" in error_msg or "401" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service authentication failed. Please contact support.",
            )
        if "invalid" in error_msg or "400" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request sent to AI service.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an error. Please try again shortly.",
        )

    except APIError as exc:
        log_error(f"Gemini APIError: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service error. Please try again shortly.",
        )

    except Exception as exc:
        log_error(f"Unexpected error in _call_gemini_sync: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error communicating with AI service.",
        )


# ---------------------------------------------------------------------------
# History Builder
# ---------------------------------------------------------------------------

def _build_history(
    history: Optional[List[ConversationTurn]],
) -> list:
    """
    Convert our ConversationTurn objects into the new SDK's Content format.

    New SDK format:
        [
            types.Content(role="user",  parts=[types.Part(text="Hello")]),
            types.Content(role="model", parts=[types.Part(text="Hi there!")]),
        ]

    Rules:
      - Roles must be "user" or "model"
      - Must start with "user" and alternate
      - Trimmed to MAX_MEMORY_TURNS to manage context window

    Args:
        history: Optional list of our ConversationTurn objects.

    Returns:
        List of types.Content objects ready for client.chats.create(history=...)
    """
    if not history:
        return []

    role_map = {
        MessageRole.USER: "user",
        MessageRole.MODEL: "model",
    }

    # Keep only the most recent N turns
    trimmed = history[-settings.MAX_MEMORY_TURNS:]

    return [
        types.Content(
            role=role_map.get(turn.role, "user"),
            parts=[types.Part(text=turn.content)],
        )
        for turn in trimmed
    ]