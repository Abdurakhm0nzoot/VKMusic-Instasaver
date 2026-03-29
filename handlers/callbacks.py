"""Central callback query handler — processes all inline keyboard presses."""

import logging
import math
import os
from datetime import date

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile

from database.engine import async_session
from database.crud import (
    get_or_create_user,
    update_user_language,
    update_user_quality,
    check_download_limit,
    increment_downloads,
    add_to_playlist,
    remove_from_playlist,
    get_playlist,
)
from services.music_service import music_service
from services.cache_service import cache_service
from services.audio_tagger import tag_audio
from handlers.music_search import (
    get_search_cache,
    TRACKS_PER_PAGE,
    _format_results,
)
from keyboards.inline import (
    search_results_kb,
    track_actions_kb,
    settings_kb,
    playlist_kb,
)
from keyboards.reply import main_menu_kb
from config import config
from utils.helpers import truncate, get_cached_url
from utils.i18n import t, get_language_flag

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


# ───────────────────────── Track Selection (1-8) ─────────────────────────


@router.callback_query(F.data.startswith("track:"))
async def cb_track_select(callback: CallbackQuery, bot: Bot) -> None:
    """Handle track selection — download, tag, and send."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌")
        return

    page = int(parts[1])
    index = int(parts[2])

    cache = get_search_cache(callback.from_user.id)
    if not cache:
        await callback.answer("🔍 Поиск устарел. Повторите.", show_alert=True)
        return

    tracks = cache["tracks"]
    idx = page * TRACKS_PER_PAGE + index

    if idx >= len(tracks):
        await callback.answer("❌")
        return

    track = tracks[idx]

    # Check limit
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language
        quality = user.audio_quality

        allowed = await check_download_limit(
            session, callback.from_user.id, config.MAX_FREE_DOWNLOADS
        )
        if not allowed:
            await callback.answer(
                t("limit_reached", lang, count=user.daily_downloads, max=config.MAX_FREE_DOWNLOADS),
                show_alert=True,
            )
            return

    await callback.answer(t("sending_track", lang, num=index + 1))

    # ── Smart Cache check ──
    content_hash = cache_service.generate_hash(track.track_id or track.url)

    async with async_session() as session:
        cached_fid = await cache_service.get_file_id(session, content_hash)

    if cached_fid:
        try:
            await bot.send_audio(
                chat_id=callback.message.chat.id,
                audio=cached_fid,
                caption=t("song_sent", lang, artist=track.artist, title=track.title),
                parse_mode="HTML",
                reply_markup=track_actions_kb(content_hash, cache["query"], lang),
            )
            async with async_session() as session:
                await increment_downloads(session, callback.from_user.id)
            return
        except Exception:
            pass

    # ── Download track ──
    file_path = await music_service.download_track(track, quality)

    if not file_path or not os.path.exists(file_path):
        await callback.answer(t("download_failed", lang), show_alert=True)
        return

    try:
        # ── Audio Injection: write ID3 tags ──
        await tag_audio(
            file_path=file_path,
            title=track.title,
            artist=track.artist,
        )

        file = FSInputFile(file_path)
        sent = await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=file,
            performer=track.artist,
            title=track.title,
            duration=track.duration,
            caption=t("song_sent", lang, artist=track.artist, title=track.title),
            parse_mode="HTML",
            reply_markup=track_actions_kb(content_hash, cache["query"], lang),
        )

        # Cache file_id
        if sent.audio:
            async with async_session() as session:
                await cache_service.save_file_id(
                    session=session,
                    content_hash=content_hash,
                    telegram_file_id=sent.audio.file_id,
                    file_type="audio",
                    title=track.title,
                    artist=track.artist,
                    duration=track.duration,
                )

        async with async_session() as session:
            await increment_downloads(session, callback.from_user.id)

    except Exception as e:
        logger.error(f"Failed to send track: {e}")
        await callback.answer(t("download_failed", lang), show_alert=True)
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass


# ───────────────────────── Video → MP3 ─────────────────────────


@router.callback_query(F.data.startswith("vid2mp3:"))
async def cb_video_to_mp3(callback: CallbackQuery, bot: Bot) -> None:
    """Extract audio from a previously downloaded video."""
    url_hash = callback.data.split(":")[1]
    url = get_cached_url(url_hash)

    if not url:
        await callback.answer("⏳ Ссылка устарела. Отправь ссылку заново.", show_alert=True)
        return

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language
        quality = user.audio_quality

    await callback.answer("🎵 Извлекаю аудио...")

    from services.downloader_service import downloader_service
    result = await downloader_service.download_audio(url, quality)

    if not result:
        await callback.answer(t("download_failed", lang), show_alert=True)
        return

    try:
        # Tag the audio
        await tag_audio(file_path=result.file_path, title=result.title)

        file = FSInputFile(result.file_path)
        await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=file,
            title=result.title,
            duration=result.duration,
        )
    except Exception as e:
        logger.error(f"vid2mp3 failed: {e}")
    finally:
        downloader_service.cleanup(result.file_path)


# ───────────────────────── Video Thumbnail ─────────────────────────


@router.callback_query(F.data.startswith("vidthumb:"))
async def cb_video_thumbnail(callback: CallbackQuery, bot: Bot) -> None:
    """Send the video thumbnail as a photo."""
    url_hash = callback.data.split(":")[1]
    url = get_cached_url(url_hash)

    if not url:
        await callback.answer("⏳ Ссылка устарела.", show_alert=True)
        return

    await callback.answer("🖼 Загружаю обложку...")

    try:
        import yt_dlp

        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        thumb_url = info.get("thumbnail") if info else None

        if thumb_url:
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=thumb_url,
                caption=f"🖼 {info.get('title', '')}",
            )
        else:
            await callback.answer("🖼 Обложка не найдена", show_alert=True)

    except Exception as e:
        logger.error(f"Thumbnail extraction failed: {e}")
        await callback.answer("❌ Не удалось извлечь обложку", show_alert=True)


# ───────────────────────── Pagination ─────────────────────────


@router.callback_query(F.data.startswith("page:"))
async def cb_page(callback: CallbackQuery) -> None:
    """Handle search results pagination."""
    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌")
        return

    direction = parts[1]
    query = parts[2]
    current_page = int(parts[3])

    cache = get_search_cache(callback.from_user.id)
    if not cache:
        await callback.answer("🔍 Поиск устарел.", show_alert=True)
        return

    tracks = cache["tracks"]
    total_pages = math.ceil(len(tracks) / TRACKS_PER_PAGE)

    new_page = min(current_page + 1, total_pages - 1) if direction == "next" else max(current_page - 1, 0)

    start = new_page * TRACKS_PER_PAGE
    page_tracks = tracks[start:start + TRACKS_PER_PAGE]

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language

    text = t(
        "search_results", lang,
        start=start + 1, end=start + len(page_tracks),
        total=len(tracks), results=_format_results(page_tracks, new_page),
    )
    kb = search_results_kb(query, new_page, total_pages, len(page_tracks), lang)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ───────────────────────── Settings ─────────────────────────


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery) -> None:
    """Handle language change."""
    new_lang = callback.data.split(":")[1]

    async with async_session() as session:
        await update_user_language(session, callback.from_user.id, new_lang)
        user = await get_or_create_user(session, callback.from_user.id)

    flag = get_language_flag(new_lang)
    today = date.today()
    dl = user.daily_downloads if user.last_download_date == today else 0

    text = (
        t("settings_title", new_lang) + "\n\n"
        + t("settings_language", new_lang, lang=new_lang.upper(), flag=flag) + "\n"
        + t("settings_quality", new_lang, quality=user.audio_quality) + "\n"
        + t("settings_downloads", new_lang, count=dl, max=config.MAX_FREE_DOWNLOADS)
    )
    kb = settings_kb(new_lang, user.audio_quality, new_lang)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(t("settings_updated", new_lang))


@router.callback_query(F.data.startswith("quality:"))
async def cb_quality(callback: CallbackQuery) -> None:
    """Handle audio quality change."""
    new_q = int(callback.data.split(":")[1])

    async with async_session() as session:
        await update_user_quality(session, callback.from_user.id, new_q)
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language

    flag = get_language_flag(lang)
    today = date.today()
    dl = user.daily_downloads if user.last_download_date == today else 0

    text = (
        t("settings_title", lang) + "\n\n"
        + t("settings_language", lang, lang=lang.upper(), flag=flag) + "\n"
        + t("settings_quality", lang, quality=new_q) + "\n"
        + t("settings_downloads", lang, count=dl, max=config.MAX_FREE_DOWNLOADS)
    )
    kb = settings_kb(lang, new_q, lang)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(t("settings_updated", lang))


# ───────────────────────── Playlist ─────────────────────────


@router.callback_query(F.data.startswith("addpl:"))
async def cb_add_to_playlist(callback: CallbackQuery) -> None:
    """Add a track to user's playlist."""
    track_hash = callback.data.split(":")[1]
    cache = get_search_cache(callback.from_user.id)

    title, artist = "Unknown", "Unknown"
    if cache:
        for tr in cache["tracks"]:
            if cache_service.generate_hash(tr.track_id or tr.url) == track_hash:
                title, artist = tr.title, tr.artist
                break

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language
        try:
            await add_to_playlist(session, callback.from_user.id, title, artist)
            await callback.answer(t("track_added_to_playlist", lang), show_alert=True)
        except Exception as e:
            logger.error(f"Playlist add failed: {e}")
            await callback.answer(t("error_generic", lang), show_alert=True)


