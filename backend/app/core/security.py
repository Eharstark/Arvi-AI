"""
core/security.py — Security Layer
===================================
Handles everything related to request safety:
  - Input sanitization (clean user text before processing)
  - Rate limiting (prevent abuse / runaway API costs)
  - API key verification helpers (for future protected endpoints)

Why security here and not in routes?
  Routes should only handle HTTP concerns.
  Security logic belongs in its own layer so it's reusable and testable.

Future additions:
  - JWT token verification
  - OAuth2 / API key authentication
  - Redis-backed distributed rate limiting
  - IP blocklist / allowlist
"""

import re
import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

from app.core.config import settings


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

def sanitize_message(message: str) -> str:
    """
    Validate and clean a user's message before it reaches the AI.

    Steps:
      1. Check it's not empty
      2. Strip leading/trailing whitespace
      3. Enforce maximum length
      4. Remove invisible / dangerous control characters

    Args:
        message: Raw string from the user's request body.

    Returns:
        A cleaned, safe string ready for processing.

    Raises:
        HTTPException 400 if the message is empty or too long.
    """
    # Guard: empty or whitespace-only
    if not message or not message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # Strip outer whitespace
    message = message.strip()

    # Guard: too long
    max_len = settings.MAX_MESSAGE_LENGTH
    if len(message) > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds maximum length of {max_len} characters.",
        )

    # Remove non-printable control characters (keep newlines and tabs)
    # These can sometimes be used to manipulate prompts or logs
    message = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)

    # Collapse multiple consecutive whitespace (but preserve intentional newlines)
    message = re.sub(r"[ \t]{2,}", " ", message)

    return message


# ---------------------------------------------------------------------------
# In-Memory Rate Limiter
# ---------------------------------------------------------------------------
# This sliding-window rate limiter works per IP address.
# It's stored in Python memory — fast, no dependencies.
#
# LIMITATION: Resets when the server restarts.
# PRODUCTION UPGRADE: Replace with Redis + slowapi for multi-instance safety.
# ---------------------------------------------------------------------------

# Internal store: { "ip_address": [timestamp1, timestamp2, ...] }
_request_log: dict = defaultdict(list)


def check_rate_limit(
    request: Request,
    max_requests: int = None,
    window_seconds: int = 60,
) -> None:
    """
    Sliding-window rate limiter based on client IP address.

    How it works:
      - Keeps a list of request timestamps per IP
      - On each request, removes timestamps older than the window
      - If the count still exceeds the limit → raise 429

    Args:
        request:        The FastAPI Request object (used to get client IP).
        max_requests:   Max allowed requests per window (default from settings).
        window_seconds: Length of the rate-limit window in seconds.

    Raises:
        HTTPException 429 if the client is sending too many requests.
    """
    if max_requests is None:
        max_requests = settings.MAX_REQUESTS_PER_MINUTE

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - window_seconds

    # Purge timestamps outside the current window
    _request_log[client_ip] = [
        ts for ts in _request_log[client_ip] if ts > window_start
    ]

    # Check limit
    if len(_request_log[client_ip]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: max {max_requests} requests "
                f"per {window_seconds} seconds. Please slow down."
            ),
        )

    # Record this request
    _request_log[client_ip].append(now)


# ---------------------------------------------------------------------------
# API Key Verification (for future protected routes)
# ---------------------------------------------------------------------------

def verify_api_key(provided_key: str, expected_key: str) -> bool:
    """
    Timing-safe string comparison for API key validation.

    Using `hmac.compare_digest` prevents timing attacks where an attacker
    could determine the correct key by measuring response time differences.

    Args:
        provided_key: The key sent by the caller.
        expected_key: The correct key (from settings / database).

    Returns:
        True if keys match, False otherwise.

    Future usage in a route:
        if not verify_api_key(request.headers.get("X-API-Key"), settings.INTERNAL_API_KEY):
            raise HTTPException(status_code=401, detail="Invalid API key")
    """
    import hmac
    return hmac.compare_digest(
        provided_key.encode("utf-8"),
        expected_key.encode("utf-8"),
    )