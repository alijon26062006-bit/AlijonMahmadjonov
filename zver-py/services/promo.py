"""Промокоды: проверка и применение.

Правила ровно те же, что в PHP-версии: код должен существовать и быть
включён, не просрочен, не исчерпан по общему лимиту и по лимиту на
пользователя, сумма заказа не ниже минимальной. Скидка бывает
процентной (kind='pct') или фиксированной (kind='fix') и никогда не
превышает саму сумму заказа.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import db

CENT = Decimal("0.01")


@dataclass(slots=True)
class Result:
    ok: bool
    err: str = ""
    promo: dict | None = None
    off: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    min_sum: Decimal = Decimal("0.00")


def _round(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


async def check(code: str, uid: int, amount: Decimal) -> Result:
    code = (code or "").strip().upper()
    if not code:
        return Result(False, "EMPTY")

    p = await db.promo_by_code(code)
    if not p:
        return Result(False, "NOT_FOUND")
    if int(p.get("active") or 0) != 1:
        return Result(False, "OFF")

    until = int(p.get("until") or 0)
    if until and until < int(time.time()):
        return Result(False, "EXPIRED")

    max_uses = int(p.get("max_uses") or 0)
    if max_uses > 0 and int(p.get("used") or 0) >= max_uses:
        return Result(False, "LIMIT")

    min_sum = Decimal(p.get("min_sum") or 0)
    if min_sum > 0 and amount < min_sum:
        return Result(False, "MIN", min_sum=min_sum)

    per_user = int(p.get("per_user") or 0)
    if per_user > 0 and await db.promo_used_by(int(p["id"]), uid) >= per_user:
        return Result(False, "USED")

    val = Decimal(p.get("val") or 0)
    off = val if p.get("kind") == "fix" else _round(amount * val / Decimal(100))
    if off > amount:
        off = amount
    off = _round(off)
    return Result(True, promo=p, off=off, total=_round(amount - off))


async def apply(promo: dict, uid: int, order_id: int | None,
                off: Decimal) -> None:
    await db.promo_apply(int(promo["id"]), uid, order_id, off)


def error_key(err: str) -> str:
    """Код ошибки → ключ текста для показа пользователю."""
    return {
        "NOT_FOUND": "promo_not_found",
        "OFF":       "promo_off",
        "EXPIRED":   "promo_expired",
        "LIMIT":     "promo_limit",
        "USED":      "promo_used",
        "MIN":       "promo_min",
        "EMPTY":     "promo_empty",
    }.get(err, "promo_not_found")
