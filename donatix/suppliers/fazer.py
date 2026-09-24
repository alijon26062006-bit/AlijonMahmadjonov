"""Клиент FazerCards API v2 (см. docs/fazercards/api-reference.md).

Что умеет: каталог Telegram Stars/Premium, игровых пополнений и подарочных карт,
создание заказов, статус заказа, баланс. Steam, ключи игр и ручные услуги —
следующий шаг."""

from __future__ import annotations

import hashlib
import logging
import random
import time
from decimal import Decimal
from typing import Any, Iterable

import httpx

from .base import (
    ProductData,
    SupplierOrder,
    SupplierRejected,
    SupplierUnavailable,
    normalize_status,
)

log = logging.getLogger(__name__)

# Для этих видов в документации заявлен Idempotency-Key: повтор с тем же ключом
# не создаст второй заказ. Для Telegram-покупок заголовок не упомянут —
# такие заказы при сбое сети не повторяем автоматически, а отдаём админу.
_IDEMPOTENT_KINDS = {"topup", "gift_card"}


def _pid(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:10]
    return f"{prefix}-{digest}"


class FazerSupplier:
    name = "fazer"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.fzr.cards/api/v2",
        *,
        transport: httpx.BaseTransport | None = None,
        catalog_pause: float = 0.6,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("FAZER_API_KEY не задан")
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        # Каталог читаем не чаще ~100 запросов в минуту (их лимит — 120).
        self._catalog_pause = catalog_pause

    # ── HTTP ──────────────────────────────────────────────────

    def _request(self, method: str, path: str, *, retry_429: bool = True, **kwargs) -> dict[str, Any]:
        for attempt in range(3):
            try:
                resp = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise SupplierUnavailable(f"{method} {path}: {exc}") from exc
            if resp.status_code == 429 and retry_429 and attempt < 2:
                wait = float(resp.headers.get("Retry-After", "2") or 2)
                time.sleep(wait * random.uniform(1.0, 1.15))
                continue
            break
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 500 or resp.status_code in (408, 429):
            raise SupplierUnavailable(f"{method} {path}: HTTP {resp.status_code}")
        if resp.status_code >= 400 or not data.get("ok", False):
            raise SupplierRejected(
                str(data.get("error") or f"HTTP {resp.status_code}"),
                code=str(data.get("code") or ""),
                http_status=resp.status_code,
            )
        return data

    def _catalog_get(self, path: str, **params) -> dict[str, Any] | None:
        """GET каталога; недоступные тарифу разделы (403) пропускаем."""
        time.sleep(self._catalog_pause)
        try:
            return self._request("GET", path, params=params)
        except SupplierRejected as exc:
            if exc.http_status in (403, 404):
                log.info("fazer: %s недоступен (%s)", path, exc)
                return None
            raise

    def _paged(self, path: str) -> Iterable[dict[str, Any]]:
        cursor = None
        while True:
            params: dict[str, Any] = {"limit": 50}
            if cursor:
                params["cursor"] = cursor
            data = self._catalog_get(path, **params)
            if not data:
                return
            yield from data.get("items", [])
            meta = data.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not meta.get("has_more") or not cursor:
                return

    # ── Каталог ───────────────────────────────────────────────

    def fetch_catalog(self) -> Iterable[ProductData]:
        yield from self._telegram()
        yield from self._topups()
        yield from self._giftcards()

    def _telegram(self) -> Iterable[ProductData]:
        stars = self._catalog_get("/telegram/stars")
        if stars:
            yield ProductData(
                id="tg-stars",
                kind="telegram_stars",
                category_id="telegram",
                category_name="Telegram",
                name="Telegram Stars",
                base_price=Decimal(str(stars["price_per_star"])),
                unit="star",
                min_qty=int(stars.get("min_amount", 50)),
                max_qty=int(stars.get("max_amount", 10000)),
                fields=[{"key": "telegram_username", "label": "Telegram @username", "type": "text"}],
                supplier_ref={},
            )
        premium = self._catalog_get("/telegram/premium")
        for plan in (premium or {}).get("plans", []):
            months = int(plan["months"])
            yield ProductData(
                id=f"tg-premium-{months}",
                kind="telegram_premium",
                category_id="telegram",
                category_name="Telegram",
                name=f"Telegram Premium — {months} мес.",
                base_price=Decimal(str(plan["price_usd"])),
                fields=[{"key": "telegram_username", "label": "Telegram @username", "type": "text"}],
                supplier_ref={"months": months},
            )

    def _topups(self) -> Iterable[ProductData]:
        for cat in list(self._paged("/topups")):
            cat_id = str(cat["category_id"])
            data = self._catalog_get("/topups/offers", category_id=cat_id)
            if not data:
                continue
            fields = [
                {"key": str(f["key"]), "label": str(f.get("label") or f["key"]), "type": str(f.get("type") or "text")}
                for f in data.get("fields", [])
            ]
            for offer in data.get("offers", []):
                yield ProductData(
                    id=_pid("topup", cat_id, str(offer["offer_id"])),
                    kind="topup",
                    category_id=cat_id,
                    category_name=str(data.get("name") or cat.get("name") or cat_id),
                    name=str(offer["name"]),
                    base_price=Decimal(str(offer["price_usd"])),
                    fields=fields,
                    supplier_ref={"category_id": cat_id, "offer_id": str(offer["offer_id"])},
                )

    def _giftcards(self) -> Iterable[ProductData]:
        for cat in list(self._paged("/giftcards")):
            cat_id = str(cat["category_id"])
            data = self._catalog_get("/giftcards/cards", category_id=cat_id)
            if not data:
                continue
            for offer in data.get("offers", []):
                yield ProductData(
                    id=_pid("gc", cat_id, str(offer["card_id"])),
                    kind="gift_card",
                    category_id=cat_id,
                    category_name=str(data.get("name") or cat.get("name") or cat_id),
                    name=str(offer["name"]),
                    base_price=Decimal(str(offer["price_usd"])),
                    min_qty=int(offer.get("min_order_quantity") or 1),
                    max_qty=min(int(offer.get("max_order_quantity") or 1), 100),
                    stock=int(offer["stock"]) if offer.get("stock") is not None else None,
                    supplier_ref={"category_id": cat_id, "card_id": str(offer["card_id"])},
                )

    # ── Заказы ────────────────────────────────────────────────

    def is_idempotent(self, kind: str) -> bool:
        return kind in _IDEMPOTENT_KINDS

    def create_order(
        self, product: dict[str, Any], quantity: int, fields: dict[str, str], idem_key: str
    ) -> SupplierOrder:
        kind = product["kind"]
        ref = product["supplier_ref"]
        headers = {"Idempotency-Key": idem_key}
        if kind == "telegram_stars":
            path, body = "/telegram/stars/buy", {
                "telegram_username": fields["telegram_username"],
                "quantity": quantity,
            }
        elif kind == "telegram_premium":
            path, body = "/telegram/premium/buy", {
                "telegram_username": fields["telegram_username"],
                "months": ref["months"],
            }
        elif kind == "topup":
            path, body = "/topups/order", {
                "category_id": ref["category_id"],
                "offer_id": ref["offer_id"],
                "fields": fields,
            }
        elif kind == "gift_card":
            path, body = "/giftcards/order", {
                "category_id": ref["category_id"],
                "card_id": ref["card_id"],
                "quantity": quantity,
            }
        else:
            raise SupplierRejected(f"вид товара {kind} не поддерживается")
        # Создание заказа не повторяем на 429 сами: решение о повторе — у воркера.
        data = self._request("POST", path, json=body, headers=headers, retry_429=False)
        order = data.get("order") or {}
        order_id = order.get("id") or data.get("order_id")
        raw = str(order.get("status") or data.get("status") or "processing")
        return SupplierOrder(order_id=str(order_id) if order_id else None, status=normalize_status(raw), raw_status=raw)

    def get_order(self, supplier_order_id: str) -> SupplierOrder:
        data = self._request("GET", f"/orders/{supplier_order_id}")
        order = data.get("order") or {}
        raw = str(order.get("status") or "")
        payload = order.get("payload")
        return SupplierOrder(
            order_id=supplier_order_id,
            status=normalize_status(raw),
            raw_status=raw,
            delivery=payload if isinstance(payload, dict) else ({"payload": payload} if payload else None),
            message=str(order.get("error") or order.get("message") or ""),
        )

    def balance(self) -> Decimal:
        data = self._request("GET", "/balance")
        return Decimal(str(data["balance"]))
