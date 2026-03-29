"""Bot configuration — loads settings from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # VK Music
    VK_TOKEN: str = os.getenv("VK_TOKEN", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

    # Redis (optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # Force Subscribe
    FORCE_SUB_CHANNEL: str = os.getenv("FORCE_SUB_CHANNEL", "")

    # Admin IDs
    ADMIN_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    # Downloads
    DOWNLOAD_DIR: Path = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
    MAX_FREE_DOWNLOADS: int = int(os.getenv("MAX_FREE_DOWNLOADS", "20"))

    @classmethod
    def validate(cls) -> None:
        """Check that critical settings are present."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in .env")
        cls.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
