"""Пропуск в API: кто пришёл, не слишком ли часто и не подбирает ли ключ.

Три разные защиты, и путать их нельзя:

  1. Проверка ключа — кто это. Ключ сверяется с хешем, дальше смотрим,
     жив ли он и не забанен ли владелец.

  2. Ограничение частоты — сколько запросов в минуту можно одному ключу.
     Считаем «дырявым ведром»: без отдельного таймера и без списка
     отметок времени, одним числом на ключ.

  3. Защита от подбора — сколько раз подряд с одного адреса приходил
     неверный ключ. Считать по ключу тут нельзя: у подбирающего ключа
     нет, он его и ищет.

Счётчики живут в памяти: бот работает одним процессом, а лишняя запись
в базу на каждый запрос стоила бы дороже самой защиты. После перезапуска
счётчики обнуляются — это приемлемо: ключ от этого не становится
известен, а подбор начинается заново с нуля попыток.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from app import db, runtime
from app.api import keys as apikeys

#: Сколько запросов в минуту разрешено одному ключу.
DEFAULT_RATE = 60

#: Всплеск: столько запросов подряд можно сделать не ожидая.
BURST = 20

#: Сколько неверных ключей с одного адреса терпим, прежде чем закрыть.
BAD_LIMIT = 10

#: На сколько закрываем адрес после этого, секунды.
BAD_BLOCK = 300.0


def rate_limit() -> int:
    """Запросов в минуту на ключ. Владелец меняет это в панели."""
    return max(1, runtime.get_int("api_rate_per_min", DEFAULT_RATE))


@dataclass
class Caller:
    """Кто сделал запрос."""
    key: db.ApiKey
    user: db.User

    @property
    def user_id(self) -> int:
        return self.user.id


class Denied(Exception):
    """Запрос отклонён. code — машинное имя причины, status — код HTTP."""

    def __init__(self, status: int, code: str, message: str,
                 retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


# ─────────────────────────────────────────────── частота запросов


#: ключ -> (сколько «воды» в ведре, когда последний раз доливали)
_buckets: dict[int, tuple[float, float]] = {}


def take(key_id: int, cost: float = 1.0) -> float:
    """Занять место в ведре. 0 — можно, иначе сколько секунд ждать.

    Ведро течёт равномерно: за минуту вытекает rate_limit() единиц.
    Поэтому ровная нагрузка проходит всегда, а всплеск — пока в ведре
    есть запас.
    """
    now = time.monotonic()
    rate = rate_limit() / 60.0
    level, seen = _buckets.get(key_id, (0.0, now))
    level = max(0.0, level - (now - seen) * rate)

    if level + cost > BURST:
        _buckets[key_id] = (level, now)
        return round((level + cost - BURST) / rate, 3)

    _buckets[key_id] = (level + cost, now)
    return 0.0


def forget_rate(key_id: int = 0) -> None:
    if key_id:
        _buckets.pop(key_id, None)
    else:
        _buckets.clear()


# ─────────────────────────────────────────────── подбор ключа


#: адрес -> (сколько промахов, до какого времени закрыт)
_bad: dict[str, tuple[int, float]] = {}


def blocked(ip: str) -> float:
    """Сколько секунд адресу ещё нельзя. 0 — можно."""
    misses, until = _bad.get(ip, (0, 0.0))
    left = until - time.monotonic()
    return round(left, 1) if left > 0 else 0.0


def note_bad_key(ip: str) -> None:
    misses, until = _bad.get(ip, (0, 0.0))
    misses += 1
    if misses >= BAD_LIMIT:
        _bad[ip] = (0, time.monotonic() + BAD_BLOCK)
    else:
        _bad[ip] = (misses, until)


def note_good_key(ip: str) -> None:
    _bad.pop(ip, None)


def forget_bad(ip: str = "") -> None:
    if ip:
        _bad.pop(ip, None)
    else:
        _bad.clear()


# ─────────────────────────────────────────────── сама проверка


def bearer(header: str) -> str:
    """Достать ключ из заголовка Authorization."""
    value = (header or "").strip()
    if not value:
        return ""
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""


async def identify(conn, token: str, ip: str = "") -> Caller:
    """Кто это. Бросает Denied, если пропускать нельзя.

    Ответ на неверный ключ и на несуществующий одинаков нарочно: разница
    в тексте подсказала бы подбирающему, что префикс он угадал.
    """
    wait = blocked(ip)
    if wait:
        raise Denied(429, "too_many_attempts",
                     "Слишком много попыток с неверным ключом.", int(wait) + 1)

    if not token or not apikeys.looks_like(token):
        note_bad_key(ip)
        raise Denied(401, "invalid_key", "Ключ не принят.")

    key_id = apikeys.cached(token)
    key = await db.get_api_key(conn, key_id) if key_id else None
    if key is None:
        for candidate in await db.api_keys_by_prefix(conn, apikeys.prefix_of(token)):
            if apikeys.verify(token, candidate.key_hash):
                key = candidate
                break

    if key is None:
        note_bad_key(ip)
        raise Denied(401, "invalid_key", "Ключ не принят.")

    note_good_key(ip)
    apikeys.remember(token, key.id)

    if not key.live:
        raise Denied(403, "key_disabled", "Ключ выключен или отозван.")

    user = await db.get_user(conn, key.user_id)
    if user is None:
        raise Denied(403, "no_account", "Аккаунт владельца ключа не найден.")
    if user.is_banned:
        raise Denied(403, "account_blocked", "Доступ закрыт.")

    wait = take(key.id)
    if wait:
        raise Denied(429, "rate_limited",
                     f"Слишком часто. Лимит — {rate_limit()} запросов в минуту.",
                     int(wait) + 1)

    return Caller(key=key, user=user)
