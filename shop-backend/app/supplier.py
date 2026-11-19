"""Client for the supplier API (read-only part for step 1).

The API key is read from settings (.env) and is never logged or returned to clients.
"""
import logging
import time
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("supplier")


class SupplierError(Exception):
    """Supplier answered with an error or is unreachable."""

    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def outcome_unknown(self) -> bool:
        """True when we can't know whether the supplier accepted (and charged) the request:
        timeout / connection error / 5xx / unreadable success. 4xx means it was rejected."""
        if self.code in ("unreachable",):
            return True
        if self.code == "no_key":
            return False
        return self.status is None or self.status >= 500 or (self.code == "bad_json" and self.status < 400)


class SupplierClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0, transport=None):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/api/v2",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self._has_key = bool(api_key)

    def close(self):
        self._client.close()

    def _req(self, method: str, path: str, **kw) -> dict[str, Any]:
        if not self._has_key:
            raise SupplierError("Ключ поставщика не задан (SUPPLIER_API_KEY в .env)", code="no_key")
        t0 = time.monotonic()
        try:
            r = self._client.request(method, path, **kw)
        except httpx.HTTPError as e:
            log.warning("supplier %s %s failed: %s", method, path, type(e).__name__)
            raise SupplierError("Поставщик недоступен, попробуйте позже", code="unreachable") from e
        ms = int((time.monotonic() - t0) * 1000)
        log.info("supplier %s %s -> %s in %sms", method, path, r.status_code, ms)
        try:
            data = r.json()
        except ValueError:
            raise SupplierError("Поставщик вернул неверный ответ", status=r.status_code, code="bad_json")
        if r.status_code >= 400 or not data.get("ok", False):
            raise SupplierError(str(data.get("error") or "Ошибка поставщика"), status=r.status_code,
                                code=data.get("code"))
        return data

    # ---- account ----
    def me(self) -> dict:
        return self._req("GET", "/me")

    def balance(self) -> dict:
        return self._req("GET", "/balance")

    # ---- top-ups ----
    def topup_categories(self) -> list[dict]:
        items, cursor = [], None
        for _ in range(50):  # safety cap on pages
            params = {"limit": "500"}
            if cursor:
                params["cursor"] = cursor
            data = self._req("GET", "/topups", params=params)
            items.extend(data.get("items", []))
            meta = data.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not meta.get("has_more") or not cursor:
                break
        return items

    def topup_offers(self, category_id: str) -> dict:
        return self._req("GET", "/topups/offers", params={"category_id": category_id})

    def validate_id_games(self) -> list[dict]:
        return self._req("GET", "/topups/validate-id").get("items", [])

    def validate_id(self, category_id: str, fields: dict[str, str]) -> dict:
        return self._req("POST", "/topups/validate-id", json={"category_id": category_id, "fields": fields})

    def topup_order(self, category_id: str, offer_id: str, fields: dict[str, str], idempotency_key: str) -> dict:
        return self._req("POST", "/topups/order", headers={"Idempotency-Key": idempotency_key},
                         json={"category_id": category_id, "offer_id": offer_id, "fields": fields})

    # ---- telegram ----
    def telegram_stars(self) -> dict:
        return self._req("GET", "/telegram/stars")

    def telegram_premium(self) -> dict:
        return self._req("GET", "/telegram/premium")

    def telegram_stars_buy(self, username: str, quantity: int) -> dict:
        # NB: the supplier documents no Idempotency-Key for Telegram — never auto-retry this call
        return self._req("POST", "/telegram/stars/buy", json={"telegram_username": username, "quantity": quantity})

    def telegram_premium_buy(self, username: str, months: int) -> dict:
        return self._req("POST", "/telegram/premium/buy", json={"telegram_username": username, "months": months})

    # ---- orders ----
    def get_order(self, supplier_order_id: str) -> dict:
        return self._req("GET", f"/orders/{supplier_order_id}")


class TTLCache:
    def __init__(self):
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, ttl: int, loader):
        hit = self._data.get(key)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        value = loader()
        self._data[key] = (time.monotonic(), value)
        return value

    def clear(self):
        self._data.clear()


cache = TTLCache()
_client: SupplierClient | None = None


def get_supplier() -> SupplierClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = SupplierClient(s.supplier_api_url, s.supplier_api_key, s.supplier_timeout_seconds)
    return _client


def set_supplier(client: SupplierClient | None) -> None:
    """Used by tests to inject a client."""
    global _client
    _client = client
    cache.clear()
