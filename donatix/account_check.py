"""Проверка аккаунта игрока до оплаты: поставщик по ID возвращает ник.

Проверку умеют не все игры — список берём у поставщика и держим час в памяти.
Если поставщик недоступен, заказ не блокируем: проверка — подсказка, а не условие."""

from __future__ import annotations

import threading
import time
from typing import Any

from .suppliers import Supplier, SupplierError, SupplierRejected

_TTL = 3600
_lock = threading.Lock()
_supported: tuple[float, frozenset[str]] | None = None
_results: dict[tuple, tuple[float, dict[str, Any]]] = {}


def supported(supplier: Supplier) -> frozenset[str]:
    """Категории (игры), для которых поставщик проверяет аккаунт."""
    global _supported
    with _lock:
        if _supported and time.monotonic() - _supported[0] < _TTL:
            return _supported[1]
    try:
        cats = frozenset(supplier.validate_id_categories())
    except (SupplierError, AttributeError):
        cats = frozenset()
    with _lock:
        _supported = (time.monotonic(), cats)
    return cats


def can_check(supplier: Supplier, product: dict[str, Any]) -> bool:
    return product["kind"] == "topup" and product["category_id"] in supported(supplier)


def check(supplier: Supplier, product: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    """{"valid": True/False/None, "player_name", "region", "message"}. None — проверить не удалось."""
    category = product["category_id"]
    key = (category, tuple(sorted((k, v.strip()) for k, v in fields.items())))
    with _lock:
        hit = _results.get(key)
        if hit and time.monotonic() - hit[0] < 300:
            return hit[1]
    try:
        result = supplier.validate_account(category, {k: v.strip() for k, v in fields.items()})
    except SupplierRejected as exc:
        result = {"valid": False, "message": str(exc)}
    except SupplierError:
        return {"valid": None, "message": "Проверка сейчас недоступна."}
    result = {"valid": bool(result.get("valid")), "player_name": result.get("player_name") or None,
              "region": result.get("region") or None, "message": result.get("message") or ""}
    with _lock:
        if len(_results) > 5000:
            _results.clear()
        _results[key] = (time.monotonic(), result)
    return result


def reset() -> None:
    global _supported
    with _lock:
        _supported = None
        _results.clear()
