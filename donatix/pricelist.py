"""Прайс-лист картинкой: Free Fire СНГ, Free Fire Индонезия и PUBG Mobile с ценами в сомони.

Цены — настоящие, из каталога: закупка у поставщика + наценка сайта (как видит
новый клиент) → по курсу сомони из «Реквизитов». Картинку собирает браузер
админа из этой страницы — поэтому цифры на ней всегда совпадают с сайтом, чего
не добиться от генератора картинок.
"""

from __future__ import annotations

import re
import sqlite3
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

from . import popular
from .config import Config
from .money import apply_markup, to_decimal

SECTIONS = (("ff_cis", "Free Fire", "СНГ"), ("ff_id", "Free Fire", "Индонезия"), ("pubg", "PUBG Mobile", "UC"))

_LEVEL = re.compile(r"прокач|level|уров|evo|эволюц|upgrade", re.I)
_PASS = re.compile(r"ваучер|voucher|member|пропуск|pass|недел|месяч|week|month|booyah|подпис|card|карт", re.I)
_NUM = re.compile(r"(\d[\d\s.,]*)")


def _amount(name: str) -> float:
    m = _NUM.search(name)
    if not m:
        return 0
    try:
        return float(m.group(1).replace(" ", "").replace(",", ""))
    except ValueError:
        return 0


def pack_order(name: str) -> tuple[int, float, str]:
    """Сначала алмазы/UC по количеству, потом ваучеры и пропуска, в конце прокачки."""
    group = 2 if _LEVEL.search(name) else 1 if _PASS.search(name) else 0
    amount = _amount(name)
    if group == 1 and not amount:  # ваучеры: неделя раньше месяца
        amount = 7 if re.search(r"недел|week", name, re.I) else 30 if re.search(r"месяц|month", name, re.I) else 0
    return group, amount, name


def _categories(conn: sqlite3.Connection) -> dict[str, tuple[str, str | None, str | None]]:
    """key → (category_id, регион или None, обложка) — те же игры, что в «Популярном»."""
    return {p["key"]: (p["category_id"], p["region"], p["image_url"])
            for p in popular._pinned(conn) if p["key"] in ("ff_cis", "ff_id", "pubg")}


_SHORT = ((re.compile(r"\s*(алмаз(ов|а)?|diamonds?)\b", re.I), " 💎"),
          (re.compile(r"ваучер на неделю|weekly (membership|voucher)", re.I), "Ваучер · неделя"),
          (re.compile(r"ваучер на месяц|monthly (membership|voucher)", re.I), "Ваучер · месяц"),
          (re.compile(r"\s*\((.*?)\)"), ""))


def short_name(name: str) -> str:
    """Короче для картинки: «100 алмазов» → «100 💎», скобки с пояснениями убираем."""
    for rx, repl in _SHORT:
        name = rx.sub(repl, name)
    return name.strip()


def tjs_price(base: Any, markup: Decimal, rate: Decimal) -> Decimal:
    """Цена продажи в сомони: так же, как сайт списывает (4 знака вверх) и показывает (2 знака)."""
    usd = apply_markup(to_decimal(base), markup).quantize(Decimal("0.0001"), rounding=ROUND_CEILING)
    return (usd * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    from .payments import settings as pay_settings
    rate = Decimal(str(pay_settings(conn, config)["tjs_rate"]))
    markup = config.kind_markups.get("topup", config.markups["bronze"])
    cats = _categories(conn)
    sections = []
    for key, game, sub in SECTIONS:
        if key not in cats:
            continue
        category_id, region, image = cats[key]
        sql = "SELECT name, base_price FROM products WHERE active = 1 AND hidden = 0 AND kind = 'topup' " \
              "AND category_id = ?"
        args: list[Any] = [category_id]
        if region:
            sql += " AND region = ?"
            args.append(region)
        rows = conn.execute(sql, args).fetchall()
        items = sorted(({"name": r["name"], "tjs": tjs_price(r["base_price"], markup, rate)} for r in rows),
                        key=lambda i: pack_order(i["name"]))
        for i in items:
            i["group"] = pack_order(i["name"])[0]
            i["price"] = f"{i['tjs']:.2f}"
            i["short"] = short_name(i["name"])
        if items:
            sections.append({"key": key, "game": game, "sub": sub, "image": image, "packs": items})
    return {"sections": sections, "rate": rate, "markup": markup}
