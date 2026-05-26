"""
core/config.py — Centralized Configuration
============================================
Every environment variable the app needs is declared here.
Pydantic-settings reads values from the .env file automatically.

Why centralize config?
  - One place to see all settings
  - Automatic type validation (wrong type = clear error at startup)
  - Easy to switch between dev / staging / production

Usage anywhere in the codebase:
    from app.core.config import settings
    print(settings.GEMINI_API_KEY)
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or the .env file.

    Pydantic validates types automatically:
      - If GEMINI_API_KEY is missing → startup fails with a clear error
      - If DEBUG is "true" → automatically cast to bool True
    """

    # ── App Metadata ─────────────────────────────────────────────────────────
    APP_NAME: str = "Gemini AI Chatbot API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"    # development | staging | production
    DEBUG: bool = True

    # ── Gemini AI Configuration ───────────────────────────────────────────────
    GEMINI_API_KEY: str                             # Required — must be in .env
    GEMINI_MODEL: str = "gemini-1.5-flash"          # Fast, capable, free-tier friendly
    # Available models:
    #   gemini-1.5-flash     → fastest, cheapest (recommended for chatbots)
    #   gemini-1.5-pro       → smarter, better reasoning (higher cost)
    #   gemini-2.0-flash-exp → experimental, latest features

    GEMINI_MAX_OUTPUT_TOKENS: int = 1024    # Max tokens in Gemini's reply
    GEMINI_TEMPERATURE: float = 0.75        # Creativity: 0.0 = robotic, 1.0 = wild
    GEMINI_TOP_P: float = 0.95             # Nucleus sampling (fine-tuning diversity)
    GEMINI_TOP_K: int = 40                 # Top-K sampling

    # ── System Instruction ────────────────────────────────────────────────────
    # This is the "personality prompt" — defines how Gemini behaves.
    # Customize this for your product's brand voice.
    SYSTEM_INSTRUCTION: str = (
        "You are a helpful, friendly, and professional AI assistant. "
        "You provide clear, accurate, and concise answers. "
        "When you don't know something, you say so honestly rather than guessing. "
        "You maintain a warm, professional tone and stay focused on the user's needs. "
        "You never fabricate facts or URLs."
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    # List of frontend origins allowed to call this API.
    # IMPORTANT: Remove '*' and set your real domain in production.
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "*",
    ]

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    MAX_REQUESTS_PER_MINUTE: int = 60       # Per IP address
    MAX_MESSAGE_LENGTH: int = 2000          # Characters per user message

    # ── Session Memory ────────────────────────────────────────────────────────
    MAX_MEMORY_TURNS: int = 10              # Max conversation turns per session
    SESSION_TTL_SECONDS: int = 3600         # Sessions expire after 1 hour

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite for development — zero setup needed.
    # Swap to PostgreSQL for production by changing this one line.
    DATABASE_URL: str = "sqlite:///./chatbot.db"
    # PostgreSQL example:
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@host:5432/chatbot"

    class Config:
        env_file = ".env"               # Read from .env in the project root
        env_file_encoding = "utf-8"
        case_sensitive = True           # GEMINI_API_KEY ≠ gemini_api_key


# ── Singleton — import this everywhere ───────────────────────────────────────
# This object is created once at import time and reused across the app.
settings = Settings()