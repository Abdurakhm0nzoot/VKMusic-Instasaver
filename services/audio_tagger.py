"""Audio Injection — writes ID3 tags (Title, Artist, Album Art) into MP3 files."""

import logging
import os

import aiohttp

logger = logging.getLogger(__name__)


async def tag_audio(
    file_path: str,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    cover_url: str | None = None,
) -> bool:
    """
    Inject ID3 tags into an MP3 file.

    Args:
        file_path: Path to the MP3 file.
        title: Track title.
        artist: Artist name.
        album: Album name.
        cover_url: URL to album art image.

    Returns:
        True if tagging succeeded.
    """
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
    except ImportError:
        logger.warning("mutagen not installed — skipping audio tagging")
        return False

    if not os.path.exists(file_path):
        return False

    try:
        # Open or create ID3 tags
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()

        # Set title
        if title:
            tags.delall("TIT2")
            tags.add(TIT2(encoding=3, text=title))

        # Set artist
        if artist:
            tags.delall("TPE1")
            tags.add(TPE1(encoding=3, text=artist))

        # Set album
        if album:
            tags.delall("TALB")
            tags.add(TALB(encoding=3, text=album))

        # Download and embed cover art
        if cover_url:
            cover_data = await _download_cover(cover_url)
            if cover_data:
                tags.delall("APIC")
                tags.add(APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,  # Front cover
                    desc="Cover",
                    data=cover_data,
                ))

        tags.save(file_path)
        logger.debug(f"Tagged: {artist} - {title}")
        return True

    except Exception as e:
        logger.error(f"Audio tagging failed: {e}")
        return False


async def _download_cover(url: str) -> bytes | None:
    """Download album cover image from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.read()
        return None
    except Exception as e:
        logger.warning(f"Cover download failed: {e}")
        return None
