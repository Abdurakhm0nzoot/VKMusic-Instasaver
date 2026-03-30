"""Media downloader service — yt-dlp wrapper for Instagram, TikTok, YouTube."""

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from config import config

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a media download."""
    file_path: str
    title: str
    duration: int  # seconds
    file_type: str  # "video" | "audio"
    thumbnail: str | None = None
    filesize: int = 0  # bytes


class DownloaderService:
    """Downloads media from social platforms using yt-dlp."""

    # Max file size for Telegram Bot API (50 MB)
    MAX_FILESIZE = 50 * 1024 * 1024

    # Supported domains
    SUPPORTED_DOMAINS = {
        "instagram.com", "www.instagram.com",
        "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
        "youtube.com", "www.youtube.com", "youtu.be",
        "m.youtube.com", "music.youtube.com",
    }

    def __init__(self):
        self.download_dir = config.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _get_video_opts(self) -> dict:
        """Optimized yt-dlp options for FAST video downloads."""
        return {
            "format": "mp4/bestvideo+bestaudio/best", # Prioritize single file mp4 for speed
            "outtmpl": str(self.download_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2,
            "nocheckcertificate": True, # Faster SSL
            "noplaylist": True,
            "playlist_items": "1", # Extremely important for IG/TikTok speed
            "merge_output_format": "mp4",
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }
            ],
            "match_filter": yt_dlp.utils.match_filter_func("duration < 900"),
        }

    def _get_audio_opts(self, quality: int = 320) -> dict:
        """Optimized yt-dlp options for FAST audio extraction."""
        return {
            "format": "bestaudio/best",
            "outtmpl": str(self.download_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2,
            "nocheckcertificate": True,
            "noplaylist": True,
            "playlist_items": "1",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(quality),
                }
            ],
        }

    async def download_video(self, url: str) -> DownloadResult | None:
        """Download video from URL. Returns DownloadResult or None on failure."""
        opts = self._get_video_opts()
        return await self._download(url, opts, "video")

    async def download_audio(
        self, url: str, quality: int = 320
    ) -> DownloadResult | None:
        """Download and extract audio from URL."""
        opts = self._get_audio_opts(quality)
        return await self._download(url, opts, "audio")

    async def _download(
        self, url: str, opts: dict, file_type: str
    ) -> DownloadResult | None:
        """Run yt-dlp in a thread pool to avoid blocking the event loop."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_download, url, opts, file_type
            )
            return result
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return None

    def _sync_download(
        self, url: str, opts: dict, file_type: str
    ) -> DownloadResult | None:
        """Synchronous download using yt-dlp."""
        info = None
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if info is None:
                    return None

                # Find the downloaded file
                if file_type == "audio":
                    # After FFmpegExtractAudio, extension changes to mp3
                    file_path = str(
                        self.download_dir / f"{info['id']}.mp3"
                    )
                else:
                    file_path = str(
                        self.download_dir / f"{info['id']}.mp4"
                    )

                # Try alternative path from yt-dlp
                if not os.path.exists(file_path):
                    # Check for prepared filename
                    prepared = ydl.prepare_filename(info)
                    if file_type == "audio":
                        prepared = os.path.splitext(prepared)[0] + ".mp3"
                    if os.path.exists(prepared):
                        file_path = prepared

                if not os.path.exists(file_path):
                    logger.error(f"Downloaded file not found: {file_path}")
                    return None

                filesize = os.path.getsize(file_path)
                if filesize > self.MAX_FILESIZE:
                    os.remove(file_path)
                    logger.warning(f"File too large ({filesize} bytes): {url}")
                    return None

                return DownloadResult(
                    file_path=file_path,
                    title=info.get("title", "Unknown"),
                    duration=info.get("duration", 0) or 0,
                    file_type=file_type,
                    thumbnail=info.get("thumbnail"),
                    filesize=filesize,
                )

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected download error: {e}")
            return None

    @staticmethod
    def cleanup(file_path: str) -> None:
        """Remove downloaded file after sending."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")


downloader_service = DownloaderService()
