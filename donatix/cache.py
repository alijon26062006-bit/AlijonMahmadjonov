"""Короткий кеш в памяти: главная и каталог не ходят в базу на каждый запрос.

Данные живут несколько секунд–минут; после загрузки каталога или правки товара
кеш сбрасывается сразу (clear), так что клиент не видит старых цен.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def get_or_set(key: str, ttl: float, make: Callable[[], Any]) -> Any:
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = make()
    with _lock:
        _store[key] = (now + ttl, value)
    return value


def clear(prefix: str = "") -> None:
    with _lock:
        for key in [k for k in _store if k.startswith(prefix)]:
            del _store[key]
