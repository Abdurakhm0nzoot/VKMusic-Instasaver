"""Force Subscribe middleware — checks if user is subscribed to the required channel."""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, Update

from config import config
from keyboards.inline import force_sub_kb
from utils.i18n import t

logger = logging.getLogger(__name__)


class ForceSubscribeMiddleware(BaseMiddleware):
    """
    Outer middleware that blocks users who are not subscribed
    to the required channel.
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        # Skip if no force sub channel configured
        if not config.FORCE_SUB_CHANNEL:
            return await handler(event, data)

        # Allow /start command and subscription check callbacks
        if isinstance(event, Message) and event.text:
            if event.text.startswith("/start"):
                return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data:
            if event.data == "checksub":
                return await handler(event, data)

        # Get user ID
        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        # Check subscription
        bot: Bot = data.get("bot")
        if bot is None:
            return await handler(event, data)

        try:
            member = await bot.get_chat_member(
                chat_id=config.FORCE_SUB_CHANNEL,
                user_id=user_id,
            )

            if member.status in ("left", "kicked"):
                # User is not subscribed
                lang = data.get("user_lang", "ru")
                text = t("force_sub", lang)
                kb = force_sub_kb(config.FORCE_SUB_CHANNEL, lang)

                if isinstance(event, Message):
                    await event.answer(text, reply_markup=kb)
                elif isinstance(event, CallbackQuery):
                    await event.answer(t("force_sub_not_subscribed", lang), show_alert=True)

                return  # Block further processing

        except Exception as e:
            logger.warning(f"Force sub check failed: {e}")
            # On error, allow the user through (fail open)

        return await handler(event, data)