@router.callback_query(F.data.startswith("pldel:"))
async def cb_remove_from_playlist(callback: CallbackQuery) -> None:
    """Remove a track from playlist."""
    item_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language
        deleted = await remove_from_playlist(session, callback.from_user.id, item_id)

        if deleted:
            await callback.answer(t("track_removed_from_playlist", lang))
        else:
            await callback.answer(t("error_generic", lang))

        items, total = await get_playlist(session, callback.from_user.id)

    if total == 0:
        await callback.message.edit_text(t("playlist_empty", lang), parse_mode="HTML")
    else:
        total_pages = math.ceil(total / 8)
        txt = ""
        for i, item in enumerate(items):
            txt += f"{i+1}. <b>{truncate(item.track_artist, 25)}</b> — {truncate(item.track_title, 35)}\n"
        text = t("playlist_title", lang, count=total, tracks=txt)
        kb = playlist_kb(items, 0, total_pages, lang)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("plpage:"))
async def cb_playlist_page(callback: CallbackQuery) -> None:
    """Playlist pagination."""
    page = int(callback.data.split(":")[1])

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language
        items, total = await get_playlist(session, callback.from_user.id, page)

    total_pages = math.ceil(total / 8)
    txt = ""
    for i, item in enumerate(items):
        num = page * 8 + i + 1
        txt += f"{num}. <b>{truncate(item.track_artist, 25)}</b> — {truncate(item.track_title, 35)}\n"

    text = t("playlist_title", lang, count=total, tracks=txt)
    kb = playlist_kb(items, page, total_pages, lang)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ───────────────────────── Shazam Download ─────────────────────────


