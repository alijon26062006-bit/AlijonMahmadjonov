"""Минимум пополнения — 10 сомони для любого способа (и при оплате покупки тоже)."""

from decimal import Decimal

import pytest

from donatix import accounts, db, payments, quickbuy, sitecfg


def test_min_10_somoni_any_method(app, config, conn):
    db.set_setting(conn, "migr.min_tjs_10", "")   # как на сервере после обновления: миграция ставит 10
    conn.execute("DELETE FROM settings WHERE key = 'migr.min_tjs_10'")
    sitecfg.load(conn, config)
    assert payments.settings(conn, config)["min_tjs"] == 10
    payments.save_methods(conn, [
        {"code": "dc", "title": "DC", "currency": "TJS", "details": "Карта 4444 5555 6666 7777", "enabled": True},
        {"code": "usdt", "title": "USDT", "currency": "USDT:TRC20", "details": "TXyz", "enabled": True}])
    uid = accounts.create_user(conn, email="m@example.com", login="minuser", password="password123",
                               status="active")
    user = accounts.get_user(conn, uid)
    for method in ("dc", "usdt"):
        with pytest.raises(payments.PaymentError, match="10 сомони"):
            payments.create(conn, config, user, method, "", amount_tjs="9.99")
        with pytest.raises(payments.PaymentError, match="10 сомони"):
            payments.create(conn, config, user, method, "0.5")   # $0.5 ≈ 5 сомони
    pid = payments.create(conn, config, user, "dc", "", amount_tjs="10")
    assert conn.execute("SELECT pay_amount FROM payments WHERE id = ?", (pid,)).fetchone()[0] == "10.00"
    # оплата покупки: не хватает 3 сомони — переводят 10, остаток на балансе
    rate = payments.settings(conn, config)["tjs_rate"]
    need = int(Decimal(3) / rate * 10000)
    assert quickbuy.to_pay_tjs(conn, config, need, 0) == 10
    assert quickbuy.to_pay_tjs(conn, config, 0, 0) == 0
