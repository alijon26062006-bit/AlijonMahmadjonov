"""Donatix: «Боты для гильдии» — группа ботов набирает клану Free Fire очки
славы (Glory). Из Donatix берём только эту услугу.

API (https://donatix.tj/api/v1, заголовок X-API-Key: dx_live_…):
  GET  /glory/regions            регионы и цена (price_usd — наша цена у Donatix)
  POST /glory/orders             {"region": id, "clan_id": "…"} — запуск, списание
                                 с нашего баланса у Donatix; не запустилось —
                                 Donatix сам возвращает деньги и отвечает ошибкой
  GET  /glory/orders             последние 50 запусков
  GET  /glory/orders/{id}        статус, очки клана, набрано, клан
  POST /glory/orders/{id}/stop   остановить (после запуска денег назад нет)
  GET  /balance                  наш баланс у Donatix

Ответы: {"ok": true, …} или {"ok": false, "error": "…", "code": "…"}.
Без User-Agent Cloudflare у Donatix запросы режет — ставим всегда.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation

import aiohttp

from app import runtime
from app.config import settings

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=25, connect=8)
#: Регионы с ценами меняются редко — не спрашиваем на каждое нажатие.
REGIONS_TTL = 5 * 60
OPEN = ("starting", "running")


class GloryError(Exception):
    """Donatix ответил отказом: запуска нет, деньги у Donatix вернулись."""

    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


class GloryUnknown(Exception):
    """Ответа нет: запустилось или нет — неизвестно."""


def key() -> str:
    return (runtime.get("donatix_key") or settings.donatix_key or "").strip()


def ready() -> bool:
    """Ключ есть и продажа включена в панели."""
    return bool(key()) and runtime.get("glory_on", "1") != "0"


def margin() -> int:
    return max(runtime.get_int("glory_margin") or 25, 0)


async def _call(method: str, path: str, body: dict | None = None) -> dict:
    url = (runtime.get("donatix_url") or settings.donatix_url).rstrip("/") + path
    headers = {"X-API-Key": key(), "User-Agent": "StarsBot/1.0",
               "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.request(method, url, json=body, headers=headers) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001 — HTML от Cloudflare и т.п.
                    data = {"ok": False, "error": (await resp.text())[:200]}
                status = resp.status
    except (TimeoutError, aiohttp.ClientError) as exc:
        raise GloryUnknown(f"нет связи с Donatix: {exc}") from exc
    if not isinstance(data, dict):
        data = {"ok": False, "error": str(data)[:200]}
    if status >= 500:
        raise GloryUnknown(f"Donatix {status}: {data.get('error') or ''}")
    if status >= 400 or data.get("ok") is False:
        raise GloryError(str(data.get("error") or f"ошибка {status}"),
                         str(data.get("code") or status))
    return data


_regions: tuple[float, list[dict]] = (0.0, [])


def forget() -> None:
    global _regions
    _regions = (0.0, [])


def price_of(price_usd) -> int:
    """Цена клиенту в дирамах: цена Donatix по нашему курсу + наценка."""
    from app.services.games import offer_price

    try:
        usd = Decimal(str(price_usd))
    except (InvalidOperation, ValueError):
        return 0
    return offer_price(usd, margin())


def cost_of(price_usd) -> int:
    from app.services.games import offer_cost

    try:
        return offer_cost(Decimal(str(price_usd)))
    except (InvalidOperation, ValueError):
        return 0


async def regions(fresh: bool = False) -> list[dict]:
    """[{id, name, premium, price_usd, price}] — price наша, в дирамах."""
    global _regions
    if not fresh and _regions[1] and time.monotonic() - _regions[0] < REGIONS_TTL:
        return _regions[1]
    data = await _call("GET", "/glory/regions")
    items = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        price = price_of(raw.get("price_usd"))
        if price <= 0:
            continue
        items.append({"id": str(raw["id"])[:20], "name": str(raw.get("name") or raw["id"])[:40],
                      "premium": bool(raw.get("premium")),
                      "price_usd": str(raw.get("price_usd")), "price": price})
    _regions = (time.monotonic(), items)
    return items


async def launch(region: str, clan_id: str) -> dict:
    """Запустить группу. Возвращает заказ Donatix.

    GloryError — отказ (Donatix деньги вернул). GloryUnknown — ответа нет:
    тогда ищем запуск для этого клана в списке, прежде чем сдаваться, —
    повторять POST нельзя, деньги спишутся дважды.
    """
    try:
        data = await _call("POST", "/glory/orders", {"region": region, "clan_id": clan_id})
        order = data.get("order")
        if isinstance(order, dict) and order.get("id"):
            return order
        raise GloryUnknown(f"Donatix не вернул заказ: {str(data)[:200]}")
    except GloryUnknown:
        found = await find_open(clan_id)
        if found is not None:
            return found
        raise


async def find_open(clan_id: str) -> dict | None:
    try:
        data = await _call("GET", "/glory/orders")
    except (GloryError, GloryUnknown) as exc:
        log.info("Donatix: список запусков не получен — %s", exc)
        return None
    for item in data.get("items") or []:
        if (isinstance(item, dict) and str(item.get("clan_id")) == clan_id
                and str(item.get("status")) in OPEN):
            return item
    return None


async def status(ext_id: str) -> dict:
    data = await _call("GET", f"/glory/orders/{ext_id}")
    return data.get("order") or {}


async def stop(ext_id: str) -> dict:
    data = await _call("POST", f"/glory/orders/{ext_id}/stop")
    return data.get("order") or {}


async def balance() -> str:
    data = await _call("GET", "/balance")
    return f"{data.get('balance', '?')} {data.get('currency') or 'USD'}"


def clean_clan(text: str) -> str | None:
    """ID клана: только цифры, 5–15 знаков. None — не похоже."""
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    return digits if 5 <= len(digits) <= 15 else None
