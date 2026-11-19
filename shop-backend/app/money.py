"""Money is always Decimal. Supplier prices are USD strings with 4 decimals."""
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
Q4 = Decimal("0.0001")


def d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q4(value) -> Decimal:
    return d(value).quantize(Q4, rounding=ROUND_HALF_UP)


def sell_price(cost, markup_percent) -> Decimal:
    """Customer price = cost + markup, rounded UP to a whole cent (never below cost)."""
    cost = d(cost)
    price = cost * (Decimal(1) + d(markup_percent) / Decimal(100))
    price = price.quantize(CENT, rounding=ROUND_CEILING)
    return max(price, cost.quantize(CENT, rounding=ROUND_CEILING))
