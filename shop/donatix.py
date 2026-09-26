"""Пайвасти Donatix — танҳо барои Telegram Stars ва Telegram Premium.

Ҳуҷҷатҳо: https://donatix.tj/api/v1 (панел → API).

*   ``GET  /products?kind=telegram_stars|telegram_premium`` — моли дуруст ва нарх
*   ``POST /accounts/check`` — санҷиши @username пеш аз пардохт
*   ``POST /orders`` бо ``Idempotency-Key`` — фармоиш
*   ``GET  /orders/{order_id}`` — ҳолат: processing → completed | failed

Калиди такрор (Idempotency-Key) барои ҳар фармоиши мо доимист. Бинобар ин
такрори дархост — пас аз таймаут ё азнавоғозкунии бот — пулро дубора
намегирад: Donatix ҳамон фармоиши аввалро бармегардонад.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from .supplier import CheckResult, OrderResult

log = logging.getLogger(__name__)

DONATIX_BASE = "https://donatix.tj/api/v1"

KIND_STARS = "telegram_stars"
KIND_PREMIUM = "telegram_premium"

ERRORS = {
    "missing_field": "Маълумоти фармоиш нопурра аст",
    "invalid_field": "Username нодуруст аст",
    "invalid_quantity": "Миқдор нодуруст аст",
    "account_not_found": "Аккаунти Telegram пайдо нашуд",
    "unauthorized": "Калиди Donatix нодуруст аст",
    "insufficient_balance": "Баланси таъминкунанда кофӣ нест",
    "account_inactive": "Аккаунти таъминкунанда фаъол нест",
    "account_blocked": "Аккаунти таъминкунанда баста шудааст",
    "product_not_found": "Ин мол дар таъминкунанда нест",
    "not_found": "Ин мол дар таъминкунанда нест",
    "out_of_stock": "Мол дар таъминкунанда тамом шудааст",
    "rate_limited": "Дархостҳо хеле зиёданд, каме сабр кунед",
}

#: Ин ҷавобҳо маънои «фармоиш шояд аллакай ҳаст»-ро доранд.
UNSURE_CODES = {"idempotency_key_reused"}

CATALOG_TTL = 600          # сония — каталог дар хотир
RETRIES = 3                # такрори фармоиш бо ҳамон калид


def _money(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _months_in(item: dict) -> set[int]:
    """«Telegram Premium 3 месяца», «tg-premium-12m» → {3} / {12}."""
    text = f"{item.get('name', '')} {item.get('product_id', '')}".lower()
    found = {int(n) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", text) if int(n) in (1, 3, 6, 12)}
    if not found and any(word in text for word in ("year", "год", "сол")):
        found.add(12)
    return found


class DonatixSupplier:
    """Муштарии Donatix API."""

    name = "donatix"
    # Фармоишро бо ҳамон калид бехатар такрор кардан мумкин аст.
    idempotent = True

    def __init__(
        self, api_key: str, base_url: str = DONATIX_BASE, *,
        key_prefix: str = "almaz", timeout: float = 35.0, retry_pause: float = 2.0,
    ) -> None:
        self.base_url = (base_url or DONATIX_BASE).rstrip("/")
        self.api_key = api_key
        self.key_prefix = key_prefix
        self.timeout = timeout
        self.retry_pause = retry_pause
        self._session = None
        self._lock = asyncio.Lock()
        self._catalog: dict[str, tuple[float, list[dict]]] = {}

    # ── дохилӣ ────────────────────────────────────────────────────────
    async def _get_session(self):
        import aiohttp

        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                )
        return self._session

    async def _request(
        self, method: str, path: str, *, headers: dict | None = None, **kwargs
    ) -> tuple[int, dict, dict]:
        """(HTTP-код, ҷавоб, сарлавҳаҳо). Хатои шабака берун мепарад."""
        session = await self._get_session()
        async with session.request(
            method, f"{self.base_url}{path}", headers=headers, **kwargs
        ) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}
            return resp.status, (data if isinstance(data, dict) else {}), dict(resp.headers)

    @staticmethod
    def _error(data: dict, status: int) -> tuple[str, str | None]:
        code = data.get("code")
        if isinstance(data.get("error"), dict):          # агар шакл дигар бошад
            code = code or data["error"].get("code")
            message = data["error"].get("message")
        else:
            message = data.get("error") or data.get("message")
        return ERRORS.get(code or "", message or f"HTTP {status}"), code

    def idempotency_key(self, order_id: str) -> str:
        return f"{self.key_prefix}-order-{order_id}"

    # ── каталог ───────────────────────────────────────────────────────
    async def items(self, kind: str) -> list[dict]:
        """Молҳои як навъ (бо нархи шумо). Хато → рӯйхати холӣ."""
        cached = self._catalog.get(kind)
        if cached and time.monotonic() - cached[0] < CATALOG_TTL:
            return cached[1]
        try:
            status, data, _ = await self._request("GET", "/products", params={"kind": kind})
        except Exception as exc:
            log.warning("Donatix /products дастнорас: %s", exc)
            return cached[1] if cached else []
        items = data.get("items") if status == 200 else None
        if not isinstance(items, list):
            log.warning("Donatix /products: HTTP %s %s", status, data.get("code"))
            return cached[1] if cached else []
        items = [i for i in items if isinstance(i, dict) and i.get("product_id")]
        self._catalog[kind] = (time.monotonic(), items)
        return items

    async def resolve(self, kind: str, amount: int) -> tuple[dict, int] | None:
        """Моли Donatix ва миқдор барои моли мо.

        Stars: як мол, миқдор = шумораи ситораҳо.
        Premium: ё як мол бо миқдор = моҳҳо, ё моли алоҳида барои 3/6/12 моҳ.
        """
        if kind == "stars":
            for item in await self.items(KIND_STARS):
                low = int(_money(item.get("min_quantity")) or 1)
                high = int(_money(item.get("max_quantity")) or 10**9)
                if low <= amount <= high:
                    return item, amount
            return None

        if kind == "premium":
            items = await self.items(KIND_PREMIUM)
            # 1) Моли алоҳида барои ҳамин муддат.
            for item in items:
                if amount in _months_in(item):
                    return item, int(_money(item.get("min_quantity")) or 1)
            # 2) Як мол, ки моҳҳоро ҳамчун миқдор мегирад.
            for item in items:
                unit = str(item.get("unit", "")).lower()
                low = int(_money(item.get("min_quantity")) or 1)
                high = int(_money(item.get("max_quantity")) or 0)
                if ("month" in unit or "мес" in unit or "моҳ" in unit) and low <= amount <= high:
                    return item, amount
        return None

    @staticmethod
    def field_key(item: dict) -> str:
        for field in item.get("fields") or []:
            if isinstance(field, dict) and field.get("key"):
                return str(field["key"])
        return "telegram_username"

    @staticmethod
    def username(target: str) -> str:
        return "@" + str(target).strip().lstrip("@")

    async def cost_usd(self, kind: str, amount: int) -> float | None:
        """Нархи харид барои панел (доллар)."""
        found = await self.resolve(kind, amount)
        if found is None:
            return None
        item, quantity = found
        price = _money(item.get("price_usd"))
        return round(price * quantity, 4) if price else None

    # ── санҷиши username ──────────────────────────────────────────────
    async def check(
        self, *, kind: str, sku: str, target: str, amount: int, server: str = ""
    ) -> CheckResult:
        try:
            found = await self.resolve(kind, amount)
            if found is None:
                return CheckResult(
                    target=target, ok=False, error="Ин мол дар таъминкунанда нест"
                )
            item, _ = found
            status, data, _ = await self._request(
                "POST", "/accounts/check",
                json={
                    "product_id": item["product_id"],
                    "fields": {self.field_key(item): self.username(target)},
                },
            )
            if status == 200 and data.get("ok") is not False:
                if data.get("supported") is False:
                    # Donatix ин навъро намесанҷад — харидор худаш тасдиқ мекунад.
                    return CheckResult(target=target, nickname=None, ok=True)
                if data.get("valid") is True:
                    return CheckResult(
                        target=target,
                        nickname=data.get("player_name") or self.username(target),
                        ok=True,
                    )
                return CheckResult(target=target, ok=False, error="Username пайдо нашуд")
            message, _ = self._error(data, status)
            return CheckResult(target=target, ok=False, error=message)
        except Exception as exc:
            log.warning("Donatix: тафтиши %s нашуд: %s", target, exc)
            return CheckResult(target=target, ok=False, error="Вақти тафтиш гузашт")

    # ── фармоиш ───────────────────────────────────────────────────────
    async def place_order(
        self, *, kind: str, sku: str, target: str, amount: int, order_id: str,
        server: str = "",
    ) -> OrderResult:
        found = await self.resolve(kind, amount)
        if found is None:
            # Ҳеҷ чиз фиристода нашуд — пулро баргардонидан бехатар аст.
            return OrderResult(
                ok=False, code="product_not_found",
                error=f"Donatix барои «{kind} × {amount}» мол надорад",
            )
        item, quantity = found
        payload = {
            "product_id": item["product_id"],
            "quantity": quantity,
            "fields": {self.field_key(item): self.username(target)},
        }
        headers = {
            "Idempotency-Key": self.idempotency_key(order_id),
            "Content-Type": "application/json",
        }

        last_error = "ҷавоб наомад"
        for attempt in range(1, RETRIES + 1):
            try:
                status, data, resp_headers = await self._request(
                    "POST", "/orders", json=payload, headers=headers
                )
            except Exception as exc:
                # Таймаут: фармоиш шояд сохта шуд. Ҳамон калид — пул дубора намеравад.
                last_error = f"Хатои шабака: {exc}"
                log.warning("Donatix: фармоиши %s — %s (кӯшиши %s)", order_id, exc, attempt)
                await asyncio.sleep(self.retry_pause * attempt)
                continue

            order = data.get("order") if isinstance(data.get("order"), dict) else None
            if status in (200, 201) and data.get("ok") is not False and order:
                return OrderResult(
                    ok=True,
                    external_id=str(order.get("order_id") or "") or None,
                    status=order.get("status"),
                )
            message, code = self._error(data, status)
            if status == 429 and attempt < RETRIES:
                wait = min(_money(resp_headers.get("Retry-After")) or 5, 15)
                await asyncio.sleep(wait)
                continue
            if status >= 500:
                last_error = message
                await asyncio.sleep(self.retry_pause * attempt)
                continue
            return OrderResult(
                ok=False, error=message, code=code, uncertain=code in UNSURE_CODES
            )
        return OrderResult(ok=False, error=last_error, uncertain=True)

    # ── ҳолат ─────────────────────────────────────────────────────────
    async def order_status(self, external_id: str, *, by_external: bool = False) -> OrderResult:
        if by_external:
            # Donatix ҷустуҷӯ бо рақами мо надорад; ба ҷои он фармоишро бо
            # ҳамон Idempotency-Key такрор мекунем (ниг. fulfillment).
            return OrderResult(ok=False, code="lookup_unsupported", error="lookup_unsupported")
        try:
            status, data, _ = await self._request("GET", f"/orders/{external_id}")
        except Exception as exc:
            return OrderResult(ok=False, error=str(exc))
        order = data.get("order") if isinstance(data.get("order"), dict) else None
        if status == 200 and order:
            return OrderResult(
                ok=True, external_id=str(external_id), status=order.get("status"),
                error=order.get("error"),
            )
        message, code = self._error(data, status)
        return OrderResult(ok=False, error=message, code=code)

    async def wait_until_done(
        self, external_id: str, *, by_external: bool = False,
        max_wait: int = 180, interval: int = 6,
    ) -> OrderResult:
        """Donatix тавсия медиҳад: ҳар 5–10 сония пурсед."""
        waited = 0
        last = OrderResult(ok=False, error="timeout")
        while waited < max_wait:
            result = await self.order_status(external_id, by_external=by_external)
            if result.ok:
                last = result
                if result.status in ("completed", "failed", "refunded"):
                    return result
            await asyncio.sleep(interval)
            waited += interval
        return last

    # ── баланс ────────────────────────────────────────────────────────
    async def balance(self) -> dict[str, Any]:
        try:
            status, data, _ = await self._request("GET", "/balance")
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        if status == 200 and data.get("ok") is not False:
            return {
                "ok": True,
                "balance": data.get("balance"),
                "currency": data.get("currency", "USD"),
            }
        message, _ = self._error(data, status)
        return {"ok": False, "error": message}

    async def products(self) -> dict[str, dict]:
        return {}

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
