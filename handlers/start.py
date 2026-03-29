"""/start and /help command handlers."""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.engine import async_session
from database.crud import get_or_create_user, update_user_language
from utils.i18n import t

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start — welcome message + initial language selection."""
    async with async_session() as session:
        user = await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    
    # Always prompt for language selection on /start
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="startlang:ru"),
            InlineKeyboardButton(text="🇺🇸 English", callback_data="startlang:en"),
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="startlang:uz")
        ]
    ])
    
    await message.answer(
        "👋 <b>Привет! Выбери язык:\n👋 Hello! Choose a language:\n👋 Assalomu alaykum! Tilni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("startlang:"))
async def cb_start_language(callback: CallbackQuery) -> None:
    """Handle initial language selection from /start."""
    lang = callback.data.split(":")[1]

    async with async_session() as session:
        await update_user_language(session, callback.from_user.id, lang)
    
    await callback.message.delete()
    await callback.message.answer(
        t("welcome", lang),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help — detailed instruction."""
    async with async_session() as session:
        user = await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
        )
        lang = user.language

    await message.answer(
        t("help", lang),
        parse_mode="HTML",
    )


# Handle the reply keyboard button "📥 Помощь" / "📥 Help"
@router.message(F.text.in_([
    "📥 Помощь", "📥 Help", "📥 Yordam",
]))
async def btn_help(message: Message) -> None:
    """Handle help button press from reply keyboard."""
    await cmd_help(message)
