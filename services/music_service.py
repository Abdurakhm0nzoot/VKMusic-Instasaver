"""Music search service — VK music via vkpymusic or fallback to yt-dlp."""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from config import config
from database.models import Track

logger = logging.getLogger(__name__)


class MusicService:
    """Search and download music tracks."""

    def __init__(self):
        self._vk_service = None
        self._initialized = False

    async def _init_vk(self) -> bool:
        """Lazy-initialize VK music service."""
        if self._initialized:
            return self._vk_service is not None

        self._initialized = True

        if not config.VK_TOKEN:
            logger.warning("VK_TOKEN not set — VK music search disabled")
            return False

        try:
            from vkpymusic import Service
            self._vk_service = Service(token=config.VK_TOKEN)
            logger.info("VK Music service initialized")
            return True
        except Exception as e:
            logger.error(f"VK Music init failed: {e}")
            return False

    async def search(self, query: str, count: int = 10) -> list[Track]:
        """Fast search: uses YouTube if VK token is missing, with a strict timeout."""
        if config.VK_TOKEN:
            try:
                vk_ok = await self._init_vk()
                if vk_ok and self._vk_service:
                    tracks = await self._search_vk(query, count)
                    if tracks: return tracks
            except Exception as e:
                logger.error(f"VK search failed: {e}")

        # Fallback to fast YouTube search
        return await self._search_youtube(query, count)

    async def _search_vk(self, query: str, count: int) -> list[Track]:
        """Search via VK Music."""
        try:
            loop = asyncio.get_event_loop()
            songs = await loop.run_in_executor(
                None, self._vk_service.search_songs_by_text, query, count
            )

            tracks = []
            for song in songs:
                tracks.append(Track(
                    title=song.title,
                    artist=song.artist,
                    duration=song.duration,
                    url=song.url,
                    track_id=f"vk_{song.owner_id}_{song.song_id}",
                    owner_id=song.owner_id,
                ))
            return tracks
        except Exception as e:
            logger.error(f"VK search internal error: {e}")
            return []

    async def _search_youtube(self, query: str, count: int) -> list[Track]:
        """Turbo-fast search using YouTube extract_flat mode with 15s timeout."""
        try:
            return await asyncio.wait_for(
                self._do_youtube_flat_search(query, count),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.error(f"YouTube search timed out for {query}")
            return []
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    async def _do_youtube_flat_search(self, query: str, count: int) -> list[Track]:
        """Internal helper for flat search."""
        import yt_dlp
        
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True, # ONLY gets titles/ids (Very fast)
            "skip_download": True,
            "socket_timeout": 10, # Убиваем поиск через 10 сек
            "retries": 1,
            "nocheckcertificate": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        }
        
        search_query = f"ytsearch{min(count, 20)}:{query}"
        logger.info(f"Executing YouTube search for: {query}")
        
        def _sync_search():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(search_query, download=False)

        result = await asyncio.get_event_loop().run_in_executor(None, _sync_search)
        
        if not result or "entries" not in result:
            return []

        tracks = []
        for entry in result["entries"]:
            if not entry: continue
            
            title_full = entry.get("title", "Unknown")
            if " - " in title_full:
                artist, title = title_full.split(" - ", 1)
            else:
                artist, title = "YouTube", title_full
                
            tracks.append(Track(
                title=title[:60].strip(),
                artist=artist[:60].strip(),
                duration=int(entry.get("duration", 0) or 0),
                url=entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                track_id=f"yt_{entry.get('id', '')}",
            ))
        return tracks

    async def download_track(self, track: Track, quality: int = 320) -> str | None:
        """Download a track and return the file path."""
        download_dir = config.DOWNLOAD_DIR
        download_dir.mkdir(parents=True, exist_ok=True)

        if str(track.track_id).startswith("vk_") and track.url:
            return await self._download_vk_track(track, download_dir)

        return await self._download_yt_track(track, quality, download_dir)

    async def _download_vk_track(self, track: Track, download_dir: Path) -> str | None:
        """Download VK track directly from URL."""
        try:
            if self._vk_service:
                safe_name = "".join(c for c in f"{track.artist} - {track.title}" if c.isalnum() or c in " -_.")[:80]
                file_path = str(download_dir / f"{safe_name}.mp3")

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._vk_service.save_music, file_path, track.url)

                if os.path.exists(file_path):
                    return file_path
            return None
        except Exception as e:
            logger.error(f"VK download failed: {e}")
            return None

    async def _download_yt_track(self, track: Track, quality: int, download_dir: Path) -> str | None:
        """Download YouTube track as MP3."""
        try:
            import yt_dlp
            safe_id = track.track_id.replace("yt_", "")
            file_path = str(download_dir / f"{safe_id}.mp3")

            opts = {
                "format": "bestaudio/best",
                "outtmpl": str(download_dir / f"{safe_id}.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(quality),
                }],
            }

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(opts).download([track.url]))

            if os.path.exists(file_path):
                return file_path
            return None
        except Exception as e:
            logger.error(f"YT download failed: {e}")
            return None


music_service = MusicService()
