"""Throttling middleware — rate-limits user requests to prevent abuse."""

import time
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Simple in-memory rate limiter.
    Limits each user to 1 request per `rate_limit` seconds.
    """

    def __init__(self, rate_limit: float = 1.5):
        self.rate_limit = rate_limit
        self._timestamps: Dict[int, float] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        now = time.time()
        last = self._timestamps.get(user_id, 0)

        if now - last < self.rate_limit:
            # Rate limited — silently ignore
            logger.debug(f"Throttled user {user_id}")
            return

        self._timestamps[user_id] = now

        # Cleanup old entries periodically (every 100 requests)
        if len(self._timestamps) > 10000:
            cutoff = now - 60
            self._timestamps = {
                uid: ts
                for uid, ts in self._timestamps.items()
                if ts > cutoff
            }

        return await handler(event, data)
