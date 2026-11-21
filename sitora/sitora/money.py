"""Деньги — в дирамах (1 сомони = 100 дирам), целыми числами: без ошибок округления."""
from __future__ import annotations

from decimal import ROUND_CEILING, Decimal


def to_diram(somoni: str | float | Decimal) -> int:
    return int((Decimal(str(somoni).replace(",", ".").replace(" ", "")) * 100).to_integral_value(ROUND_CEILING))


def fmt(diram: int) -> str:
    """12345 → «123,45», 100000 → «1 000». Пробелы между разрядами, дробь только если есть."""
    sign = "-" if diram < 0 else ""
    whole, frac = divmod(abs(int(diram)), 100)
    s = f"{whole:,}".replace(",", " ")
    return sign + (s + (f",{frac:02d}".rstrip("0") if frac else ""))


def price(usd: Decimal, rate: Decimal, markup_pct: Decimal) -> int:
    """Цена клиенту в дирамах: закупка в долларах × курс × (1 + наценка). Округляем вверх до 10 дирам."""
    raw = Decimal(usd) * Decimal(rate) * (Decimal(1) + Decimal(markup_pct) / 100) * 100
    return int((raw / 10).to_integral_value(ROUND_CEILING)) * 10
