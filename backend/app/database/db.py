"""
database/db.py — Database Engine, Session, and Models
=======================================================
Sets up the async SQLAlchemy database connection.

Current state: SQLite (file-based, zero-config — perfect for development).
Production upgrade: Change DATABASE_URL in .env to a PostgreSQL connection string.
  Everything in this file continues to work unchanged.

SQLite connection string (dev):
  sqlite:///./chatbot.db

PostgreSQL connection string (production):
  postgresql+asyncpg://user:password@localhost:5432/chatbot_db

What's defined here:
  - Async engine (the database connection pool)
  - Session factory (creates DB sessions for each request)
  - Base class (all ORM models inherit from this)
  - init_db() (creates tables on startup)
  - get_db() (FastAPI dependency for injecting DB sessions into routes)

Future ORM models (add to this file or separate files in database/):
  - ConversationLog (persistent message storage)
  - User (auth accounts)
  - Feedback (thumbs up/down on responses)
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.core.config import settings
from app.utils.helpers import log_info, log_error


# ---------------------------------------------------------------------------
# Convert DB URL to Async-Compatible Format
# ---------------------------------------------------------------------------

def _to_async_url(url: str) -> str:
    """
    Convert a standard database URL to its async driver equivalent.

    SQLAlchemy async requires async-specific drivers:
      sqlite:///        → sqlite+aiosqlite:///    (uses aiosqlite)
      postgresql://     → postgresql+asyncpg://   (uses asyncpg)
    """
    if "sqlite" in url and "aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


_async_db_url = _to_async_url(settings.DATABASE_URL)


# ---------------------------------------------------------------------------
# Async Database Engine
# ---------------------------------------------------------------------------
# The engine manages the connection pool.
# echo=True prints all SQL queries — very useful for debugging, disable in prod.

_connect_args = {}
if "sqlite" in _async_db_url:
    # SQLite-specific: allow use from multiple threads (needed for async)
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    _async_db_url,
    echo=settings.DEBUG,        # SQL query logging — set DEBUG=False in production
    future=True,
    connect_args=_connect_args,
)


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
# async_sessionmaker creates database sessions on demand.
# expire_on_commit=False keeps objects accessible after a commit.

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Base Model Class
# ---------------------------------------------------------------------------
# All SQLAlchemy ORM table definitions inherit from this.

class Base(DeclarativeBase):
    """
    Base class for all database models.

    Example of a future ConversationLog model:

        from sqlalchemy import Column, Integer, String, Text, DateTime, func

        class ConversationLog(Base):
            __tablename__ = "conversation_logs"

            id         = Column(Integer, primary_key=True, index=True)
            session_id = Column(String(100), index=True, nullable=False)
            role       = Column(String(10), nullable=False)    # "user" or "model"
            content    = Column(Text, nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now())

    To activate: import ConversationLog here so Base.metadata knows about it,
    then run init_db() to create the table.
    """
    pass


# ---------------------------------------------------------------------------
# Startup: Table Creation
# ---------------------------------------------------------------------------

async def init_db() -> None:
    """
    Create all database tables on startup (if they don't already exist).

    Safe to call multiple times — SQLAlchemy's CREATE TABLE IF NOT EXISTS
    means existing tables are never dropped or modified.

    Production note: Once you add migrations (Alembic), replace this
    with `alembic upgrade head` and remove this function.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log_info(f"Database tables initialized | url={_async_db_url}")
    except Exception as exc:
        log_error(f"Database initialization error: {exc}")
        # Don't crash the app — database is optional until models are added.
        log_info("Continuing without database (no ORM models defined yet).")


# ---------------------------------------------------------------------------
# FastAPI Dependency: Per-Request DB Session
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides one database session per request.

    Automatically:
      - Opens a session at the start of the request
      - Commits on success
      - Rolls back on error
      - Closes the session when done

    Usage in a route:
        from sqlalchemy.ext.asyncio import AsyncSession
        from fastapi import Depends
        from app.database.db import get_db

        @router.get("/something")
        async def my_route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(ConversationLog))
            logs = result.scalars().all()
            return logs
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()