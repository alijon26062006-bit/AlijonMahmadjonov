"""Проверка аккаунта игрока до оплаты: поставщик по ID возвращает ник.

Проверку умеют не все игры — список берём у поставщика и держим час в памяти.
Если поставщик недоступен, заказ не блокируем: проверка — подсказка, а не условие."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .suppliers import Supplier, SupplierError, SupplierRejected

log = logging.getLogger(__name__)
_TTL = 3600
_lock = threading.Lock()
_supported: tuple[float, frozenset[str]] | None = None
_results: dict[tuple, tuple[float, dict[str, Any]]] = {}
_flash: Any = None   # FlashTopup — запасная проверка ника, когда наш поставщик игру не проверяет


def configure(config: Any) -> None:
    """Ключи FlashTopup из .env — включают поиск ника по ID для игр, которые есть у них."""
    global _flash
    if getattr(config, "flashtopup_api_id", "") and getattr(config, "flashtopup_api_key", ""):
        from .flashtopup import FlashTopup
        _flash = FlashTopup(config.flashtopup_api_id, config.flashtopup_api_key)
    else:
        _flash = None


def _flash_game(product: dict[str, Any]) -> dict[str, Any] | None:
    if _flash is None or product.get("kind") != "topup":
        return None
    from .shopbot import base_name
    return _flash.match(base_name(product.get("category_name") or ""))


def _id_fields(fields: dict[str, str]) -> tuple[str, str]:
    """Наши поля → user_id и server_id FlashTopup: ID игрока — первое, сервер/зона — по названию."""
    server = next((v for k, v in fields.items() if any(w in k.lower() for w in ("server", "zone", "сервер"))), "")
    user = next((v for k, v in fields.items() if v and v != server), "")
    return user.strip(), server.strip()


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
    if product["kind"] != "topup":
        return False
    return product["category_id"] in supported(supplier) or _flash_game(product) is not None


def check(supplier: Supplier, product: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    """{"valid": True/False/None, "player_name", "region", "message"}. None — проверить не удалось."""
    category = product["category_id"]
    key = (category, tuple(sorted((k, v.strip()) for k, v in fields.items())))
    with _lock:
        hit = _results.get(key)
        if hit and time.monotonic() - hit[0] < 300:
            return hit[1]
    strict = True
    if category in supported(supplier):
        try:
            result = supplier.validate_account(category, {k: v.strip() for k, v in fields.items()})
        except SupplierRejected as exc:
            result = {"valid": False, "message": str(exc)}
        except SupplierError:
            return {"valid": None, "message": "Проверка сейчас недоступна."}
    else:
        game = _flash_game(product)
        user, server = _id_fields(fields)
        if game is None or not user:
            return {"valid": None, "message": "Проверка сейчас недоступна."}
        from .flashtopup import FlashError
        try:
            result = _flash.check_id(game["validation_code"], user, server)
        except FlashError as exc:
            log.warning("FlashTopup check-id: %s", exc)
            return {"valid": None, "message": "Проверка сейчас недоступна."}
        strict = False   # чужая проверка — ник показываем, но заказ из-за неё не блокируем
    result = {"valid": bool(result.get("valid")), "player_name": result.get("player_name") or None,
              "region": result.get("region") or None, "message": result.get("message") or "", "strict": strict}
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
