"""Курс рубля к сомони для показа цен: «10 с. / 95 ₽».

Режим auto — курс ЦБ России (cbr-xml-daily.ru, раз в 6 часов). Режим
manual — свой курс из панели (например, как у вас при переводе из
России); бот его не трогает.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from app import db, runtime

log = logging.getLogger(__name__)

URL = "https://www.cbr-xml-daily.ru/daily_json.js"
EVERY = 6 * 60 * 60


def parse(data: dict) -> float | None:
    """Из ответа ЦБ: сколько рублей в 1 сомони."""
    try:
        tjs = data["Valute"]["TJS"]
        rate = float(tjs["Value"]) / float(tjs["Nominal"] or 1)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return rate if rate > 0 else None


async def fetch() -> float | None:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.get(URL) as resp:
                data = await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 — нет курса — оставляем прежний
        log.info("Курс рубля не получен: %s", exc)
        return None
    return parse(data) if isinstance(data, dict) else None


async def refresh(conn) -> float | None:
    """Обновить курс, если режим auto. Возвращает новый курс или None."""
    if runtime.get("rub_mode", "auto") != "auto":
        return None
    rate = await fetch()
    if rate:
        await runtime.set_value(conn, "rub_per_tjs", f"{rate:.4f}")
    return rate


async def loop() -> None:
    while True:
        try:
            conn = await db.connect()
            try:
                await refresh(conn)
            finally:
                await conn.close()
            await asyncio.sleep(EVERY)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.warning("Курс рубля: %s", exc)
            await asyncio.sleep(600)
