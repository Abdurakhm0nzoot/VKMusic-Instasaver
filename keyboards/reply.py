"""Reply keyboards (persistent bottom buttons)."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from utils.i18n import t


def main_menu_kb(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Main menu reply keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("btn_search", lang)),
                KeyboardButton(text=t("btn_help", lang)),
            ],
            [
                KeyboardButton(text=t("btn_playlist", lang)),
                KeyboardButton(text=t("btn_settings", lang)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
    return keyboard
