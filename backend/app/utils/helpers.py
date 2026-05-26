"""
utils/helpers.py — Shared Utility Functions
=============================================
General-purpose helper functions used across the application.

Why have a helpers file?
  Service files should stay focused on their domain logic.
  Cross-cutting concerns like logging and text processing go here,
  keeping everything else clean.

Contents:
  - Structured logger setup (all modules import from here)
  - Timestamp helpers
  - Text processing utilities
  - Retry decorator scaffold (for future production use)
"""

import logging
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Logger Configuration
# ---------------------------------------------------------------------------
# We configure one logger here and every module imports log_info / log_error.
# This means log format is consistent across the entire application.

def _setup_logger() -> logging.Logger:
    """
    Create and configure the application-wide logger.

    Log format: 2024-01-15 10:30:45 | INFO     | Your message here
    """
    logger = logging.getLogger("gemini_chatbot")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


_logger = _setup_logger()


# ── Logging shortcuts ─────────────────────────────────────────────────────
# Import these instead of using logging directly — keeps code cleaner.

def log_info(message: str) -> None:
    """Log an informational message (normal operations)."""
    _logger.info(message)

def log_error(message: str) -> None:
    """Log an error message (something went wrong)."""
    _logger.error(message)

def log_warning(message: str) -> None:
    """Log a warning (unexpected but recoverable situation)."""
    _logger.warning(message)

def log_debug(message: str) -> None:
    """Log a debug message (detailed internal state — only visible in DEBUG mode)."""
    _logger.debug(message)


# ---------------------------------------------------------------------------
# Timestamp Utilities
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """
    Return the current UTC time as an ISO 8601 string.
    Example: "2024-01-15T10:30:45.123456+00:00"

    Use this for consistent timestamp fields in responses and logs.
    """
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp() -> float:
    """Return the current UTC time as a Unix timestamp (float seconds)."""
    return datetime.now(timezone.utc).timestamp()


# ---------------------------------------------------------------------------
# Text Utilities
# ---------------------------------------------------------------------------

def truncate(text: str, max_chars: int = 80, suffix: str = "...") -> str:
    """
    Truncate a string to max_chars, appending suffix if truncated.

    Used for safe logging of long strings (user messages, AI replies)
    without flooding the logs.

    Args:
        text:      The string to truncate.
        max_chars: Maximum number of characters to keep.
        suffix:    Characters appended when truncated.

    Returns:
        Truncated string with suffix, or the original if short enough.

    Example:
        truncate("Hello world this is a long sentence", max_chars=15)
        → "Hello world thi..."
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def word_count(text: str) -> int:
    """Return the approximate word count of a text string."""
    return len(text.split())


def is_question(text: str) -> bool:
    """
    Simple heuristic: does this text look like a question?

    Used as a lightweight signal in intent classification.
    """
    stripped = text.strip()
    return stripped.endswith("?") or stripped.lower().startswith(
        ("what", "who", "where", "when", "why", "how", "is ", "are ", "can ", "could ", "would ", "should ", "do ", "does ")
    )


# ---------------------------------------------------------------------------
# Retry Decorator (scaffold — for future use)
# ---------------------------------------------------------------------------

def with_retry(max_attempts: int = 3, delay_seconds: float = 1.0):
    """
    Decorator for retrying async functions on transient failures.

    SCAFFOLD — not yet wired to Gemini calls.
    Phase 2: Wrap get_gemini_response() with this for production resilience.

    Usage (future):
        @with_retry(max_attempts=3, delay_seconds=0.5)
        async def get_gemini_response(...):
            ...
    """
    import functools
    import asyncio

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    log_warning(
                        f"Retry {attempt}/{max_attempts} for '{func.__name__}': {exc}"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(delay_seconds * attempt)  # Exponential backoff
            raise last_error
        return wrapper
    return decorator