"""Миёнаравҳо: сабти корбар ва маҳдудкунии дастрасӣ."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError
from aiogram.types import TelegramObject, Update

from . import keyboards, style, texts
from .subscription import missing_channels
from .config import Config
from .db import Database

log = logging.getLogger(__name__)


async def _tell(bot, chat_id: int, text: str) -> None:
    """Паёми хидматӣ мефиристад. Хатои фиристодан набояд ҷараёнро вайрон кунад."""
    if bot is None:
        return
    try:
        await bot.send_message(chat_id, text)
    except Exception as exc:
        log.info("Паёми хидматӣ ба %s нарасид: %s", chat_id, exc)


class GuardMiddleware(BaseMiddleware):
    """Ҳар навигариро сабт мекунад ва корбарони маҳдудшударо намегузаронад."""

    def __init__(self, db: Database, cfg: Config) -> None:
        self.db = db
        self.cfg = cfg

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        inner = event.event if isinstance(event, Update) else event
        src = getattr(inner, "from_user", None)
        if src is None or src.is_bot:
            return await handler(event, data)

        user = self.db.touch_user(src.id, src.username, src.first_name)
        data["user"] = user

        if user.is_blocked and not self.cfg.is_admin(src.id):
            await _tell(data.get("bot"), src.id, texts.BLOCKED)
            return None

        if not await self._subscribed(inner, data, src.id):
            return None

        return await handler(event, data)

    async def _subscribed(self, inner, data: dict[str, Any], user_id: int) -> bool:
        """Обунаи ҳатмӣ. Админ ва худи тугмаи санҷиш озоданд."""
        bot = data.get("bot")
        if bot is None or self.cfg.is_admin(user_id):
            return True
        if getattr(inner, "data", None) == keyboards.CB_CHECK_SUB:
            return True  # ҳамин тугма обунаро месанҷад

        missing = await missing_channels(bot, self.db, user_id)
        if not missing:
            return True
        try:
            await bot.send_message(
                user_id,
                texts.subscribe_required(missing),
                reply_markup=keyboards.subscribe(missing),
            )
        except Exception as exc:
            log.info("Дархости обуна ба %s нарасид: %s", user_id, exc)
        return False


class ErrorGuardMiddleware(BaseMiddleware):
    """Хатои ғайричашмдошт набояд ботро хомӯш кунад."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            log.exception("Хато ҳангоми коркарди навигарӣ")
            inner = event.event if isinstance(event, Update) else event
            src = getattr(inner, "from_user", None)
            if src is not None:
                await _tell(data.get("bot"), src.id, texts.ERROR)
            return None


class ButtonStyleFallback(BaseRequestMiddleware):
    """Муҳофиз: агар Telegram рангҳоро қабул накунад, бот наафтад.

    Баъзе серверҳо ё версияҳои кӯҳна майдони ``style``-ро намешиносанд ва
    тамоми паёмро рад мекунанд. Дар ин ҳолат рангҳоро хомӯш мекунем,
    аз клавиатура мебардорем ва паёмро аз нав мефиристем.
    """

    async def __call__(self, make_request, bot, method):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            markup = getattr(method, "reply_markup", None)
            if markup is None or "style" not in str(exc).lower():
                raise
            log.error(
                "Telegram ранги тугмаҳоро қабул накард (%s). "
                "Рангҳо хомӯш карда шуданд — SHOP_BUTTON_COLORS=0 дар .env нависед.",
                exc,
            )
            style.set_enabled(False)
            if not style.strip(markup):
                raise
            return await make_request(bot, method)


class ConflictWatch(BaseRequestMiddleware):
    """Нусхаи дигари ҳамин бот дар ҷои дигар кор мекунад — админ фавран медонад.

    Telegram ба ду нусхае, ки бо як токен навсозӣ мегиранд, «Conflict» мегӯяд.
    Қулфи файл танҳо дар як сервер кор мекунад; ин муҳофиз — байни серверҳо.

    Пас аз ҳар азнавоғозкунӣ дархости кӯҳнаи getUpdates то 30 сония зинда
    мемонад ва чанд «Conflict» медиҳад — ин нусхаи дуюм нест. Бинобар ин
    тревога танҳо вақте меравад, ки конфликт аз ``min_span`` сония дарозтар бошад.
    """

    def __init__(
        self, notify, every: float = 900.0, min_span: float = 90.0, min_hits: int = 5,
        quiet_gap: float = 120.0,
    ) -> None:
        self.notify = notify
        self.every = every
        self.min_span = min_span
        self.min_hits = min_hits
        self.quiet_gap = quiet_gap
        self._last_alert = -every
        self._streak_start: float | None = None
        self._last_hit = 0.0
        self._hits = 0
        self._tasks: set = set()

    def _hit(self, now: float) -> bool:
        """Конфликти навбатӣ. True — вақти тревога аст."""
        if self._streak_start is None or now - self._last_hit > self.quiet_gap:
            self._streak_start, self._hits = now, 0
        self._hits += 1
        self._last_hit = now
        lasting = now - self._streak_start >= self.min_span and self._hits >= self.min_hits
        if lasting and now - self._last_alert >= self.every:
            self._last_alert = now
            return True
        return False

    async def __call__(self, make_request, bot, method):
        try:
            return await make_request(bot, method)
        except TelegramConflictError:
            if self._hit(time.monotonic()):
                log.error("Нусхаи дигари бот бо ҳамин токен кор мекунад!")
                task = asyncio.create_task(self.notify(bot))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            raise
