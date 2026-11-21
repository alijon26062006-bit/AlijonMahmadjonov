"""Поставщик Telegram Stars и Premium (API v2: /telegram/stars, /telegram/premium, /orders, /balance).

Создание заказа — с Idempotency-Key: при обрыве связи повторяем тем же ключом, поставщик не создаст второй заказ.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

log = logging.getLogger(__name__)

_FAILED = ("refund", "cancel", "fail", "reject", "error", "expire", "return", "revers", "declin", "void",
           "timeout", "not_found", "abort", "denied", "возврат", "отмен", "ошибк", "отклон")
_DONE = ("complet", "success", "succeed", "deliver", "fulfil", "done", "выполн", "доставл", "успеш")


class SupplierError(Exception):
    """Поставщик ответил отказом (ошибка в данных, нет денег у реселлера и т.п.) — заказ не создан."""


class SupplierUnavailable(Exception):
    """Нет связи или сбой у поставщика — неизвестно, создан ли заказ. Повторять тем же ключом."""


@dataclass
class SupplierOrder:
    id: str | None
    status: str          # processing | completed | failed
    raw: str = ""
    message: str = ""


def normalize(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    if "partial" in v:
        return "processing"   # частично — решает админ, не возвращаем автоматически
    if any(r in v for r in _FAILED):
        return "failed"
    if any(r in v for r in _DONE):
        return "completed"
    return "processing"


class Supplier:
    def __init__(self, api_key: str, base_url: str, transport: httpx.BaseTransport | None = None, timeout: float = 45):
        if not api_key:
            raise ValueError("SITORA_FAZER_KEY не задан")
        self._c = httpx.Client(base_url=base_url, timeout=timeout, transport=transport,
                               headers={"X-API-Key": api_key, "Accept": "application/json"})

    def _req(self, method: str, path: str, **kw) -> dict[str, Any]:
        for attempt in range(3):
            try:
                r = self._c.request(method, path, **kw)
            except httpx.HTTPError as exc:
                raise SupplierUnavailable(f"{method} {path}: {exc}") from exc
            if r.status_code == 429 and attempt < 2 and method == "GET":
                time.sleep(float(r.headers.get("Retry-After") or 2))
                continue
            break
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 500 or r.status_code in (408, 429):
            raise SupplierUnavailable(f"{method} {path}: HTTP {r.status_code}")
        if r.status_code >= 400 or not data.get("ok", False):
            raise SupplierError(str(data.get("error") or data.get("message") or f"HTTP {r.status_code}"))
        return data

    def stars_info(self) -> dict[str, Any]:
        d = self._req("GET", "/telegram/stars")
        return {"price_per_star": Decimal(str(d["price_per_star"])), "min": int(d.get("min_amount", 50)),
                "max": int(d.get("max_amount", 10000))}

    def premium_plans(self) -> list[dict[str, Any]]:
        d = self._req("GET", "/telegram/premium")
        return [{"months": int(p["months"]), "price_usd": Decimal(str(p["price_usd"]))} for p in d.get("plans", [])]

    def buy_stars(self, username: str, qty: int, idem: str) -> SupplierOrder:
        return self._buy("/telegram/stars/buy", {"telegram_username": username, "quantity": qty}, idem)

    def buy_premium(self, username: str, months: int, idem: str) -> SupplierOrder:
        return self._buy("/telegram/premium/buy", {"telegram_username": username, "months": months}, idem)

    def _buy(self, path: str, body: dict[str, Any], idem: str) -> SupplierOrder:
        d = self._req("POST", path, json=body, headers={"Idempotency-Key": idem})
        o = d.get("order") or {}
        raw = str(o.get("status") or d.get("status") or "processing")
        oid = o.get("id") or d.get("order_id")
        return SupplierOrder(str(oid) if oid else None, normalize(raw), raw)

    def get_order(self, oid: str) -> SupplierOrder:
        d = self._req("GET", f"/orders/{oid}")
        o = d.get("order") if isinstance(d.get("order"), dict) else d
        raw = str(o.get("status") or o.get("state") or d.get("status") or "")
        if o.get("refunded") is True:
            raw = raw or "refunded"
        return SupplierOrder(oid, normalize(raw), raw, str(o.get("error") or o.get("message") or ""))

    def balance(self) -> Decimal:
        d = self._req("GET", "/balance")
        for k in ("balance", "amount", "available"):
            if d.get(k) is not None:
                return Decimal(str(d[k]).replace(",", ""))
        bal = d.get("data") or {}
        return Decimal(str(bal.get("balance", 0)))
