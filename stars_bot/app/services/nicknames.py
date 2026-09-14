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
#: Второй источник. Лимит у gameskinbo — 100 запросов в месяц, этого
#: мало, поэтому спрашиваем и его: два независимых источника дают ник
#: чаще, чем один.
COMMUNITY = "https://developers.freefirecommunity.com/api/v1/info"
#: Запасной источник без ключа. Живёт на бесплатном хостинге и засыпает,
#: поэтому спрашиваем его последним.
FALLBACK = "https://free-ff-api-src-5plp.onrender.com/api/v1/account"

#: Где в ответе лежит ник. Сервисы отвечают по-разному, а обёртка вокруг
#: одного и того же поля меняется от версии к версии, поэтому ищем по
#: набору известных имён, а не по одному пути.
NAME_KEYS = (
    "AccountName", "accountName", "nickname", "nickName", "name",
    "player_name", "playerName", "username", "user_name",
)
#: Ветки, внутрь которых стоит заглянуть.
NEST_KEYS = (
    "AccountInfo", "accountInfo", "basicInfo", "basic_info",
    "data", "result", "player", "account", "profile", "info",
)

TIMEOUT = aiohttp.ClientTimeout(total=8, connect=4)
FALLBACK_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
CACHE_TTL = 30 * 60          # полчаса

#: Регионы, которые понимает gameskinbo. Чужой код слать нельзя: сервис
#: либо ответит отказом, либо будет искать не там. Регион вообще
#: необязателен — он только ускоряет поиск, ID в Free Fire уникален
#: глобально, поэтому незнакомый код просто выбрасываем.
KNOWN_REGIONS = {"BD", "IND", "BR", "US", "SAC", "NA", "ID", "SG", "PK"}


def known_region(region: str) -> str:
    code = (region or "").strip().upper()
    return code if code in KNOWN_REGIONS else ""

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


def pick_name(data, depth: int = 0) -> str | None:
    """Достать ник из ответа, как бы сервис его ни завернул.

    Разбирать каждый источник отдельно — значит ломаться на каждой смене
    формата. Ник узнаётся по имени поля, а не по месту.
    """
    if not isinstance(data, dict) or depth > 4:
        return None

    for key in NAME_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in NEST_KEYS:
        found = pick_name(data.get(key), depth + 1)
        if found:
            return found

    # Ответ мог прийти списком найденных аккаунтов.
    for value in data.values():
        if isinstance(value, list) and value:
            found = pick_name(value[0], depth + 1)
            if found:
                return found
    return None


async def _from_community(
    session: aiohttp.ClientSession, uid: str, region: str, key: str,
) -> tuple[str | None, str]:
    """Второй справочник: developers.freefirecommunity.com."""
    region = known_region(region)
    url = f"{COMMUNITY}?uid={uid}" + (f"&region={region}" if region else "")
    headers = {"Accept": "application/json"}
    if key:
        headers["x-api-key"] = key
        headers["Authorization"] = f"Bearer {key}"

    async with session.get(url, headers=headers) as response:
        if response.status in (400, 402):
            # Прямой отказ по игроку. Покупку он всё равно не запирает —
            # это решает вызывающий, — но и ник придумывать не из чего.
            return None, "bad"
        if response.status == 404:
            # Двусмысленно: так отвечают и на «нет игрока», и на «нет
            # такого адреса». Принять второе за первое — значит пугать
            # клиента из-за переехавшего сервиса.
            log.info("Ники: freefirecommunity вернул 404 по %s", uid)
            return None, "unknown"
        if response.status != 200:
            log.info("Ники: freefirecommunity ответил %s", response.status)
            return None, "unknown"
        data = await response.json(content_type=None)

    name = pick_name(data)
    return (name, "ok") if name else (None, "unknown")


async def _from_gameskinbo(
    session: aiohttp.ClientSession, uid: str, region: str, key: str,
) -> tuple[str | None, str]:
    region = known_region(region)
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

    name = pick_name(data)
    return (name, "ok") if name else (None, "unknown")


async def _from_fallback(uid: str, region: str) -> tuple[str | None, str]:
    url = f"{FALLBACK}?region={known_region(region) or 'BR'}&uid={uid}"
    try:
        async with aiohttp.ClientSession(timeout=FALLBACK_TIMEOUT) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None, "unknown"
                data = await response.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 — запасной источник ненадёжен
        log.info("Ники: запасной источник молчит — %s", exc)
        return None, "unknown"

    name = pick_name(data)
    return (name, "ok") if name else (None, "unknown")


async def free_fire(
    uid: str, key: str = "", region: str = "", community_key: str = "",
) -> Nickname:
    """Ник по ID. Регион только ускоряет поиск — ID в Free Fire уникален
    глобально, поэтому регион аккаунта с регионом товара не сверяем.

    Источников три, и спрашиваются они по очереди: у первого месячный
    лимит в сто запросов, второй без лимита, третий живёт на бесплатном
    хостинге и часто спит. Первый же найденный ник обрывает очередь.
    """
    uid = str(uid).strip()
    hit = cached(uid)
    if hit:
        return Nickname(uid=uid, name=hit, verdict="ok", source="кэш")

    refused = False        # хоть один источник прямо сказал «нет такого»

    for source, fetch, needs_key in (
        ("gameskinbo", _from_gameskinbo, key),
        ("freefirecommunity", _from_community, None),
    ):
        if needs_key is not None and not needs_key:
            continue       # у gameskinbo без ключа спрашивать нечего
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                name, verdict = await fetch(
                    session, uid, region,
                    key if source == "gameskinbo" else community_key,
                )
        except Exception as exc:  # noqa: BLE001 — переходим к следующему
            log.info("Ники: %s не ответил — %s", source, exc)
            continue

        if verdict == "ok" and name:
            remember(uid, name)
            return Nickname(uid=uid, name=name, verdict="ok", source=source)
        if verdict == "bad":
            # Отказ запоминаем, но очередь не обрываем: другой источник
            # знает другие регионы и может найти того же игрока.
            refused = True

    name, verdict = await _from_fallback(uid, region)
    if verdict == "ok" and name:
        remember(uid, name)
        return Nickname(uid=uid, name=name, verdict="ok", source="запасной")
    if refused:
        return Nickname(uid=uid, name=None, verdict="bad")
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
