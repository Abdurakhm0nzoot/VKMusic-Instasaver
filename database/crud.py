"""CRUD operations for database models."""

from datetime import date, datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, FileCache, PlaylistItem


# ───────────────────────── User ─────────────────────────


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    """Get existing user or create a new one."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


async def update_user_language(
    session: AsyncSession, telegram_id: int, lang: str
) -> None:
    """Update user's language preference."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        user.language = lang
        await session.commit()


async def update_user_quality(
    session: AsyncSession, telegram_id: int, quality: int
) -> None:
    """Update user's audio quality preference."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        user.audio_quality = quality
        await session.commit()


async def update_user_setting(
    session: AsyncSession, telegram_id: int, setting_name: str, value: any
) -> None:
    """Update an arbitrary user setting (theme, bitrate_preview, etc)."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user and hasattr(user, setting_name):
        setattr(user, setting_name, value)
        await session.commit()


async def check_download_limit(
    session: AsyncSession, telegram_id: int, max_downloads: int
) -> bool:
    """Check if user has remaining downloads. Returns True if allowed."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return True

    if user.is_premium:
        return True

    today = date.today()
    if user.last_download_date != today:
        # Reset daily counter
        user.daily_downloads = 0
        user.last_download_date = today
        await session.commit()
        return True

    return user.daily_downloads < max_downloads


async def increment_downloads(
    session: AsyncSession, telegram_id: int
) -> int:
    """Increment daily download counter. Returns new count."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return 0

    today = date.today()
    if user.last_download_date != today:
        user.daily_downloads = 1
        user.last_download_date = today
    else:
        user.daily_downloads += 1

    await session.commit()
    return user.daily_downloads


# ───────────────────────── FileCache ─────────────────────────


async def get_cached_file(
    session: AsyncSession, content_hash: str
) -> FileCache | None:
    """Look up a cached Telegram file_id by content hash."""
    stmt = select(FileCache).where(FileCache.content_hash == content_hash)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def save_cached_file(
    session: AsyncSession,
    content_hash: str,
    telegram_file_id: str,
    file_type: str,
    title: str | None = None,
    artist: str | None = None,
    duration: int | None = None,
) -> FileCache:
    """Save a Telegram file_id to cache."""
    cache_entry = FileCache(
        content_hash=content_hash,
        telegram_file_id=telegram_file_id,
        file_type=file_type,
        title=title,
        artist=artist,
        duration=duration,
    )
    session.add(cache_entry)
    await session.commit()
    await session.refresh(cache_entry)
    return cache_entry


# ───────────────────────── Playlist ─────────────────────────


async def add_to_playlist(
    session: AsyncSession,
    telegram_id: int,
    track_title: str,
    track_artist: str,
    track_url: str | None = None,
    file_cache_id: int | None = None,
) -> PlaylistItem:
    """Add a track to user's playlist."""
    # Get user
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise ValueError(f"User {telegram_id} not found")

    item = PlaylistItem(
        user_id=user.id,
        track_title=track_title,
        track_artist=track_artist,
        track_url=track_url,
        file_cache_id=file_cache_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_playlist(
    session: AsyncSession, telegram_id: int, page: int = 0, per_page: int = 8
) -> tuple[list[PlaylistItem], int]:
    """Get user's playlist with pagination. Returns (items, total_count)."""
    # Get user
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return [], 0

    # Count total
    count_stmt = (
        select(PlaylistItem)
        .where(PlaylistItem.user_id == user.id)
    )
    count_result = await session.execute(count_stmt)
    total = len(count_result.scalars().all())

    # Get page
    stmt = (
        select(PlaylistItem)
        .where(PlaylistItem.user_id == user.id)
        .order_by(PlaylistItem.added_at.desc())
        .offset(page * per_page)
        .limit(per_page)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def remove_from_playlist(
    session: AsyncSession, telegram_id: int, item_id: int
) -> bool:
    """Remove a track from user's playlist. Returns True if deleted."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return False

    stmt = delete(PlaylistItem).where(
        PlaylistItem.id == item_id,
        PlaylistItem.user_id == user.id,
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0
