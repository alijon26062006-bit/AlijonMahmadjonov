"""Ники Free Fire по числовому ID — чтобы клиент увидел, кому платит.

Бесплатный план gameskinbo даёт 100 запросов В МЕСЯЦ и 5 в минуту. Это
очень мало, поэтому удачные ответы держим в памяти полчаса: один и тот же
человек обычно вводит свой ID несколько раз подряд, и каждый такой ввод
не должен съедать лимит.

Неудачи не кэшируем: сервис мог просто не ответить, и через минуту тот же
ID вернёт ник. Запомнить «ника нет» значило бы испортить проверку до
перезапуска бота.

Ник — не пропуск к покупке. Пополнение идёт по ID, ник нужен только для
сверки глазами: не получили — показываем «ID принят» и даём купить.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

GAMESKINBO = "https://api.gameskinbo.com/ff-info/get"
GAMESKINBO_USAGE = "https://api.gameskinbo.com/api/usage"
#: Запасной источник без ключа. Живёт на бесплатном хостинге и засыпает,
#: поэтому спрашиваем его только когда основной молчит.
FALLBACK = "https://free-ff-api-src-5plp.onrender.com/api/v1/account"

TIMEOUT = aiohttp.ClientTimeout(total=8, connect=4)
FALLBACK_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
CACHE_TTL = 30 * 60          # полчаса

_cache: dict[str, tuple[float, str]] = {}


@dataclass
class Nickname:
    uid: str
    name: str | None
    verdict: str       # ok | bad | unknown
    source: str = ""


def cached(uid: str) -> str | None:
    found = _cache.get(uid)
    if not found:
        return None
    stored_at, name = found
    if time.time() - stored_at > CACHE_TTL:
        _cache.pop(uid, None)
        return None
    return name


def remember(uid: str, name: str) -> None:
    _cache[uid] = (time.time(), name)


def forget_all() -> None:
    _cache.clear()


async def _from_gameskinbo(
    session: aiohttp.ClientSession, uid: str, region: str, key: str,
) -> tuple[str | None, str]:
    url = f"{GAMESKINBO}?uid={uid}" + (f"&region={region}" if region else "")
    async with session.get(url, headers={"x-api-key": key}) as response:
        if response.status == 402:
            return None, "bad"          # сервис прямо говорит: ID неверный
        if response.status in (401, 429):
            log.info("Ники: gameskinbo ответил %s", response.status)
            return None, "unknown"
        if response.status != 200:
            return None, "unknown"
        data = await response.json(content_type=None)

    info = (data or {}).get("AccountInfo") or {}
    name = info.get("AccountName")
    return (str(name), "ok") if name else (None, "unknown")


async def _from_fallback(uid: str, region: str) -> tuple[str | None, str]:
    url = f"{FALLBACK}?region={region or 'BR'}&uid={uid}"
    try:
        async with aiohttp.ClientSession(timeout=FALLBACK_TIMEOUT) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None, "unknown"
                data = await response.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 — запасной источник ненадёжен
        log.info("Ники: запасной источник молчит — %s", exc)
        return None, "unknown"

    name = ((data or {}).get("basicInfo") or {}).get("nickname")
    return (str(name), "ok") if name else (None, "unknown")


async def free_fire(uid: str, key: str = "", region: str = "") -> Nickname:
    """Ник по ID. Регион только ускоряет поиск — ID в Free Fire уникален
    глобально, поэтому регион аккаунта с регионом товара не сверяем."""
    uid = str(uid).strip()
    hit = cached(uid)
    if hit:
        return Nickname(uid=uid, name=hit, verdict="ok", source="кэш")

    if key:
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                name, verdict = await _from_gameskinbo(session, uid, region, key)
        except Exception as exc:  # noqa: BLE001 — переходим к запасному
            log.info("Ники: gameskinbo не ответил — %s", exc)
            name, verdict = None, "unknown"

        if verdict == "ok" and name:
            remember(uid, name)
            return Nickname(uid=uid, name=name, verdict="ok", source="gameskinbo")
        if verdict == "bad":
            return Nickname(uid=uid, name=None, verdict="bad", source="gameskinbo")

    name, verdict = await _from_fallback(uid, region)
    if verdict == "ok" and name:
        remember(uid, name)
        return Nickname(uid=uid, name=name, verdict="ok", source="запасной")
    return Nickname(uid=uid, name=None, verdict="unknown")


async def usage(key: str) -> dict | None:
    """Остаток лимита у gameskinbo."""
    if not key:
        return None
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.get(
                GAMESKINBO_USAGE, headers={"x-api-key": key}
            ) as response:
                if response.status != 200:
                    return None
                return await response.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        log.info("Ники: лимит не прочитался — %s", exc)
        return None
