"""Async Database Session Management.

Provides async engine, session factory, and dependency injection
for FastAPI using SQLAlchemy 2.0 patterns.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from autosre.db.models import Base


# Default to SQLite for development
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./autosre.db"

# Module-level engine and session factory
_engine: Optional[AsyncEngine] = None
_async_session: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """Get database URL from environment or use default."""
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    
    # Convert postgres:// to postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    return url


def get_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Get or create the async database engine.
    
    Args:
        database_url: Optional database URL. If not provided, uses
                     DATABASE_URL env var or default SQLite.
    
    Returns:
        AsyncEngine instance (singleton pattern).
    """
    global _engine
    
    if _engine is None:
        url = database_url or get_database_url()
        
        # Engine options
        engine_kwargs = {
            "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
        }
        
        # Use NullPool for SQLite to avoid threading issues
        if "sqlite" in url:
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # PostgreSQL connection pool settings
            engine_kwargs["pool_size"] = int(os.getenv("DATABASE_POOL_SIZE", "5"))
            engine_kwargs["max_overflow"] = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_recycle"] = 300
        
        _engine = create_async_engine(url, **engine_kwargs)
    
    return _engine


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Get the async session factory.
    
    Returns:
        async_sessionmaker configured for the current engine.
    """
    global _async_session
    
    if _async_session is None:
        engine = get_engine()
        _async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    
    return _async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.
    
    Yields a database session and ensures proper cleanup.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_async_session()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions.
    
    Use this when you need a session outside of FastAPI dependency injection.
    
    Usage:
        async with get_db_context() as db:
            result = await db.execute(query)
    """
    session_factory = get_async_session()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(drop_existing: bool = False) -> None:
    """Initialize the database, creating all tables.
    
    Args:
        drop_existing: If True, drops all existing tables first.
                      Use with caution!
    """
    engine = get_engine()
    
    async with engine.begin() as conn:
        if drop_existing:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine and clean up connections."""
    global _engine, _async_session
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session = None


def reset_engine() -> None:
    """Reset the engine (useful for testing with different databases)."""
    global _engine, _async_session
    _engine = None
    _async_session = None
