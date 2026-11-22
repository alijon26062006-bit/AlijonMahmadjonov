"""Витрина VPS: страны, тарифы, ОС и цены — всё из API Hetzner, ничего не зашито в коде.

Цена клиенту, $ в месяц = вверх до цента(
    (price_monthly.net тарифа в локации + price_monthly.net IPv4 этой локации)
    × курс валюты аккаунта к USD × (1 + наценка) )
В сомони — по курсу Sitora («Курс, сомони за 1 $» в админке), вверх до дирама.
"""
from __future__ import annotations

import json
import logging
from decimal import ROUND_CEILING, Decimal, InvalidOperation

import httpx

from .. import db, shop
from .hetzner import Hetzner

log = logging.getLogger(__name__)
CATALOG_TTL = 3600
DEFAULT_MARKUP = 20
DAY = 86400
COUNTRIES = {"DE": ("Германия", "Олмон"), "FI": ("Финляндия", "Финланд"), "US": ("США", "ИМА"),
             "SG": ("Сингапур", "Сингапур")}


def markup(conn) -> int:
    try:
        return max(0, min(int(db.get_setting(conn, "vps_markup", str(DEFAULT_MARKUP))), 300))
    except ValueError:
        return DEFAULT_MARKUP


def _dec(value) -> Decimal | None:
    try:
        d = Decimal(str(value).replace(",", "."))
        return d if d > 0 else None
    except (InvalidOperation, ValueError):
        return None


async def account_rate(conn, currency: str, transport=None) -> Decimal:
    """Сколько USD в единице валюты аккаунта Hetzner. EUR: курс админа, иначе раз в сутки с open.er-api.com."""
    currency = (currency or "EUR").upper()
    if currency == "USD":
        return Decimal(1)
    manual = _dec(db.get_setting(conn, f"vps_{currency.lower()}_usd"))
    if manual:
        return manual
    cached = json.loads(db.get_setting(conn, f"vps_{currency.lower()}_usd_auto", "{}") or "{}")
    import time
    if cached.get("at", 0) > time.time() - DAY and _dec(cached.get("value")):
        return _dec(cached["value"])
    try:
        async with httpx.AsyncClient(timeout=15, transport=transport) as c:
            value = _dec(((await c.get(f"https://open.er-api.com/v6/latest/{currency}")).json().get("rates") or {}).get("USD"))
    except Exception as exc:  # noqa: BLE001 — нет сети: прошлый курс
        log.info("Курс %s→USD не получен: %s", currency, exc)
        value = None
    if value:
        db.set_setting(conn, f"vps_{currency.lower()}_usd_auto", json.dumps({"value": str(value), "at": time.time()}))
        return value
    if _dec(cached.get("value")):
        return _dec(cached["value"])
    raise RuntimeError(f"Нет курса {currency}→USD: задайте его в админке (раздел VPS).")


def price_cents(type_net: Decimal, ipv4_net: Decimal, rate: Decimal, markup_percent: int) -> int:
    usd = (type_net + ipv4_net) * rate * (100 + markup_percent) / 100
    return int((usd * 100).to_integral_value(rounding=ROUND_CEILING))


def to_diram(cents: int, somoni_per_usd: Decimal) -> int:
    """Центы USD → дирамы по курсу Sitora, вверх до дирама."""
    return int((Decimal(cents) * somoni_per_usd).to_integral_value(rounding=ROUND_CEILING))


def _money(entry, field="price_monthly") -> Decimal | None:
    try:
        return Decimal(str(((entry or {}).get(field) or {}).get("net")))
    except Exception:  # noqa: BLE001
        return None


async def raw(h: Hetzner) -> dict:
    async def fetch():
        return {
            "locations": await h.list("/locations", "locations"),
            "server_types": await h.list("/server_types", "server_types"),
            "images": await h.list("/images", "images", {"type": "system", "status": "available"}),
            "pricing": (await h.get("/pricing")).get("pricing") or {},
        }
    return await h.cached("catalog", CATALOG_TTL, fetch)


def _available_here(st: dict, location: str) -> bool:
    for loc in st.get("locations") or []:
        if loc.get("name") == location:
            return loc.get("available", True) is not False and not loc.get("deprecation")
    return not st.get("locations") and any(p.get("location") == location for p in st.get("prices") or [])


async def build(conn, h: Hetzner, transport=None) -> dict:
    data = await raw(h)
    currency = (data["pricing"].get("currency") or "EUR").upper()
    rate = await account_rate(conn, currency, transport)
    somoni = shop.rate(conn)
    pct = markup(conn)
    ipv4: dict[str, tuple[Decimal, Decimal]] = {}
    for item in data["pricing"].get("primary_ips") or []:
        if item.get("type") == "ipv4":
            for p in item.get("prices") or []:
                if p.get("location") and _money(p) is not None:
                    ipv4[p["location"]] = (_money(p), _money(p, "price_hourly") or Decimal(0))

    locations = []
    for loc in data["locations"]:
        name = loc.get("name")
        plans = []
        for st in data["server_types"]:
            if st.get("deprecation") or st.get("deprecated") or not _available_here(st, name):
                continue
            price = next((p for p in st.get("prices") or [] if p.get("location") == name), None)
            type_net = _money(price)
            if type_net is None:
                continue
            ip_net, ip_hour = ipv4.get(name, (Decimal(0), Decimal(0)))
            cents = price_cents(type_net, ip_net, rate, pct)
            hourly = (_money(price, "price_hourly") or Decimal(0)) + ip_hour
            plans.append({
                "name": st["name"], "cores": st.get("cores"), "memory": st.get("memory"), "disk": st.get("disk"),
                "architecture": st.get("architecture", "x86"), "cpu_type": st.get("cpu_type", "shared"),
                "price_usd": cents, "price": to_diram(cents, somoni),
                "cost_monthly": int(((type_net + ip_net) * rate * 100).to_integral_value(rounding=ROUND_CEILING)),
                "cost_hourly_e6": int((hourly * rate * 1_000_000).to_integral_value(rounding=ROUND_CEILING)),
                "traffic_tb": round(((price or {}).get("included_traffic") or 0) / 1024 ** 4, 1),
            })
        if plans:
            plans.sort(key=lambda p: (p["price"], p["cores"]))
            ru, tj = COUNTRIES.get(loc.get("country", ""), (loc.get("country", ""), loc.get("country", "")))
            locations.append({"name": name, "city": loc.get("city", ""), "country": loc.get("country", ""),
                              "country_ru": ru, "country_tj": tj, "plans": plans})
    images = [{"name": i["name"], "title": i.get("description") or i["name"], "flavor": i.get("os_flavor", ""),
               "architecture": i.get("architecture", "x86")}
              for i in data["images"] if not i.get("deprecated") and i.get("status", "available") == "available"]
    images.sort(key=lambda i: (i["flavor"], i["name"]))
    return {"locations": locations, "images": images, "currency": currency, "rate": str(rate),
            "somoni_per_usd": str(somoni), "markup": pct}


async def find_offer(conn, h: Hetzner, location: str, server_type: str, image: str, transport=None):
    cat = await build(conn, h, transport)
    loc = next((l for l in cat["locations"] if l["name"] == location), None)
    plan = next((p for p in (loc or {}).get("plans", []) if p["name"] == server_type), None)
    if plan is None:
        raise ValueError("Этот тариф сейчас недоступен в выбранной локации.")
    img = next((i for i in cat["images"] if i["name"] == image and i["architecture"] == plan["architecture"]), None)
    if img is None:
        raise ValueError("Эта ОС недоступна для выбранного тарифа.")
    return plan, img
