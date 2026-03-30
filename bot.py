"""
Antigravity Bot — Universal Telegram Media Bot.

Entry point: initializes the bot, registers handlers, and starts polling.
"""

import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from database.engine import init_db
from handlers import register_all_routers
from middlewares.force_sub import ForceSubscribeMiddleware
from middlewares.throttling import ThrottlingMiddleware

# ─── Logging ───

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def main() -> None:
    """Initialize and start the bot."""
    # Validate config
    config.validate()
    logger.info("✅ Config validated")

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Create bot instance
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Create dispatcher
    dp = Dispatcher()

    # Register middlewares
    dp.message.outer_middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.outer_middleware(ThrottlingMiddleware(rate_limit=0.5))

    if config.FORCE_SUB_CHANNEL:
        dp.message.outer_middleware(ForceSubscribeMiddleware())
        dp.callback_query.outer_middleware(ForceSubscribeMiddleware())
        logger.info(f"✅ Force subscribe: {config.FORCE_SUB_CHANNEL}")

    # Register handlers
    register_all_routers(dp)
    logger.info("✅ Handlers registered")

    # ПРОВЕРКА ТОКЕНА (Для пользователя)
    try:
        bot_info = await bot.get_me()
        logger.info(f"🤖 БОТ ЗАПУЩЕН! Имя: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"🔑 ИСПОЛЬЗУЕТСЯ ТОКЕН: {config.BOT_TOKEN.split(':')[0]}...")
    except Exception as e:
        logger.error(f"❌ Не удалось получить инфо о боте (Проверьте токен!): {e}")

    # Установка команд и профиля на 3 языках
    from aiogram.types import BotCommand
    
    try:
        # RU (Русский)
        cmds_ru = [
            BotCommand(command="start", description="🚀 Запуск бота"),
            BotCommand(command="song", description="🎵 Поиск музыки"),
            BotCommand(command="artist", description="🎤 Поиск по артисту"),
            BotCommand(command="top", description="🔥 Популярные треки"),
            BotCommand(command="my", description="📋 Мой плейлист"),
            BotCommand(command="settings", description="⚙️ Настройки бота"),
            BotCommand(command="help", description="ℹ️ Помощь с ботом"),
        ]
        await bot.set_my_commands(cmds_ru, language_code="ru")
        await bot.set_my_commands(cmds_ru) # По умолчанию
        
        # EN (English)
        cmds_en = [
            BotCommand(command="start", description="🚀 Start bot"),
            BotCommand(command="song", description="🎵 Search music"),
            BotCommand(command="artist", description="🎤 Search artist"),
            BotCommand(command="top", description="🔥 Popular tracks"),
            BotCommand(command="my", description="📋 My playlist"),
            BotCommand(command="settings", description="⚙️ Bot settings"),
            BotCommand(command="help", description="ℹ️ Help with bot"),
        ]
        await bot.set_my_commands(cmds_en, language_code="en")

        # UZ (O'zbekcha)
        cmds_uz = [
            BotCommand(command="start", description="🚀 Botni ishga tushirish"),
            BotCommand(command="song", description="🎵 Musiqa qidirish"),
            BotCommand(command="artist", description="🎤 Artist bo'yicha qidirish"),
            BotCommand(command="top", description="🔥 Mashhur treklar"),
            BotCommand(command="my", description="📋 Mening pleylistim"),
            BotCommand(command="settings", description="⚙️ Bot sozlamalari"),
            BotCommand(command="help", description="ℹ️ Botda yordam"),
        ]
        await bot.set_my_commands(cmds_uz, language_code="uz")

        # Описание профиля
        await bot.set_my_short_description("Слушай и скачивай любую музыку!", language_code="ru")
        await bot.set_my_short_description("Listen to and download any music!", language_code="en")
        await bot.set_my_short_description("Istalgan musiqani tinglang va yuklab oling!", language_code="uz")
        
        logger.info("✅ Bot commands and localized profiles set")
    except Exception as e:
        logger.error(f"❌ Failed to set commands or profile: {e}")
        logger.info("⚠️ Continuing startup anyway...")

    # Запуск фонового веб-сервера для Render (чтобы бот не засыпал)
    from aiohttp import web
    
    async def health_check(request):
        return web.Response(text="Bot is running! 🚀")

    app = web.Application()
    app.router.add_get("/", health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Dummy Web Server started on port {port}")

    # Start polling
    logger.info("🚀 Antigravity Bot started!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
