"""Handlers package — registers all routers with the dispatcher."""

from aiogram import Dispatcher

from handlers.start import router as start_router
from handlers.downloader import router as downloader_router
from handlers.music_search import router as music_search_router
from handlers.playlist import router as playlist_router
from handlers.settings import router as settings_router
from handlers.shazam_handler import router as shazam_router
from handlers.callbacks import router as callbacks_router
from handlers.admin import router as admin_router


def register_all_routers(dp: Dispatcher) -> None:
    """Register all handler routers with the dispatcher."""
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(callbacks_router)
    dp.include_router(shazam_router)
    dp.include_router(downloader_router)
    dp.include_router(music_search_router)
    dp.include_router(playlist_router)
    dp.include_router(settings_router)