@router.callback_query(F.data.startswith("shazamdl:"))
async def cb_shazam_download(callback: CallbackQuery, bot: Bot) -> None:
    """Download a Shazam-recognized track."""
    query = callback.data.split(":", 1)[1]

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language

    await callback.answer(t("searching", lang))

    tracks = await music_service.search(query, count=5)
    if not tracks:
        await callback.answer(t("search_empty", lang, query=query), show_alert=True)
        return

    track = tracks[0]
    file_path = await music_service.download_track(track, user.audio_quality)
    if not file_path or not os.path.exists(file_path):
        await callback.answer(t("download_failed", lang), show_alert=True)
        return

    try:
        await tag_audio(file_path=file_path, title=track.title, artist=track.artist)

        file = FSInputFile(file_path)
        content_hash = cache_service.generate_hash(track.track_id or track.url)

        sent = await bot.send_audio(
            chat_id=callback.message.chat.id,
            audio=file, performer=track.artist, title=track.title,
            duration=track.duration,
            caption=t("song_sent", lang, artist=track.artist, title=track.title),
            parse_mode="HTML",
            reply_markup=track_actions_kb(content_hash, query, lang),
        )

        if sent.audio:
            async with async_session() as session:
                await cache_service.save_file_id(
                    session=session, content_hash=content_hash,
                    telegram_file_id=sent.audio.file_id, file_type="audio",
                    title=track.title, artist=track.artist, duration=track.duration,
                )
                await increment_downloads(session, callback.from_user.id)
    except Exception as e:
        logger.error(f"Shazam send failed: {e}")
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass


# ───────────────────────── Force Sub Check ─────────────────────────


@router.callback_query(F.data == "checksub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot) -> None:
    """Re-check channel subscription."""
    if not config.FORCE_SUB_CHANNEL:
        await callback.answer("✅")
        return
    try:
        member = await bot.get_chat_member(config.FORCE_SUB_CHANNEL, callback.from_user.id)
        async with async_session() as session:
            user = await get_or_create_user(session, callback.from_user.id)
            lang = user.language
        if member.status in ("left", "kicked"):
            await callback.answer(t("force_sub_not_subscribed", lang), show_alert=True)
        else:
            await callback.answer(t("force_sub_success", lang), show_alert=True)
            await callback.message.delete()
    except Exception:
        await callback.answer("✅")


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("more:"))
async def cb_more(callback: CallbackQuery) -> None:
    """Back to search results."""
    query = callback.data.split(":", 1)[1]
    cache = get_search_cache(callback.from_user.id)
    if not cache:
        await callback.answer("🔍 Повторите поиск", show_alert=True)
        return

    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language

    tracks = cache["tracks"]
    page_tracks = tracks[:TRACKS_PER_PAGE]
    total_pages = math.ceil(len(tracks) / TRACKS_PER_PAGE)

    text = t(
        "search_results", lang,
        start=1, end=len(page_tracks),
        total=len(tracks), results=_format_results(page_tracks, 0),
    )
    kb = search_results_kb(query, 0, total_pages, len(page_tracks), lang)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
