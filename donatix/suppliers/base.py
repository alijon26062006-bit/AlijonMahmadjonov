"""Общий интерфейс поставщика. Сегодня это FazerCards, завтра можно добавить второго."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Protocol

KINDS = ("telegram_stars", "telegram_premium", "topup", "gift_card")

KIND_TITLES = {
    "telegram_stars": "Telegram Stars",
    "telegram_premium": "Telegram Premium",
    "topup": "Пополнение игр",
    "gift_card": "Подарочные карты",
}


@dataclass
class ProductData:
    id: str
    kind: str
    category_id: str
    category_name: str
    name: str
    base_price: Decimal
    unit: str = "item"
    min_qty: int = 1
    max_qty: int = 1
    stock: int | None = None
    fields: list[dict[str, str]] = field(default_factory=list)
    supplier_ref: dict[str, Any] = field(default_factory=dict)


@dataclass
class SupplierOrder:
    order_id: str | None
    status: str  # processing | completed | failed
    raw_status: str = ""
    delivery: dict[str, Any] | None = None
    message: str = ""


class SupplierError(Exception):
    """Базовая ошибка поставщика."""


class SupplierRejected(SupplierError):
    """Поставщик точно отказал (4xx): заказа у него нет, деньги клиенту можно вернуть."""

    def __init__(self, message: str, code: str = "", http_status: int = 0):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class SupplierUnavailable(SupplierError):
    """Непонятно, прошёл ли запрос (таймаут, 5xx, сеть). Деньги не возвращаем,
    пока не выясним статус."""


# Статусы поставщика → наши. Точного списка в документации FazerCards нет,
# поэтому незнакомый статус считаем «ещё в работе».
_DONE = {"completed", "complete", "success", "succeeded", "delivered", "done", "fulfilled"}
_FAILED = {"failed", "fail", "error", "cancelled", "canceled", "rejected", "refunded", "declined", "expired"}


def normalize_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in _DONE:
        return "completed"
    if value in _FAILED:
        return "failed"
    return "processing"


class Supplier(Protocol):
    name: str

    def fetch_catalog(self) -> Iterable[ProductData]: ...

    def create_order(
        self, product: dict[str, Any], quantity: int, fields: dict[str, str], idem_key: str
    ) -> SupplierOrder: ...

    def get_order(self, supplier_order_id: str) -> SupplierOrder: ...

    def balance(self) -> Decimal: ...

    def is_idempotent(self, kind: str) -> bool:
        """Можно ли безопасно повторить создание заказа с тем же ключом."""
        ...
