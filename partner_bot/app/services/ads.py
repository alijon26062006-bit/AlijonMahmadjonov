"""Реклама Donatix в боте: картинка с кнопками «Перейти» и «Пропустить».

Бот только спрашивает Donatix в спокойный момент — когда показывает главное
меню. Решает Donatix: кому, когда и что (не больше двух раз в день одному
человеку, в разное время, общий счёт на все боты). Владельцу и админам
бота реклама не показывается никогда — проверяем и здесь, и на Donatix.

Работает, только когда бот подключён к Donatix (задан DONATIX_URL). Любой
сбой здесь бот не ломает: рекламы просто не будет.
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from app.config import settings
from app.services import access

log = logging.getLogger(__name__)

SKIP = "adskip"
TIMEOUT = aiohttp.ClientTimeout(total=8)
_tasks: set[asyncio.Task] = set()     # держим ссылки, иначе задачу может собрать сборщик мусора


def enabled() -> bool:
    return bool(os.environ.get("DONATIX_URL") and settings.fazer_api_key)


def maybe_show(bot: Bot | None, user_id: int) -> None:
    """Запустить в фоне: меню показывается сразу, реклама — следом, если сейчас её время."""
    if bot is None or not enabled() or access.is_admin(user_id):
        return
    task = asyncio.create_task(_show(bot, user_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _ask(user_id: int) -> dict | None:
    url = os.environ["DONATIX_URL"].rstrip("/") + "/api/v2/ads/next"
    headers = {"X-API-Key": settings.fazer_api_key, "Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=headers) as s:
        async with s.post(url, json={"tg_user_id": user_id}) as r:
            if r.status != 200:
                return None
            body = await r.json(content_type=None)
    return body.get("ad") if isinstance(body, dict) else None


async def _show(bot: Bot, user_id: int) -> None:
    try:
        ad = await _ask(user_id)
        if not ad:
            return
        await bot.send_photo(user_id, photo=ad["photo"], caption=ad.get("caption") or "Реклама",
                             reply_markup=InlineKeyboardMarkup.model_validate(ad["reply_markup"]))
    except Exception as exc:  # noqa: BLE001 — реклама не должна мешать боту
        log.warning("реклама Donatix: %s", exc)
