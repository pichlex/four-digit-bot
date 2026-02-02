from typing import Callable, Dict, Any, Awaitable, Set

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: Set[int]):
        self.allowed_ids = allowed_ids

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None or user_id not in self.allowed_ids:
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=False)
            else:
                await event.answer("Нет доступа")
            return None

        return await handler(event, data)
