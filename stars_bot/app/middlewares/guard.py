"""Мидлварь: регистрация пользователя и отсечение забаненных."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app import db, texts
from app.config import settings


class UserGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        conn: aiosqlite.Connection | None = data.get("conn")
        if user is None or conn is None:
            return await handler(event, data)

        await db.upsert_user(conn, user.id, user.username, user.first_name)

        if not settings.is_admin(user.id) and await db.is_banned(conn, user.id):
            if isinstance(event, Message):
                await event.answer(texts.BANNED)
            elif isinstance(event, CallbackQuery):
                await event.answer(texts.BANNED, show_alert=True)
            return None

        return await handler(event, data)
