"""Игрушечный поставщик: чтобы сайт работал без ключа FazerCards и для тестов.
Заказы выполняются со второго запроса статуса и выдают фейковые коды."""

from __future__ import annotations

import secrets
import threading
from decimal import Decimal
from typing import Any, Iterable

from .base import ProductData, SupplierOrder, SupplierRejected, SupplierUnavailable

_TG_FIELD = [{"key": "telegram_username", "label": "Telegram @username", "type": "text"}]
_PLAYER_FIELD = [{"key": "player_id", "label": "Player ID", "type": "text"}]


def demo_catalog() -> list[ProductData]:
    items = [
        ProductData("tg-stars", "telegram_stars", "telegram", "Telegram", "Telegram Stars",
                    Decimal("0.015375"), unit="star", min_qty=50, max_qty=10000, fields=_TG_FIELD),
    ]
    items.append(ProductData("steam-topup", "steam_topup", "steam", "Steam", "Пополнение Steam",
                             Decimal("0.975"), unit="usd",
                             fields=[{"key": "steam_login", "label": "Логин Steam", "type": "text"},
                                     {"key": "currency", "label": "Валюта", "type": "select"},
                                     {"key": "amount", "label": "Сумма", "type": "number"}],
                             supplier_ref={"rates": {"USD": "1", "RUB": "92.5", "KZT": "520", "UAH": "41.2"},
                                           "min_usd": "0.5", "max_usd": "1000"}))
    for months, price in ((3, "12.2898"), (6, "16.3898"), (12, "29.7148")):
        items.append(ProductData(f"tg-premium-{months}", "telegram_premium", "telegram", "Telegram",
                                 f"Telegram Premium — {months} мес.", Decimal(price),
                                 fields=_TG_FIELD, supplier_ref={"months": months}))
    for uc, price in ((60, "0.99"), (325, "4.75"), (660, "9.40"), (1800, "23.50")):
        items.append(ProductData(f"topup-pubg-{uc}", "topup", "pubg_mobile", "PUBG Mobile",
                                 f"{uc} UC", Decimal(price), fields=_PLAYER_FIELD,
                                 supplier_ref={"category_id": "pubg_mobile", "offer_id": f"uc{uc}"}))
    for dm, price in ((100, "0.95"), (520, "4.60")):
        items.append(ProductData(f"topup-ff-{dm}", "topup", "free_fire", "Free Fire",
                                 f"{dm} алмазов", Decimal(price), fields=_PLAYER_FIELD,
                                 supplier_ref={"category_id": "free_fire", "offer_id": f"d{dm}"}))
    for usd, price in ((5, "5.2500"), (10, "10.5000"), (20, "20.9000")):
        items.append(ProductData(f"gc-steam-{usd}", "gift_card", "steam_usd", "Steam USD",
                                 f"Steam — ${usd}", Decimal(price), max_qty=10, stock=50,
                                 supplier_ref={"category_id": "steam_usd", "card_id": f"s{usd}"}))
    return items


class MockSupplier:
    name = "mock"

    def __init__(self, catalog: list[ProductData] | None = None, balance: Decimal = Decimal("1000")):
        self._catalog = catalog if catalog is not None else demo_catalog()
        self._balance = balance
        self._orders: dict[str, dict[str, Any]] = {}
        self._by_idem: dict[str, str] = {}
        self._lock = threading.Lock()
        # Для тестов: следующий create_order упадёт так, как задано.
        self.fail_next: str | None = None  # "reject" | "unavailable" | "unavailable_after_create"
        self.fail_on_poll = False
        self.polls_to_complete = 1

    def fetch_catalog(self) -> Iterable[ProductData]:
        return list(self._catalog)

    def is_idempotent(self, kind: str) -> bool:
        return kind in ("topup", "gift_card", "steam_topup")

    def check_steam_login(self, login: str) -> bool:
        return not login.lower().startswith("bad")

    def create_order(self, product, quantity, fields, idem_key) -> SupplierOrder:
        with self._lock:
            mode, self.fail_next = self.fail_next, None
            if mode == "reject":
                raise SupplierRejected("Недостаточно средств у поставщика", code="insufficient_balance",
                                       http_status=400)
            if mode == "unavailable":
                raise SupplierUnavailable("timeout")
            if idem_key in self._by_idem:
                oid = self._by_idem[idem_key]
            else:
                oid = f"ord-{secrets.randbelow(9_000_000) + 1_000_000}"
                self._by_idem[idem_key] = oid
                self._orders[oid] = {"product": product, "quantity": quantity, "fields": fields, "polls": 0}
            if mode == "unavailable_after_create":
                raise SupplierUnavailable("timeout after create")
            return SupplierOrder(order_id=oid, status="processing", raw_status="processing")

    def get_order(self, supplier_order_id: str) -> SupplierOrder:
        with self._lock:
            if self.fail_on_poll:
                return SupplierOrder(supplier_order_id, "failed", "failed", message="Игрок не найден")
            order = self._orders.get(supplier_order_id)
            if order is None:
                raise SupplierRejected("order not found", http_status=404)
            order["polls"] += 1
            if order["polls"] < self.polls_to_complete:
                return SupplierOrder(supplier_order_id, "processing", "processing")
            product = order["product"]
            if product["kind"] == "gift_card":
                codes = [f"DEMO-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
                         for _ in range(order["quantity"])]
                delivery = {"codes": codes}
            else:
                delivery = {"message": "Зачислено на аккаунт"}
            return SupplierOrder(supplier_order_id, "completed", "completed", delivery=delivery)

    def balance(self) -> Decimal:
        return self._balance
