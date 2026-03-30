from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DbMiddleware(BaseMiddleware):

    def __init__(self, engine) -> None:
        self.engine = engine

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db_engine"] = self.engine
        return await handler(event, data)
