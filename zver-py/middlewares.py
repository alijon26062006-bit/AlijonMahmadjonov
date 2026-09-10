"""Защита от перебора и заблокированных пользователей.

Ключ лимита — telegram id, а не IP: в боте IP не виден, а id подделать
нельзя. Как и в PHP, любая ошибка проверки пропускает пользователя —
лимитер не должен становиться причиной отказа в обслуживании.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

import db
from handlers.common import is_admin, log
from texts import DEFAULT_LANG, t

# не больше 20 действий за 10 секунд; при превышении — минута тишины
LIMIT = 20
WINDOW = 10
BAN_MINUTES = 1


class Guard(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or is_admin(user.id):
            return await handler(event, data)

        uid = user.id
        key = f"tg:{uid}"

        try:
            if await db.is_banned(key):
                await _quiet_notice(event, "too_fast")
                return None

            if not await db.rate_ok(key, LIMIT, WINDOW):
                await db.ban(key, BAN_MINUTES, "flood")
                log.info("пользователь %s притормозён за частые действия", uid)
                await _quiet_notice(event, "too_fast")
                return None

            row = await db.get_user(uid)
            if row and row.get("blocked"):
                await _quiet_notice(event, "blocked", row.get("lang"))
                return None
        except Exception as e:
            log.warning("защита не отработала, пропускаю %s: %s", uid, e)

        return await handler(event, data)


async def _quiet_notice(event: TelegramObject, key: str,
                        lang: str | None = None) -> None:
    """Сообщить один раз и тихо: на кнопке — всплывашкой, на тексте — ответом."""
    lang = lang or DEFAULT_LANG
    try:
        obj = event.event if isinstance(event, Update) else event
        if isinstance(obj, CallbackQuery):
            await obj.answer(t(lang, key), show_alert=True)
        elif isinstance(obj, Message):
            await obj.answer(t(lang, key))
    except Exception:
        pass
