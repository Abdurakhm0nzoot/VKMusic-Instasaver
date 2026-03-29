"""Admin panel handler — broadcasting and stats."""

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.engine import async_session
from sqlalchemy import text
from keyboards.inline import InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from utils.i18n import t

logger = logging.getLogger(__name__)
router = Router(name="admin")


class BroadcastState(StatesGroup):
    waiting_for_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def admin_kb() -> InlineKeyboardMarkup:
    """Admin panel keyboard."""
    buttons = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Show admin panel if user is admin."""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👋 <b>Добро пожаловать в админ-панель</b>\n"
        "Выберите действие из меню ниже:",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    """Show bot statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Access denied", show_alert=True)
        return

    async with async_session() as session:
        # Get total users
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        total_users = result.scalar()

        # Get total downloads
        result = await session.execute(text("SELECT SUM(total_downloads) FROM users"))
        total_downloads = result.scalar() or 0

        # Get today's active users
        result = await session.execute(text("SELECT COUNT(*) FROM users WHERE last_download_date = CURRENT_DATE"))
        active_today = result.scalar()

    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"⬇️ Всего скачиваний: <b>{total_downloads}</b>\n"
        f"🔥 Активные сегодня: <b>{active_today}</b>"
    )

    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")
        ]]),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    """Start broadcast flow."""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📢 <b>Режим рассылки</b>\n\n"
        "Отправьте сообщение (текст, фото, видео), которое хотите разослать всем пользователям.\n"
        "Для отмены отправьте /cancel.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Отмена", callback_data="admin_back")
        ]])
    )
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.answer()


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot) -> None:
    """Process message and send to all users."""
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("Рассылка отменена.", reply_markup=admin_kb())
        return

    await state.clear()
    status_msg = await message.answer("⏳ Начинаю рассылку...")

    success = 0
    failed = 0

    async with async_session() as session:
        result = await session.execute(text("SELECT telegram_id FROM users"))
        user_ids = [row[0] for row in result.fetchall()]

    for user_id in user_ids:
        try:
            await message.send_copy(chat_id=user_id)
            success += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Успешно: {success}\n"
        f"Не удалось (заблокировали): {failed}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Back to main admin menu."""
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    await callback.message.edit_text(
        "👋 <b>Добро пожаловать в админ-панель</b>\n"
        "Выберите действие из меню ниже:",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )
