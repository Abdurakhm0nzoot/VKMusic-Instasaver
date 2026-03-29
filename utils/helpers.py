"""Utility helpers — URL parsing, formatting, etc."""

import re
from urllib.parse import urlparse


# URL detection regex
URL_REGEX = re.compile(
    r"https?://(?:www\.)?"
    r"(?:instagram\.com|tiktok\.com|vm\.tiktok\.com|"
    r"youtube\.com|youtu\.be|m\.youtube\.com|music\.youtube\.com)"
    r"[^\s]+"
)

# Platform detection
PLATFORM_PATTERNS = {
    "instagram": re.compile(r"(?:www\.)?instagram\.com"),
    "tiktok": re.compile(r"(?:www\.)?(?:vm\.)?tiktok\.com"),
    "youtube": re.compile(r"(?:www\.)?(?:m\.)?(?:music\.)?(?:youtube\.com|youtu\.be)"),
}


def extract_url(text: str) -> str | None:
    """Extract the first supported URL from text."""
    match = URL_REGEX.search(text)
    return match.group(0) if match else None


def detect_platform(url: str) -> str | None:
    """Detect platform from URL. Returns 'instagram', 'tiktok', 'youtube', or None."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(domain):
            return platform

    return None


def is_music_link(url: str) -> bool:
    """Check if URL is a music/audio link (YouTube Music, etc.)."""
    return "music.youtube.com" in url


def format_duration(seconds: int) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    if seconds <= 0:
        return "0:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename."""
    return "".join(c for c in name if c.isalnum() or c in " -_.()").strip()[:200]


def format_filesize(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def escape_md(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = ""
    for char in text:
        if char in special_chars:
            escaped += f"\\{char}"
        else:
            escaped += char
    return escaped


# ───────────────────────── URL Cache (for video MP3/thumbnail buttons) ──

# Shared dict: url_hash → original URL
url_cache: dict[str, str] = {}


def cache_url(url: str) -> str:
    """Store URL in cache and return its hash key."""
    key = str(abs(hash(url)))[:12]
    url_cache[key] = url
    return key


def get_cached_url(url_hash: str) -> str | None:
    """Retrieve cached URL by hash."""
    return url_cache.get(url_hash)
