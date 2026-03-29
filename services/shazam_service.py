"""Shazam music recognition service via shazamio."""

import asyncio
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


@dataclass
class ShazamResult:
    """Result of music recognition."""
    title: str
    artist: str
    album: str | None = None
    cover_url: str | None = None
    shazam_url: str | None = None


class ShazamService:
    """Recognize music from audio files using Shazam."""

    async def recognize(self, file_path: str) -> ShazamResult | None:
        """
        Recognize a song from an audio file.
        Supports: voice messages, audio files, video notes.
        The file should ideally be in WAV format.
        """
        try:
            from shazamio import Shazam

            shazam = Shazam()

            # Convert to a format shazamio can handle
            wav_path = await self._convert_to_wav(file_path)
            if wav_path is None:
                wav_path = file_path

            out = await shazam.recognize(wav_path)

            # Cleanup temp WAV
            if wav_path != file_path and os.path.exists(wav_path):
                os.remove(wav_path)

            # Parse result
            if not out or "track" not in out:
                return None

            track = out["track"]
            return ShazamResult(
                title=track.get("title", "Unknown"),
                artist=track.get("subtitle", "Unknown"),
                album=self._get_album(track),
                cover_url=self._get_cover(track),
                shazam_url=track.get("url"),
            )

        except ImportError:
            logger.error("shazamio not installed — pip install shazamio")
            return None
        except Exception as e:
            logger.error(f"Shazam recognition failed: {e}")
            return None

    async def _convert_to_wav(self, input_path: str) -> str | None:
        """Convert audio to WAV format using ffmpeg."""
        try:
            output_path = os.path.splitext(input_path)[0] + ".wav"

            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-ar", "44100",
                "-ac", "1",
                "-f", "wav",
                output_path,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.wait()

            if process.returncode == 0 and os.path.exists(output_path):
                return output_path

            return None

        except FileNotFoundError:
            logger.warning("ffmpeg not found — skipping conversion")
            return None
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return None

    @staticmethod
    def _get_album(track: dict) -> str | None:
        """Extract album name from Shazam response."""
        sections = track.get("sections", [])
        for section in sections:
            if section.get("type") == "SONG":
                metadata = section.get("metadata", [])
                for meta in metadata:
                    if meta.get("title") == "Album":
                        return meta.get("text")
        return None

    @staticmethod
    def _get_cover(track: dict) -> str | None:
        """Extract cover image URL from Shazam response."""
        images = track.get("images", {})
        return images.get("coverart") or images.get("background")


shazam_service = ShazamService()
