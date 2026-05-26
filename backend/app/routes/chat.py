"""
routes/chat.py — Chat API Endpoints
=====================================
Defines all HTTP endpoints for the chatbot.

The route layer is intentionally THIN. Its only job is:
  1. Receive and validate HTTP requests
  2. Call the appropriate service functions
  3. Return HTTP responses

All real logic lives in services/ — not here.
This separation makes the code testable, maintainable, and easy to read.

Endpoints defined here:
  POST   /api/v1/chat                      → Main chat endpoint
  GET    /api/v1/chat/session/{session_id} → Get session info
  DELETE /api/v1/chat/session/{session_id} → Clear session memory
  GET    /api/v1/chat/stats                → Server stats (monitoring)
"""

import uuid
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.models.chat_models import (
    ChatRequest,
    ChatResponse,
    SessionInfoResponse,
    SessionClearResponse,
    ErrorResponse,
    IntentType,
    MessageRole,
)
from app.services.gemini_service import get_gemini_response
from app.services.intent_classifier import classify_intent, should_escalate, get_escalation_reply
from app.services.memory_service import memory_service
from app.core.security import sanitize_message, check_rate_limit
from app.utils.helpers import log_info, log_error


# ---------------------------------------------------------------------------
# Router Setup
# ---------------------------------------------------------------------------
# This router is mounted at /api/v1 in main.py
# So /chat here becomes /api/v1/chat in the full URL

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /chat — Main Chat Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the AI chatbot",
    description=(
        "Accepts a user message, classifies its intent, queries Gemini AI, "
        "maintains session memory, and returns the AI response. "
        "Send the returned `session_id` with every subsequent message "
        "to maintain conversation context."
    ),
    responses={
        200: {"description": "AI response returned successfully"},
        400: {"model": ErrorResponse, "description": "Invalid input (empty message, too long, etc.)"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Server error"},
        502: {"model": ErrorResponse, "description": "Gemini API error"},
    },
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Main chat handler — the orchestrator.

    Full request pipeline:
      1.  Rate limit check (prevent abuse)
      2.  Input sanitization (clean the message)
      3.  Session ID resolution (use existing or create new)
      4.  Intent classification (SIMPLE vs COMPLEX)
      5.  Escalation check (COMPLEX → return agent signal immediately)
      6.  Memory retrieval (load conversation history)
      7.  Gemini API call (generate AI response)
      8.  Memory update (save the exchange)
      9.  Response assembly and return
    """

    # ── Step 1: Rate Limiting ─────────────────────────────────────────────
    check_rate_limit(request)

    # ── Step 2: Input Sanitization ────────────────────────────────────────
    # Cleans the message and raises 400 if it's empty or too long
    clean_message = sanitize_message(body.message)

    # ── Step 3: Session ID Resolution ─────────────────────────────────────
    # If the frontend sends a session_id → use it (continuing a conversation)
    # If not → generate a new one (starting a fresh conversation)
    session_id = body.session_id or memory_service.generate_session_id()
    is_new_session = not memory_service.session_exists(session_id)

    log_info(
        f"Chat request | session={session_id} | "
        f"new_session={is_new_session} | msg_len={len(clean_message)}"
    )

    # ── Step 4: Intent Classification ─────────────────────────────────────
    intent = classify_intent(clean_message)

    # ── Step 5: Escalation Check ──────────────────────────────────────────
    if should_escalate(intent):
        log_info(f"Escalating COMPLEX request | session={session_id}")
        return ChatResponse(
            reply=get_escalation_reply(),
            intent=IntentType.COMPLEX,
            session_id=session_id,
            escalate=True,
            model_used=None,
            turn_count=memory_service.get_turn_count(session_id),
        )

    # ── Step 6: Memory Retrieval ──────────────────────────────────────────
    # Priority: use history from request body if provided,
    # otherwise load from server-side memory.
    history = body.history or memory_service.get_history(session_id)

    # ── Step 7: Gemini API Call ───────────────────────────────────────────
    # This is the async call to our Gemini service layer.
    # Errors here are handled inside gemini_service.py and re-raised as HTTPExceptions.
    try:
        reply, model_used = await get_gemini_response(
            user_message=clean_message,
            history=history,
        )
    except Exception:
        # Errors from gemini_service are already HTTPExceptions — let them propagate
        log_error(f"Gemini call failed | session={session_id}")
        raise

    # ── Step 8: Save Exchange to Memory ──────────────────────────────────
    memory_service.add_exchange(
        session_id=session_id,
        user_message=clean_message,
        model_reply=reply,
    )

    turn_count = memory_service.get_turn_count(session_id)
    log_info(
        f"Chat complete | session={session_id} | "
        f"intent={intent} | turns={turn_count} | model={model_used}"
    )

    # ── Step 9: Return Response ───────────────────────────────────────────
    return ChatResponse(
        reply=reply,
        intent=intent,
        session_id=session_id,
        escalate=False,
        model_used=model_used,
        turn_count=turn_count,
    )


# ---------------------------------------------------------------------------
# GET /chat/session/{session_id} — Session Info
# ---------------------------------------------------------------------------

@router.get(
    "/chat/session/{session_id}",
    response_model=SessionInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session info",
    description="Check whether a session exists and how many turns it has stored.",
)
async def get_session_info(session_id: str) -> SessionInfoResponse:
    """
    Return metadata about a conversation session.

    Useful for the frontend to check if a session is still alive
    after a page refresh or app restart.
    """
    exists = memory_service.session_exists(session_id)
    turn_count = memory_service.get_turn_count(session_id)

    return SessionInfoResponse(
        session_id=session_id,
        exists=exists,
        turn_count=turn_count,
        message=(
            f"Session has {turn_count} stored turns."
            if exists
            else "Session not found or has expired."
        ),
    )


# ---------------------------------------------------------------------------
# DELETE /chat/session/{session_id} — Clear Session Memory
# ---------------------------------------------------------------------------

@router.delete(
    "/chat/session/{session_id}",
    response_model=SessionClearResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear session memory",
    description=(
        "Delete all conversation history for a session. "
        "Call this when the user starts a new chat or logs out."
    ),
)
async def clear_session(session_id: str) -> SessionClearResponse:
    """
    Clear all stored conversation history for the given session_id.

    The session_id itself is not invalidated — the user can continue
    chatting with the same ID, but the AI will have no memory of prior messages.
    """
    cleared = memory_service.clear_session(session_id)
    return SessionClearResponse(
        success=cleared,
        session_id=session_id,
        message=(
            f"Session '{session_id}' cleared successfully."
            if cleared
            else f"Session '{session_id}' was not found (may have already expired)."
        ),
    )


# ---------------------------------------------------------------------------
# GET /chat/stats — Server Stats (useful for monitoring)
# ---------------------------------------------------------------------------

@router.get(
    "/chat/stats",
    status_code=status.HTTP_200_OK,
    summary="Server memory stats",
    description="Returns the number of active sessions in memory. Useful for monitoring.",
    tags=["Monitoring"],
)
async def get_stats() -> dict:
    """
    Return basic server statistics for monitoring dashboards.

    In production, protect this endpoint with authentication.
    """
    return {
        "active_sessions": memory_service.get_active_session_count(),
        "memory_storage": "in-process (upgrade to Redis for production)",
        "ai_provider": "Google Gemini",
    }