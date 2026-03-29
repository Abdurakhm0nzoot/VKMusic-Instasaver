"""Music search handlers — /song, /artist, /top, and text search."""

import logging
import math
import os

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile

from database.engine import async_session
from database.crud import (
    get_or_create_user,
    check_download_limit,
    increment_downloads,
)
from services.music_service import music_service, Track
from services.cache_service import cache_service
from keyboards.inline import search_results_kb, track_actions_kb
from config import config
from utils.helpers import format_duration, truncate
from utils.i18n import t

logger = logging.getLogger(__name__)
router = Router(name="music_search")

# In-memory search results cache (user_id -> search data)
_search_cache: dict[int, dict] = {}

TRACKS_PER_PAGE = 8


def _format_results(tracks: list[Track], page: int) -> str:
    """Format a page of tracks as numbered list matching user's layout."""
    lines = []
    start = page * TRACKS_PER_PAGE
    for i, track in enumerate(tracks):
        num = start + i + 1
        duration_str = format_duration(track.duration)
        title = truncate(track.title, 35)
        artist = truncate(track.artist, 25)
        # Mocking views and bitrate to match screenshot aesthetic since API doesn't provide them
        lines.append(f"{num}. {artist} – {title} {duration_str} {39.9}M 320k")
    return "\n".join(lines)


async def _do_search(
    message: Message, query: str, bot: Bot
) -> None:
    """Execute music search and display results."""
    async with async_session() as session:
        user = await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
        )
        lang = user.language

    # Send searching status
    status_msg = await message.answer(
        t("searching", lang), parse_mode="HTML"
    )

    # Search for tracks
    all_tracks = await music_service.search(query, count=50)

    if not all_tracks:
        await status_msg.edit_text(
            t("search_empty", lang, query=query),
            parse_mode="HTML",
        )
        return

    # Cache results for this user
    _search_cache[message.from_user.id] = {
        "query": query,
        "tracks": all_tracks,
    }

    # Show first page
    page = 0
    page_tracks = all_tracks[:TRACKS_PER_PAGE]
    total_pages = math.ceil(len(all_tracks) / TRACKS_PER_PAGE)

    results_text = _format_results(page_tracks, page)
    
    # Theme text modification, basic map
    theme_bullet = "🔎" if user.theme != "android" else "🍃"
    if user.theme == "pink": theme_bullet = "💗"
    elif user.theme == "vector": theme_bullet = "👾"
    
    text = (
        f"{theme_bullet} <b>{query}</b>\n"
        f"Результаты {page * TRACKS_PER_PAGE + 1}-{page * TRACKS_PER_PAGE + len(page_tracks)} из {len(all_tracks)}\n\n"
        f"<code>{results_text}</code>"
    )

    kb = search_results_kb(
        query=query,
        page=page,
        total_pages=total_pages,
        track_count=len(page_tracks),
        lang=lang,
    )

    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ─── Commands ───


@router.message(F.text.startswith("/song"))
async def cmd_song(message: Message, bot: Bot) -> None:
    """Handle /song <query> — search by song name."""
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        async with async_session() as session:
            user = await get_or_create_user(session, message.from_user.id)
            lang = user.language
        await message.answer(t("search_prompt", lang), parse_mode="HTML")
        return

    query = parts[1].strip()
    await _do_search(message, query, bot)


@router.message(F.text.startswith("/artist"))
async def cmd_artist(message: Message, bot: Bot) -> None:
    """Handle /artist <name> — search by artist name."""
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        async with async_session() as session:
            user = await get_or_create_user(session, message.from_user.id)
            lang = user.language
        await message.answer(t("artist_prompt", lang), parse_mode="HTML")
        return

    query = parts[1].strip()
    await _do_search(message, query, bot)


@router.message(F.text.startswith("/top"))
async def cmd_top(message: Message, bot: Bot) -> None:
    """Handle /top — show popular tracks."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Топ за день", callback_data="top_search:day"),
            InlineKeyboardButton(text="Топ за месяц", callback_data="top_search:month"),
        ]
    ])
    await message.answer("Выберите период:", reply_markup=kb)

@router.callback_query(F.data.startswith("top_search:"))
async def cb_top_search(callback: CallbackQuery, bot: Bot) -> None:
    """Execute top search based on selected period."""
    period = callback.data.split(":")[1]
    query = "top hits today" if period == "day" else "top hits month"
    
    await callback.message.delete()
    await _do_search(callback.message, query, bot)


# ─── Reply keyboard button for search ───

@router.message(F.text.in_([
    "🎵 Поиск музыки", "🎵 Search Music", "🎵 Musiqa qidirish",
]))
async def btn_search(message: Message) -> None:
    """Handle search button press from reply keyboard."""
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language
    await message.answer(t("search_prompt", lang), parse_mode="HTML")


# ─── Universal text search (Google-like) ───

@router.message(F.text & ~F.text.startswith("/"))
async def universal_search(message: Message, bot: Bot) -> None:
    """
    If user sends plain text (not a command, not a URL),
    treat it as a music search query.
    """
    text = message.text.strip()

    # Skip if it's a reply keyboard button
    known_buttons = [
        "🎵", "📥", "📋", "⚙️",
    ]
    if any(text.startswith(btn) for btn in known_buttons):
        return

    # Skip URLs (handled by downloader)
    if text.startswith("http://") or text.startswith("https://"):
        return

    # Skip very short queries
    if len(text) < 2:
        return

    await _do_search(message, text, bot)


def get_search_cache(user_id: int) -> dict | None:
    """Get cached search results for a user. Used by callbacks."""
    return _search_cache.get(user_id)


def clear_search_cache(user_id: int) -> None:
    """Clear cached search results for a user."""
    _search_cache.pop(user_id, None)
