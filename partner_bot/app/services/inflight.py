"""Мягкая остановка: не бросать начатое на полпути.

По сигналу остановки (обновление, перезапуск) aiogram перестаёт брать
новые нажатия, но обработку уже начатых не ждёт — их обрывает выход из
программы. Если в этот момент шла покупка, деньги списаны, а заказ так и
остался бы «в выдаче». Поэтому каждое нажатие отмечается здесь, и перед
выходом бот ждёт, пока все начатые доделаются (не дольше DRAIN секунд).

Если не успели — заказ не пропадёт: при следующем запуске его доведёт
delivery.resume_interrupted (с тем же ключом повтора, без второй оплаты).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

log = logging.getLogger(__name__)

DRAIN = 25
_running: set[asyncio.Task] = set()


class InFlight(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        task = asyncio.current_task()
        if task is not None:
            _running.add(task)
        try:
            return await handler(event, data)
        finally:
            if task is not None:
                _running.discard(task)


def busy() -> int:
    return len([t for t in _running if not t.done()])


async def drain(timeout: float = DRAIN) -> int:
    """Дождаться начатых нажатий. Вернёт, сколько так и не доделалось."""
    me = asyncio.current_task()
    pending = {t for t in _running if not t.done() and t is not me}
    if not pending:
        return 0
    log.info("Остановка: жду %s начатых действий (до %s с)…", len(pending), timeout)
    _, left = await asyncio.wait(pending, timeout=timeout)
    if left:
        log.warning("Остановка: %s действий не доделались — доведу после запуска", len(left))
    return len(left)
