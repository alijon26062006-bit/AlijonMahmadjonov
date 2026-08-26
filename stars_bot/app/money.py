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


def parse4(raw: str) -> int | None:
    """'0.1629' -> 1629 (десятитысячные сомони). None, если не число."""
    text = raw.strip().replace(" ", "").replace(",", ".")
    if not re.match(r"^\d{1,7}(\.\d{1,4})?$", text):
        return None
    whole, _, frac = text.partition(".")
    return int(whole) * 10_000 + int(frac.ljust(4, "0")) if frac else int(whole) * 10_000


def fmt4(e4: int) -> str:
    """Цена за штуку с четырьмя знаками: 1629 -> '0.1629 с.'

    Дирама для цены одной звезды мало: он равен ~7% её стоимости, и
    наценки 10% и 15% округлялись бы в одно и то же число.
    """
    whole, frac = divmod(abs(e4), 10_000)
    sign = "-" if e4 < 0 else ""
    return f"{sign}{whole}.{frac:04d} {settings.currency}"


def stars_cost(quantity: int) -> int:
    """Стоимость quantity звёзд в дирамах.

    Цена хранится в десятитысячных сомони, поэтому округляем один раз —
    на итоговой сумме, а не на каждой звезде.
    """
    total_e4 = quantity * runtime.star_price_e4()
    return (total_e4 + 50) // 100          # e4 -> дирамы, с округлением


def affordable_stars(balance: int) -> int:
    """Сколько звёзд можно купить на данный баланс."""
    price_e4 = runtime.star_price_e4()
    return balance * 100 // price_e4 if price_e4 > 0 else 0


def discount_of(price: int, percent: int) -> int:
    """Размер скидки в дирамах. Округляем к ближайшему дираму."""
    if percent <= 0 or price <= 0:
        return 0
    return min((price * percent + 50) // 100, price)
