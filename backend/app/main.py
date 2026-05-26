"""
main.py — FastAPI Application Entry Point
==========================================
This is where the backend server is born.

It does four things:
  1. Creates the FastAPI app instance
  2. Attaches middleware (CORS, future: logging, auth)
  3. Registers all route modules
  4. Runs startup / shutdown logic (DB init, Gemini config check)

Run this file with:
  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import chat
from app.database.db import init_db
from app.services.gemini_service import configure_gemini
from app.utils.helpers import log_info


# ---------------------------------------------------------------------------
# Lifespan — startup and shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything before `yield` runs once on startup.
    Everything after `yield` runs once on shutdown.
    """
    log_info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    log_info(f"Environment: {settings.ENVIRONMENT}")

    configure_gemini()
    log_info(f"Gemini configured | model={settings.GEMINI_MODEL}")

    await init_db()
    log_info("Database ready.")
    log_info("Backend is live and accepting requests.")
    yield

    log_info("Shutting down gracefully...")


# ---------------------------------------------------------------------------
# FastAPI App Instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-style AI Chatbot Backend — "
        "FastAPI + Gemini API + Session Memory"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Route Registration
# ---------------------------------------------------------------------------
app.include_router(
    chat.router,
    prefix="/api/v1",
    tags=["Chat"],
)


# ---------------------------------------------------------------------------
# Root & Health Check Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — confirms the server is alive."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ai_provider": "Google Gemini",
        "model": settings.GEMINI_MODEL,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check for load balancers and uptime monitors."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "ai_provider": "Google Gemini",
    }