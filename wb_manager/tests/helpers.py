"""Помощники тестов: фиктивные токены WB, управляемые часы, настройки."""

from __future__ import annotations

import asyncio
import base64
import json
import random

from wbm.config import WBSettings

SELLER_ID = "e8923014-e233-47a8-898e-3cc86d67ea61"


def _b64(obj: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def make_jwt(payload: dict[str, object]) -> str:
    """Фиктивный JWT того же вида, что токены WB (подпись не настоящая)."""
    return (
        f"{_b64({'alg': 'ES256', 'kid': 'test', 'typ': 'JWT'})}.{_b64(payload)}.c2lnbmF0dXJlX2Zha2U"
    )


def scopes(*bits: int) -> int:
    mask = 0
    for bit in bits:
        mask |= 1 << bit
    return mask


def personal_token(**overrides: object) -> str:
    payload: dict[str, object] = {
        "acc": 3,
        "for": "self",
        "t": False,
        "s": scopes(1, 5, 7, 30),  # Контент, Статистика, Отзывы и вопросы, только чтение
        "sid": SELLER_ID,
        "id": "0b5c3f5e-1111-4222-8333-944445555666",
        "exp": 4_102_444_800,  # 01.01.2100
    }
    payload.update(overrides)
    return make_jwt(payload)


class FakeClock:
    """Часы, которые идут только когда кто-то «спит» — тесты мгновенные и предсказуемые."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        await asyncio.sleep(0)  # как настоящий sleep — отдаём управление другим задачам
        self.now += seconds


class NoJitter(random.Random):
    def uniform(self, a: float, b: float) -> float:
        return a


def make_settings(**overrides: object) -> WBSettings:
    values: dict[str, object] = {
        "sandbox": False,
        "max_retries": 2,
        "max_rate_limit_retries": 2,
        "backoff_base": 1.0,
        "backoff_max": 30.0,
        "max_wait": 300.0,
        "max_concurrency": 4,
    }
    values.update(overrides)
    return WBSettings(_env_file=None, **values)  # type: ignore[arg-type]


def sandbox_token(**overrides: object) -> str:
    """Тестовый токен песочницы: acc=2, t=true."""
    payload: dict[str, object] = {"acc": 2, "t": True, "s": scopes(1, 30), "sid": SELLER_ID}
    payload.update(overrides)
    return make_jwt(payload)
