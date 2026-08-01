from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.repositories import UserRepo
from bot.services import log_action


class UserMiddleware(BaseMiddleware):
    """Регистрирует/обновляет пользователя и кладёт его в data["db_user"]."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if tg_user and session and not tg_user.is_bot:
            repo = UserRepo(session)
            user, created = await repo.upsert(
                tg_user.id, tg_user.username, tg_user.full_name
            )
            data["db_user"] = user
            if created:
                await log_action(session, tg_user.id, "create", "users", user.id,
                                 new={"tg_id": str(tg_user.id),
                                      "username": tg_user.username or ""})
        return await handler(event, data)
