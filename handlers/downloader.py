"""URL downloader handler — catches links to Instagram, TikTok, YouTube."""

import logging
import os

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile

from database.engine import async_session
from database.crud import (
    get_or_create_user,
    check_download_limit,
    increment_downloads,
)
from services.downloader_service import downloader_service, DownloadResult
from services.cache_service import cache_service
from config import config
from utils.helpers import extract_url, detect_platform, format_filesize
from utils.i18n import t
from utils.helpers import url_cache
from keyboards.inline import video_actions_kb

logger = logging.getLogger(__name__)
router = Router(name="downloader")


@router.message(F.text.regexp(r"https?://"))
async def handle_url(message: Message, bot: Bot) -> None:
    """Detect URLs and download media from supported platforms."""
    url = extract_url(message.text)
    if not url:
        return

    platform = detect_platform(url)
    if not platform:
        return  # Not a supported platform

    # Get user info
    async with async_session() as session:
        user = await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
        )
        lang = user.language

        # Check download limit
        allowed = await check_download_limit(
            session, message.from_user.id, config.MAX_FREE_DOWNLOADS
        )
        if not allowed:
            await message.answer(
                t("limit_reached", lang,
                  count=user.daily_downloads,
                  max=config.MAX_FREE_DOWNLOADS),
                parse_mode="HTML",
            )
            return

    # Send "downloading" status
    platform_name = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube"}.get(platform, platform)
    status_msg = await message.answer(
        t("downloading_media", lang, platform=platform_name),
        parse_mode="HTML",
    )

    # ── Store URL for MP3/Thumbnail buttons ──
    cache_url(url)

    # ── Smart Cache check ──
    content_hash = cache_service.generate_hash(url)

    async with async_session() as session:
        cached_file_id = await cache_service.get_file_id(session, content_hash)

    if cached_file_id:
        try:
            bot_info = await bot.get_me()
            caption_text = f"@{bot_info.username} orqali yuklab olindi"

            await bot.send_video(
                chat_id=message.chat.id,
                video=cached_file_id,
                caption=caption_text,
                reply_to_message_id=message.message_id,
                reply_markup=video_actions_kb(url, lang),
            )
            await status_msg.delete()
            async with async_session() as session:
                await increment_downloads(session, message.from_user.id)
            return
        except Exception:
            pass  # file_id invalid, fall through

    # ── Download ──
    result: DownloadResult | None = None
    try:
        result = await downloader_service.download_video(url)
    except Exception as e:
        logger.error(f"Download exception: {e}")

    if result is None:
        await status_msg.edit_text(t("download_failed", lang), parse_mode="HTML")
        return

    # ── Check file size ──
    if result.filesize > downloader_service.MAX_FILESIZE:
        await status_msg.edit_text(
            t("download_too_large", lang) + f"\n📦 {format_filesize(result.filesize)}",
            parse_mode="HTML",
        )
        downloader_service.cleanup(result.file_path)
        return

    # ── Send file ──
    try:
        file = FSInputFile(result.file_path)
        
        bot_info = await bot.get_me()
        caption_text = f"@{bot_info.username} orqali yuklab olindi"

        sent = await bot.send_video(
            chat_id=message.chat.id,
            video=file,
            caption=caption_text,
            duration=result.duration,
            reply_to_message_id=message.message_id,
            parse_mode="HTML",
            reply_markup=video_actions_kb(url, lang),
        )

        # Save to Smart Cache
        file_id = sent.video.file_id if sent.video else None
        if file_id:
            async with async_session() as session:
                await cache_service.save_file_id(
                    session=session,
                    content_hash=content_hash,
                    telegram_file_id=file_id,
                    file_type="video",
                    title=result.title,
                    duration=result.duration,
                )

        async with async_session() as session:
            await increment_downloads(session, message.from_user.id)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Failed to send file: {e}")
        await status_msg.edit_text(t("download_failed", lang), parse_mode="HTML")

    finally:
        if result:
            downloader_service.cleanup(result.file_path)
