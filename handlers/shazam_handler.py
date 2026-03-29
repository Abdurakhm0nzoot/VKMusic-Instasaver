"""Shazam handler — recognizes music from voice messages, audio, video notes."""

import logging
import os

from aiogram import Router, F, Bot
from aiogram.types import Message

from database.engine import async_session
from database.crud import get_or_create_user
from services.shazam_service import shazam_service
from keyboards.inline import shazam_result_kb
from config import config
from utils.i18n import t

logger = logging.getLogger(__name__)
router = Router(name="shazam")


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Recognize music from voice messages."""
    await _recognize(message, bot, "voice")


@router.message(F.audio)
async def handle_audio_recognition(message: Message, bot: Bot) -> None:
    """Recognize music from audio files (forwarded songs, etc.)."""
    # Only process short audio files (likely Shazam requests)
    if message.audio.duration and message.audio.duration > 120:
        return
    await _recognize(message, bot, "audio")


@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot) -> None:
    """Recognize music from video notes (circles)."""
    await _recognize(message, bot, "video_note")


async def _recognize(
    message: Message, bot: Bot, media_type: str
) -> None:
    """Common recognition logic."""
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        lang = user.language

    # Send status
    status_msg = await message.answer(
        t("shazam_listening", lang), parse_mode="HTML"
    )

    # Download the file from Telegram
    try:
        if media_type == "voice":
            file_obj = await bot.get_file(message.voice.file_id)
        elif media_type == "audio":
            file_obj = await bot.get_file(message.audio.file_id)
        elif media_type == "video_note":
            file_obj = await bot.get_file(message.video_note.file_id)
        else:
            return

        # Download to local file
        download_dir = config.DOWNLOAD_DIR
        download_dir.mkdir(parents=True, exist_ok=True)

        ext = "ogg" if media_type == "voice" else "mp4"
        local_path = str(download_dir / f"shazam_{message.from_user.id}.{ext}")

        await bot.download_file(file_obj.file_path, local_path)

    except Exception as e:
        logger.error(f"Failed to download file for Shazam: {e}")
        await status_msg.edit_text(t("error_generic", lang))
        return

    # Recognize
    try:
        result = await shazam_service.recognize(local_path)

        if result is None:
            await status_msg.edit_text(
                t("shazam_not_found", lang), parse_mode="HTML"
            )
            return

        album = result.album or "—"
        text = t(
            "shazam_found", lang,
            artist=result.artist,
            title=result.title,
            album=album,
        )

        kb = shazam_result_kb(result.artist, result.title, lang)

        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        logger.error(f"Shazam recognition error: {e}")
        await status_msg.edit_text(t("shazam_not_found", lang), parse_mode="HTML")

    finally:
        # Cleanup
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
            # Also remove WAV if created
            wav_path = os.path.splitext(local_path)[0] + ".wav"
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except OSError:
            pass
