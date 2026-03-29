"""Async SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import config
from database.models import Base

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


from sqlalchemy import text

async def init_db() -> None:
    """Create all tables on startup and try to apply simple migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Simple auto-migration for newly added columns
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN theme VARCHAR(50) DEFAULT 'pixel'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN bitrate_preview BOOLEAN DEFAULT TRUE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN likes_buttons BOOLEAN DEFAULT TRUE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN audio_caption VARCHAR(100) DEFAULT 'Ссылка на бота'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN advanced_search BOOLEAN DEFAULT TRUE"))
        except Exception:
            pass



async def get_session() -> AsyncSession:
    """Create and return a new async session."""
    async with async_session() as session:
        return session
