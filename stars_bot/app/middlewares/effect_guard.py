"""Если Telegram не принял эффект сообщения — отправить без него.

Эффект работает только в личке; номер мог устареть. Ни то, ни другое не
повод терять само сообщение — особенно «оплата прошла» или «заказ
выполнен».
"""
from __future__ import annotations

import logging

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest

log = logging.getLogger(__name__)


class EffectGuard(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            if not getattr(method, "message_effect_id", None):
                raise
            log.warning("Telegram не принял эффект сообщения (%s) — шлю без него", exc)
            object.__setattr__(method, "message_effect_id", None)
            return await make_request(bot, method)
