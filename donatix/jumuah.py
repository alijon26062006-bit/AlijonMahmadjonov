"""Пятница 13:00–14:00 (время Душанбе) — время джума-намаза: покупки на сайте и в своём боте закрыты.

Пополнять баланс можно. Партнёры по API-ключу (их сайты и боты) покупают как обычно — их не трогаем.
Оплата, пришедшая в этот час с покупкой, оформится в заказ сама сразу после 14:00.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Config

START_HOUR, END_HOUR = 13, 14
FRIDAY = 4
MESSAGE = ("Пятница, 13:00–14:00 — время джума-намаза. Покупки закрыты до 14:00 по Душанбе. "
           "Пополнить баланс можно, заказ оформите после 14:00.")
SITE_SOURCES = ("panel", "shopbot", "quick")


def _local(config: Config, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone(timedelta(hours=config.tz_offset)))


def closed(config: Config, now: datetime | None = None) -> bool:
    t = _local(config, now)
    return t.weekday() == FRIDAY and START_HOUR <= t.hour < END_HOUR


def blocks(config: Config, user: Any = None, source: str = "panel", now: datetime | None = None) -> bool:
    """Закрыта ли покупка: только сайт и свой бот, не API-ключ."""
    if source not in SITE_SOURCES or not closed(config, now):
        return False
    from .accounts import is_api
    return not (user is not None and is_api(user))
