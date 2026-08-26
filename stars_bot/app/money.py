"""Деньги хранятся в дирамах (1 сомони = 100 дирам) целыми числами.

Float для денег не используем никогда: 0.1 + 0.2 != 0.3, а на балансе
пользователя такие копейки превращаются в расхождение с кассой.
"""
from __future__ import annotations

import re

from app import runtime
from app.config import settings

_AMOUNT_RE = re.compile(r"^\d{1,9}([.,]\d{1,2})?$")


def parse(raw: str) -> int | None:
    """'12.50' -> 1250 дирам. None, если строка не похожа на сумму."""
    text = raw.strip().replace(" ", "")
    if not _AMOUNT_RE.match(text):
        return None
    text = text.replace(",", ".")
    whole, _, frac = text.partition(".")
    return int(whole) * 100 + int(frac.ljust(2, "0")) if frac else int(whole) * 100


def fmt(diram: int) -> str:
    """1250 -> '12.50 с.'"""
    sign = "-" if diram < 0 else ""
    whole, frac = divmod(abs(diram), 100)
    return f"{sign}{whole:,}".replace(",", " ") + f".{frac:02d} {settings.currency}"


def stars_cost(quantity: int) -> int:
    """Стоимость quantity звёзд в дирамах по текущей цене."""
    return quantity * runtime.star_price()


def affordable_stars(balance: int) -> int:
    """Сколько звёзд можно купить на данный баланс."""
    price = runtime.star_price()
    return balance // price if price > 0 else 0
