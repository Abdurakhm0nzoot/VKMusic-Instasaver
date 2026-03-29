"""Settings handler — /settings command."""

import logging
from datetime import date

from aiogram import Router, F
from aiogram.types import Message

from database.engine import async_session
from database.crud import get_or_create_user
from keyboards.inline import settings_kb
from config import config
from utils.i18n import t, get_language_flag
from utils.helpers import format_filesize

logger = logging.getLogger(__name__)
router = Router(name="settings")


@router.message(F.text.startswith("/settings"))
async def cmd_settings(message: Message) -> None:
    """Handle /settings — show settings panel."""
    await _show_settings(message)


@router.message(F.text.in_([
    "⚙️ Настройки", "⚙️ Settings", "⚙️ Sozlamalar",
]))
async def btn_settings(message: Message) -> None:
    """Handle settings button from reply keyboard."""
    await _show_settings(message)


async def _show_settings(message: Message) -> None:
    """Display settings panel with inline toggles."""
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language

        # Calculate downloads today
        today = date.today()
        downloads_today = user.daily_downloads if user.last_download_date == today else 0
        max_dl = config.MAX_FREE_DOWNLOADS

    flag = get_language_flag(lang)

    text = (
        t("settings_title", lang) + "\n\n"
        + t("settings_language", lang, lang=lang.upper(), flag=flag) + "\n"
        + t("settings_quality", lang, quality=user.audio_quality) + "\n"
        + t("settings_downloads", lang, count=downloads_today, max=max_dl)
    )

    kb = settings_kb(
        current_lang=lang,
        current_quality=user.audio_quality,
        lang=lang,
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb)
