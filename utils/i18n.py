"""Internationalization (i18n) — simple JSON-based translation system."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Load all locale files
_translations: dict[str, dict[str, str]] = {}
_locales_dir = Path(__file__).parent.parent / "locales"

SUPPORTED_LANGUAGES = ["ru", "en", "uz"]
DEFAULT_LANGUAGE = "ru"


def _load_locales() -> None:
    """Load all JSON locale files from the locales/ directory."""
    global _translations

    if not _locales_dir.exists():
        logger.warning(f"Locales directory not found: {_locales_dir}")
        return

    for lang in SUPPORTED_LANGUAGES:
        file_path = _locales_dir / f"{lang}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    _translations[lang] = json.load(f)
                logger.info(f"Loaded locale: {lang} ({len(_translations[lang])} keys)")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load locale {lang}: {e}")
        else:
            logger.warning(f"Locale file not found: {file_path}")


# Load on import
_load_locales()


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """
    Get a translated string by key.

    Args:
        key: The translation key (e.g., "welcome", "downloading")
        lang: Language code (ru, en, uz)
        **kwargs: Format parameters for the string

    Returns:
        Translated and formatted string, or the key itself if not found.
    """
    # Try requested language
    text = _translations.get(lang, {}).get(key)

    # Fallback to default language
    if text is None and lang != DEFAULT_LANGUAGE:
        text = _translations.get(DEFAULT_LANGUAGE, {}).get(key)

    # Fallback to English
    if text is None and lang != "en":
        text = _translations.get("en", {}).get(key)

    # Last resort: return the key
    if text is None:
        return key

    # Format with kwargs
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return text


def get_language_flag(lang: str) -> str:
    """Get flag emoji for a language code."""
    flags = {
        "ru": "🇷🇺",
        "en": "🇬🇧",
        "uz": "🇺🇿",
    }
    return flags.get(lang, "🌐")


def get_language_name(lang: str) -> str:
    """Get native name for a language code."""
    names = {
        "ru": "Русский",
        "en": "English",
        "uz": "O'zbek",
    }
    return names.get(lang, lang)
