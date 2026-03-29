"""Playlist handler — /my command."""

import logging

from aiogram import Router, F
from aiogram.types import Message

from database.engine import async_session
from database.crud import get_or_create_user, get_playlist
from keyboards.inline import playlist_kb
from utils.helpers import truncate
from utils.i18n import t
import math

logger = logging.getLogger(__name__)
router = Router(name="playlist")


@router.message(F.text.startswith("/my"))
async def cmd_playlist(message: Message) -> None:
    """Handle /my — show personal playlist."""
    await _show_playlist(message, page=0)


@router.message(F.text.in_([
    "📋 Плейлист", "📋 Playlist", "📋 Pleylist",
]))
async def btn_playlist(message: Message) -> None:
    """Handle playlist button from reply keyboard."""
    await _show_playlist(message, page=0)


async def _show_playlist(message: Message, page: int = 0) -> None:
    """Display user's playlist with pagination."""
    per_page = 8

    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language
        items, total = await get_playlist(session, message.from_user.id, page, per_page)

    if not items or total == 0:
        await message.answer(t("playlist_empty", lang), parse_mode="HTML")
        return

    # Format track list
    tracks_text = ""
    for i, item in enumerate(items):
        num = page * per_page + i + 1
        artist = truncate(item.track_artist, 25)
        title = truncate(item.track_title, 35)
        tracks_text += f"{num}. <b>{artist}</b> — {title}\n"

    total_pages = math.ceil(total / per_page)
    text = t("playlist_title", lang, count=total, tracks=tracks_text)

    kb = playlist_kb(items, page, total_pages, lang)

    await message.answer(text, parse_mode="HTML", reply_markup=kb)
