"""Music search service — VK music via vkpymusic or fallback to yt-dlp."""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """Represents a music track."""
    title: str
    artist: str
    duration: int  # seconds
    url: str  # download URL or search query
    track_id: str = ""  # unique identifier
    owner_id: int = 0

    @property
    def display_name(self) -> str:
        return f"{self.artist} — {self.title}"

    @property
    def duration_str(self) -> str:
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"


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
            from vkpymusic import TokenReceiver, Service

            self._vk_service = Service.parse_config()
            logger.info("VK Music service initialized")
            return True
        except ImportError:
            logger.warning("vkpymusic not installed")
            return False
        except Exception as e:
            logger.warning(f"VK Music init failed: {e}")
            # Try creating service with token directly
            try:
                from vkpymusic import Service
                self._vk_service = Service(token=config.VK_TOKEN)
                logger.info("VK Music service initialized with direct token")
                return True
            except Exception as e2:
                logger.error(f"VK Music direct init also failed: {e2}")
                return False

    async def search(self, query: str, count: int = 50) -> list[Track]:
        """Search for tracks by query. Returns list of Track objects."""
        vk_ok = await self._init_vk()

        if vk_ok and self._vk_service:
            return await self._search_vk(query, count)

        # Fallback: use yt-dlp YouTube search
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
            logger.error(f"VK search failed: {e}")
            return await self._search_youtube(query, min(count, 20))

    async def _search_youtube(self, query: str, count: int) -> list[Track]:
        """Fallback search via yt-dlp YouTube search."""
        try:
            import yt_dlp

            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "default_search": "ytmsearch",
            }

            search_query = f"ytmsearch{min(count, 20)}:{query}"

            loop = asyncio.get_event_loop()

            def _do_search():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    result = ydl.extract_info(search_query, download=False)
                    return result

            result = await loop.run_in_executor(None, _do_search)

            if not result or "entries" not in result:
                return []

            tracks = []
            for entry in result["entries"]:
                if entry is None:
                    continue
                tracks.append(Track(
                    title=entry.get("title", "Unknown"),
                    artist=entry.get("uploader", entry.get("channel", "Unknown")),
                    duration=entry.get("duration", 0) or 0,
                    url=entry.get("url", entry.get("webpage_url", "")),
                    track_id=f"yt_{entry.get('id', '')}",
                ))

            return tracks

        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return []

    async def download_track(
        self, track: Track, quality: int = 320
    ) -> str | None:
        """Download a track and return the file path."""
        download_dir = config.DOWNLOAD_DIR
        download_dir.mkdir(parents=True, exist_ok=True)

        if track.track_id.startswith("vk_") and track.url:
            return await self._download_vk_track(track, download_dir)

        # For YouTube tracks, use yt-dlp
        return await self._download_yt_track(track, quality, download_dir)

    async def _download_vk_track(
        self, track: Track, download_dir: Path
    ) -> str | None:
        """Download VK track directly from URL."""
        try:
            if self._vk_service:
                safe_name = "".join(
                    c for c in f"{track.artist} - {track.title}"
                    if c.isalnum() or c in " -_."
                )[:100]
                file_path = str(download_dir / f"{safe_name}.mp3")

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._vk_service.save_music,
                    file_path,
                    track.url,
                )

                if os.path.exists(file_path):
                    return file_path

            return None
        except Exception as e:
            logger.error(f"VK download failed: {e}")
            return None

    async def _download_yt_track(
        self, track: Track, quality: int, download_dir: Path
    ) -> str | None:
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
                "socket_timeout": 60,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(quality),
                    }
                ],
            }

            loop = asyncio.get_event_loop()

            def _do_download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([track.url])

            await loop.run_in_executor(None, _do_download)

            if os.path.exists(file_path):
                return file_path

            return None

        except Exception as e:
            logger.error(f"YT download failed: {e}")
            return None


music_service = MusicService()
