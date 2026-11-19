from decimal import Decimal

from app.money import sell_price


def test_sell_price_rounds_up_to_cent():
    assert sell_price("0.8866", 10) == Decimal("0.98")  # 0.97526 -> 0.98
    assert sell_price("1.0000", 10) == Decimal("1.10")
    assert sell_price("0.8866", 0) == Decimal("0.89")  # never below cost
    assert sell_price("29.7148", Decimal("12.5")) == Decimal("33.43")
