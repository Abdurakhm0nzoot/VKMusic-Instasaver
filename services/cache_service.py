"""Smart Cache service — maps content hashes to Telegram file_ids."""

import hashlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import get_cached_file, save_cached_file

logger = logging.getLogger(__name__)


class CacheService:
    """Manages the content_hash ↔ file_id cache in the database."""

    @staticmethod
    def generate_hash(identifier: str) -> str:
        """Generate a SHA-256 hash for a URL, track ID, or other identifier."""
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    async def get_file_id(
        self, session: AsyncSession, content_hash: str
    ) -> str | None:
        """Look up a cached Telegram file_id. Returns file_id or None."""
        entry = await get_cached_file(session, content_hash)
        if entry:
            logger.debug(f"Cache HIT: {content_hash[:16]}...")
            return entry.telegram_file_id
        logger.debug(f"Cache MISS: {content_hash[:16]}...")
        return None

    async def save_file_id(
        self,
        session: AsyncSession,
        content_hash: str,
        telegram_file_id: str,
        file_type: str,
        title: str | None = None,
        artist: str | None = None,
        duration: int | None = None,
    ) -> None:
        """Save a Telegram file_id to the cache."""
        try:
            await save_cached_file(
                session=session,
                content_hash=content_hash,
                telegram_file_id=telegram_file_id,
                file_type=file_type,
                title=title,
                artist=artist,
                duration=duration,
            )
            logger.debug(f"Cached file_id for {content_hash[:16]}...")
        except Exception as e:
            logger.error(f"Failed to cache file_id: {e}")


cache_service = CacheService()
