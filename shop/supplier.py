"""Пайвасти таъминкунанда — FireLoot Partner API.

Се навъи мол:

*   ``game``   — Free Fire ва PUBG: ``POST /validate`` (лақаб) ва ``POST /order``
*   ``stars``  — Telegram Stars: ``POST /telegram/check`` ва ``POST /telegram/order``
*   ``manual`` — API надорад (масалан Premium): фармоишро админ дастӣ иҷро мекунад

Ҳамаи хатоҳо дар дохил гирифта мешаванд — бот аз сабаби таъминкунанда намеафтад.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

# Ҳолатҳои ниҳоии фармоиш дар FireLoot
FINAL_STATUSES = ("completed", "failed", "refunded")

CHECK_ERRORS = {
    "invalid_uid": "ID-и бозигар нодуруст аст",
    "invalid_request": "Дархост нопурра аст",
    "unauthorized": "Калиди API нодуруст аст",
    "region_unsupported": "Региони аккаунт дастгирӣ намешавад",
    "product_not_found": "Ин мол дар таъминкунанда нест",
    "rate_limited": "Дархостҳо хеле зиёданд, каме сабр кунед",
    "service_unavailable": "Хидмат вақтинча дастнорас аст",
    "not_found": "Username пайдо нашуд",
    "invalid_username": "Username нодуруст аст",
}

ORDER_ERRORS = {
    **CHECK_ERRORS,
    "insufficient_balance": "Баланси таъминкунанда кофӣ нест",
    "insufficient_stars_balance": "Баланси Stars-и таъминкунанда кофӣ нест",
    "duplicate_order": "Ин рақами фармоиш аллакай истифода шудааст",
    "order_not_found": "Фармоиш пайдо нашуд",
    "invalid_quantity": "Миқдор нодуруст аст",
}


@dataclass(frozen=True)
class CheckResult:
    """Натиҷаи тафтиши ID ё username."""

    target: str
    nickname: str | None = None
    ok: bool = True
    error: str | None = None


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    external_id: str | None = None   # рақами фармоиш дар таъминкунанда
    status: str | None = None
    error: str | None = None
    code: str | None = None
    # Ҷавоб наомад (шабака, таймаут, 5xx): фармоиш шояд ҚАБУЛ ШУДА бошад.
    # Дар ин ҳолат пулро худкор баргардонидан мумкин нест — аввал месанҷем.
    uncertain: bool = False


class Supplier(Protocol):
    name: str

    async def check(
        self, *, kind: str, sku: str, target: str, amount: int, server: str = ""
    ) -> CheckResult: ...

    async def place_order(
        self, *, kind: str, sku: str, target: str, amount: int, order_id: str,
        server: str = "",
    ) -> OrderResult: ...

    async def order_status(self, external_id: str, *, by_external: bool = False) -> OrderResult: ...

    async def balance(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class ManualSupplier:
    """Бе API: ҳама фармоишҳо дастӣ аз панели админ иҷро мешаванд."""

    name = "manual"

    async def check(
        self, *, kind: str, sku: str, target: str, amount: int, server: str = ""
    ) -> CheckResult:
        # Лақаб маълум нест — харидор худаш ID-и худро тасдиқ мекунад.
        return CheckResult(target=target, nickname=None, ok=True)

    async def place_order(
        self, *, kind: str, sku: str, target: str, amount: int, order_id: str,
        server: str = "",
    ) -> OrderResult:
        return OrderResult(ok=True, external_id=None, status=None)

    async def order_status(self, external_id: str, *, by_external: bool = False) -> OrderResult:
        return OrderResult(ok=False, error="manual")

    async def balance(self) -> dict[str, Any]:
        return {"ok": False, "error": "Реҷаи дастӣ — баланс нест"}

    async def close(self) -> None:
        return None


class FireLootSupplier:
    """Муштарии FireLoot Partner API."""

    name = "fireloot"

    def __init__(self, base_url: str, api_key: str, timeout: float = 35.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = None
        self._lock = asyncio.Lock()

    # ── дохилӣ ────────────────────────────────────────────────────────
    async def _get_session(self):
        import aiohttp

        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
        return self._session

    async def _request(self, method: str, path: str, **kwargs) -> tuple[int, dict]:
        session = await self._get_session()
        async with session.request(method, f"{self.base_url}{path}", **kwargs) as resp:
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {}
            return resp.status, (data if isinstance(data, (dict, list)) else {})

    @staticmethod
    def _error(data: dict, status: int, table: dict[str, str]) -> tuple[str, str | None]:
        """Ҷавоби хаторо ба матни фаҳмо табдил медиҳад."""
        err = data.get("error") if isinstance(data.get("error"), dict) else {}
        code = err.get("code") or data.get("code")
        message = err.get("message") or data.get("message") or f"HTTP {status}"
        return table.get(code, f"{code or status}: {message}"), code

    # ── тафтиши ID / username ─────────────────────────────────────────
    async def check(
        self, *, kind: str, sku: str, target: str, amount: int, server: str = ""
    ) -> CheckResult:
        if kind == "manual" or not self.base_url:
            return CheckResult(target=target, nickname=None, ok=True)
        try:
            if kind == "stars":
                username = target.lstrip("@").strip()
                status, data = await self._request(
                    "POST", "/telegram/check",
                    json={"username": username, "stars": int(amount)},
                )
                nickname = data.get("name") or username
            else:
                payload: dict[str, Any] = {"sku": sku, "uid": str(target)}
                if server:
                    payload["server_id"] = str(server)
                status, data = await self._request("POST", "/validate", json=payload)
                nickname = data.get("player_name")

            if status == 200 and data.get("valid") is True and nickname:
                return CheckResult(target=target, nickname=nickname, ok=True)
            message, _ = self._error(data, status, CHECK_ERRORS)
            return CheckResult(target=target, nickname=None, ok=False, error=message)
        except Exception as exc:
            log.warning("Тафтиши %s нашуд: %s", target, exc)
            return CheckResult(target=target, nickname=None, ok=False, error="Вақти тафтиш гузашт")

    # ── фиристодани фармоиш ───────────────────────────────────────────
    async def place_order(
        self, *, kind: str, sku: str, target: str, amount: int, order_id: str,
        server: str = "",
    ) -> OrderResult:
        if kind == "manual" or not self.base_url:
            return OrderResult(ok=True, external_id=None, status=None)
        try:
            if kind == "stars":
                status, data = await self._request(
                    "POST", "/telegram/order",
                    json={
                        "username": target.lstrip("@").strip(),
                        "stars": int(amount),
                        "external_id": str(order_id),
                    },
                )
            else:
                order_payload: dict[str, Any] = {
                    "external_id": str(order_id),
                    "sku": sku,
                    "uid": str(target),
                }
                if server:
                    order_payload["server_id"] = str(server)
                status, data = await self._request("POST", "/order", json=order_payload)

            if status in (200, 201):
                external = data.get("order_id") or data.get("id")
                return OrderResult(
                    ok=True,
                    external_id=str(external) if external else None,
                    status=data.get("status"),
                )
            message, code = self._error(data, status, ORDER_ERRORS)
            # 5xx ё ҷавоби бе коди хато — сервер шояд фармоишро аллакай сабт кардааст.
            unsure = status >= 500 or status == 0 or not code or code == "duplicate_order"
            return OrderResult(ok=False, error=message, code=code, uncertain=unsure)
        except Exception as exc:
            # Таймаут ё канда шудани пайваст: дархост шояд ба сервер расида бошад.
            log.warning("Фармоиши %s — ҷавоб наомад: %s", order_id, exc)
            return OrderResult(ok=False, error=f"Хатои шабака: {exc}", uncertain=True)

    # ── санҷиши ҳолат ─────────────────────────────────────────────────
    async def order_status(self, external_id: str, *, by_external: bool = False) -> OrderResult:
        if not self.base_url:
            return OrderResult(ok=False, error="API танзим нашудааст")
        path = f"/order/{external_id}" + ("?by=external" if by_external else "")
        try:
            status, data = await self._request("GET", path)
            if status == 200:
                return OrderResult(
                    ok=True, external_id=str(external_id), status=data.get("status")
                )
            message, code = self._error(data, status, ORDER_ERRORS)
            return OrderResult(ok=False, error=message, code=code)
        except Exception as exc:
            return OrderResult(ok=False, error=str(exc))

    async def wait_until_done(
        self, external_id: str, *, by_external: bool = False,
        max_wait: int = 120, interval: int = 4,
    ) -> OrderResult:
        """То ҳолати ниҳоӣ интизор мешавад (completed / failed / refunded)."""
        waited = 0
        last = OrderResult(ok=False, error="timeout")
        while waited < max_wait:
            result = await self.order_status(external_id, by_external=by_external)
            if result.ok:
                last = result
                if result.status in FINAL_STATUSES:
                    return result
            await asyncio.sleep(interval)
            waited += interval
        return last

    # ── баланс ва каталог ─────────────────────────────────────────────
    async def balance(self) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "error": "API танзим нашудааст"}
        try:
            status, data = await self._request("GET", "/balance")
            if status == 200:
                return {
                    "ok": True,
                    "balance": data.get("balance"),
                    "currency": data.get("currency", "USD"),
                    "stars_balance": data.get("stars_balance"),
                    "telegram_active": data.get("telegram_active"),
                }
            message, _ = self._error(data, status, ORDER_ERRORS)
            return {"ok": False, "error": message}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def products(self) -> dict[str, dict]:
        """Каталоги воқеии таъминкунанда — барои санҷиши SKU-ҳо."""
        if not self.base_url:
            return {}
        try:
            status, data = await self._request("GET", "/products")
            if status == 200 and isinstance(data, list):
                return {item["sku"]: item for item in data if "sku" in item}
            log.warning("GET /products: HTTP %s", status)
            return {}
        except Exception as exc:
            log.warning("GET /products дастнорас: %s", exc)
            return {}

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


def build_supplier(kind: str, url: str = "", key: str = "") -> Supplier:
    """`kind`: ``fireloot`` ё ``manual``."""
    if kind in ("fireloot", "http") and url and key:
        return FireLootSupplier(url, key)
    return ManualSupplier()
