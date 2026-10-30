"""P2P D-коинов: объявления по своей цене, сделка мгновенная за баланс, сайт — гарант, минуса нет."""

import pytest
from conftest import balance, csrf_of, web_login
from fastapi.testclient import TestClient
from test_dcoin import _buy, _user

from donatix import accounts, db, dcoin, p2p


@pytest.fixture
def market(conn, monkeypatch):
    monkeypatch.setattr(dcoin, "START_PRICE", 1.0)                      # цена «взрослая», без запаса
    monkeypatch.setattr(dcoin, "exchange_open", lambda *a, **k: True)
    seller, buyer = _user(conn, "seller"), _user(conn, "buyer")
    for _ in range(5):
        _buy(conn, seller, 100_000, cost=50_000)                         # $10 — 1000 D у продавца
    with db.tx(conn):
        accounts.post_ledger(conn, buyer, 500_000, "пополнение")         # у покупателя $50
    return seller, buyer


def _px(conn, pct):
    """Цена объявления в процентах от рыночной (как ввёл бы человек)."""
    return p2p.ref_price_m(conn) * pct // 100


def _money_total(conn):
    return conn.execute("SELECT SUM(balance_micro) FROM users").fetchone()[0]


def _coins_total(conn):
    held = conn.execute("SELECT SUM(dcoin) FROM users").fetchone()[0]
    in_ads = conn.execute("SELECT COALESCE(SUM(remaining), 0) FROM p2p_ads WHERE status = 'open' AND side = 'sell'"
                          ).fetchone()[0]
    in_orders = conn.execute("SELECT COALESCE(SUM(units), 0) FROM p2p_orders WHERE status = 'pending'").fetchone()[0]
    return held + in_ads + in_orders


def _money_all(conn):   # деньги людей + в резервах объявлений «покупаю» + в открытых ордерах
    return (_money_total(conn)
            + conn.execute("SELECT COALESCE(SUM(locked_micro), 0) FROM p2p_ads WHERE status = 'open'").fetchone()[0]
            + conn.execute("SELECT COALESCE(SUM(total_micro), 0) FROM p2p_orders WHERE status = 'pending'").fetchone()[0])


def test_order_freezes_both_sides_then_owner_confirms(conn, market):
    seller, buyer = market
    money0, coins0, pool0 = _money_all(conn), _coins_total(conn), dcoin.state(conn)["pool"]
    have = dcoin.balance(conn, seller)
    ad = p2p.create_ad(conn, seller, "sell", _px(conn, 110), 300 * dcoin.UNIT)       # продаю 300 D на 10% дороже копилки
    assert dcoin.balance(conn, seller) == have - 300 * dcoin.UNIT          # монеты заморожены в объявлении
    assert p2p.book(conn, "sell")[0]["who"] == "sel***"
    with pytest.raises(p2p.P2PError, match="ваше"):
        p2p.open_order(conn, seller, ad, 10 * dcoin.UNIT)
    b0 = balance(conn, buyer)
    oid = p2p.open_order(conn, buyer, ad, 100 * dcoin.UNIT)
    o = conn.execute("SELECT * FROM p2p_orders WHERE id = ?", (oid,)).fetchone()
    assert o["status"] == "pending" and balance(conn, buyer) == b0 - o["total_micro"]   # деньги заморожены
    assert p2p.book(conn, "sell")[0]["remaining"] == 200 * dcoin.UNIT                   # 100 D больше никто не возьмёт
    assert dcoin.balance(conn, buyer) == 0                                              # монет ещё нет
    assert _money_all(conn) == money0 and _coins_total(conn) == coins0
    with pytest.raises(p2p.P2PError, match="владелец"):
        p2p.confirm(conn, buyer, oid)                                     # подтверждает только продавец
    s0 = balance(conn, seller)
    p2p.confirm(conn, seller, oid)
    assert dcoin.balance(conn, buyer) == 100 * dcoin.UNIT and balance(conn, seller) == s0 + o["total_micro"]
    assert _money_all(conn) == money0 and _coins_total(conn) == coins0 and dcoin.state(conn)["pool"] == pool0
    with pytest.raises(p2p.P2PError, match="завершён"):
        p2p.cancel_order(conn, buyer, oid)


def test_order_cancel_and_timeout_unfreeze(conn, market):
    from datetime import datetime, timedelta, timezone
    seller, buyer = market
    money0, coins0 = _money_all(conn), _coins_total(conn)
    ad = p2p.create_ad(conn, buyer, "buy", _px(conn, 95), 200 * dcoin.UNIT)           # покупаю: деньги в резерве
    c0 = dcoin.balance(conn, seller)
    oid = p2p.open_order(conn, seller, ad, 100 * dcoin.UNIT)                # продаю — мои монеты заморожены
    assert dcoin.balance(conn, seller) == c0 - 100 * dcoin.UNIT
    p2p.cancel_order(conn, buyer, oid)                                      # владелец отклонил — всё вернулось
    assert dcoin.balance(conn, seller) == c0 and p2p.book(conn, "buy")[0]["remaining"] == 200 * dcoin.UNIT
    oid2 = p2p.open_order(conn, seller, ad, 50 * dcoin.UNIT)
    later = datetime.now(timezone.utc) + timedelta(minutes=p2p.ORDER_MINUTES + 1)
    conn.execute("UPDATE p2p_orders SET expires_at = ? WHERE id = ?",
                 ((later - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), oid2))
    assert [o["id"] for o in p2p.expire(conn)] == [oid2]                    # 15 минут вышли — отменён сам
    assert conn.execute("SELECT status FROM p2p_orders WHERE id = ?", (oid2,)).fetchone()[0] == "expired"
    assert dcoin.balance(conn, seller) == c0
    assert _money_all(conn) == money0 and _coins_total(conn) == coins0


def test_closed_ad_with_open_order_returns_to_owner(conn, market):
    seller, buyer = market
    have = dcoin.balance(conn, seller)
    ad = p2p.create_ad(conn, seller, "sell", _px(conn, 100), 100 * dcoin.UNIT)
    oid = p2p.open_order(conn, buyer, ad, 40 * dcoin.UNIT)
    p2p.cancel(conn, seller, ad)                                            # закрыл объявление: 60 D вернулись
    assert dcoin.balance(conn, seller) == have - 40 * dcoin.UNIT
    p2p.cancel_order(conn, buyer, oid)                                      # ордер отменён — 40 D тоже ему
    assert dcoin.balance(conn, seller) == have


def test_buy_ad_fully_filled_returns_rounding(conn, market):
    seller, buyer = market
    bal0 = balance(conn, buyer)
    ad = p2p.create_ad(conn, buyer, "buy", _px(conn, 95), 200 * dcoin.UNIT)
    oid = p2p.open_order(conn, seller, ad, 200 * dcoin.UNIT)
    total = conn.execute("SELECT total_micro FROM p2p_orders WHERE id = ?", (oid,)).fetchone()[0]
    p2p.confirm(conn, buyer, oid)
    assert dcoin.balance(conn, buyer) == 200 * dcoin.UNIT and balance(conn, buyer) == bal0 - total
    assert conn.execute("SELECT status, locked_micro FROM p2p_ads WHERE id = ?", (ad,)).fetchone()[:] == ("done", 0)


def test_guards(conn, market):
    seller, buyer = market
    with pytest.raises(p2p.P2PError, match="от 80%"):
        p2p.create_ad(conn, seller, "sell", _px(conn, 300), 10 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError, match="свободных"):
        p2p.create_ad(conn, seller, "sell", _px(conn, 100), 10**9)
    with pytest.raises(p2p.P2PError, match="Не хватает денег"):
        p2p.create_ad(conn, buyer, "buy", _px(conn, 100), 10**9)
    assert conn.execute("SELECT COUNT(*) FROM p2p_ads").fetchone()[0] == 0
    ad = p2p.create_ad(conn, seller, "sell", _px(conn, 100), 500 * dcoin.UNIT, min_units=20 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError, match="Минимум"):
        p2p.open_order(conn, buyer, ad, 5 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError):
        p2p.cancel(conn, buyer, ad)
    for _ in range(p2p.MAX_PENDING):
        p2p.open_order(conn, buyer, ad, 30 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError, match="открытых ордера"):
        p2p.open_order(conn, buyer, ad, 30 * dcoin.UNIT)


def test_p2p_sale_does_not_block_daily_exchange(conn, market):
    seller, buyer = market
    p2p.create_ad(conn, seller, "sell", _px(conn, 100), 10 * dcoin.UNIT)
    assert dcoin.exchange(conn, seller, dcoin.balance(conn, seller)) > 0


def test_pages_instant_deal_number_and_complaint(app, conn, market):
    seller, buyer = market
    db.set_setting(conn, "pay.tjs_rate", "10")
    s = TestClient(app)
    token = web_login(s, "seller@example.com", "password123")
    s.cookies.set("dx_cur", "TJS")
    price_tjs = dcoin.price(conn) * 10 * 1.05                               # человек сам вводит цену в сомони
    r = s.post("/panel/p2p/ad", data={"csrf": token, "side": "sell", "price": f"{price_tjs:.10f}", "amount": "100"})
    assert "размещено" in r.text
    ad = conn.execute("SELECT id, pct FROM p2p_ads").fetchone()
    assert ad["pct"] == 105
    b = TestClient(app)
    web_login(b, "buyer@example.com", "password123")
    page = b.get("/panel/p2p").text
    assert "sel***" in page and "Мгновенно" in page and "dc-canvas" in page and "покупают" not in page
    s_bal = balance(conn, seller)
    r = b.post(f"/panel/p2p/{ad['id']}/take", data={"csrf": csrf_of(page), "amount": "40"})
    assert "Куплено 40.00 D" in r.text and "P2P-000001" in r.text                 # сразу, без подтверждения
    assert dcoin.balance(conn, buyer) == 40 * dcoin.UNIT and balance(conn, seller) > s_bal
    o = conn.execute("SELECT status FROM p2p_orders").fetchone()
    assert o["status"] == "done"
    assert "/panel/support/new?topic=p2p&order=P2P-000001" in r.text       # жалоба по номеру ордера
    form = b.get("/panel/support/new?topic=p2p&order=P2P-000001").text
    assert 'value="P2P-000001"' in form
    ads = s.get("/panel/p2p?tab=ads").text
    assert "Самая низкая у продавцов" in ads and "Макс" in ads


def test_book_sort_amount_filter_and_tabs(app, conn, market):
    seller, buyer = market
    other = _user(conn, "third")
    for _ in range(3):
        _buy(conn, other, 100_000, cost=50_000)
    cheap = p2p.create_ad(conn, other, "sell", _px(conn, 90), 100 * dcoin.UNIT)
    pricey = p2p.create_ad(conn, seller, "sell", _px(conn, 120), 300 * dcoin.UNIT)
    p2p.confirm(conn, seller, p2p.open_order(conn, buyer, pricey, 10 * dcoin.UNIT))   # у продавца есть сделка
    assert [a["id"] for a in p2p.book(conn, "sell")] == [cheap, pricey]   # по цене: сначала дешёвые
    by_deals = p2p.book(conn, "sell", sort="deals")
    assert by_deals[0]["id"] == pricey and by_deals[0].get("top")          # «Рекомендации» — больше сделок
    big = p2p.book(conn, "sell")[1]["max_usd"]
    assert [a["id"] for a in p2p.book(conn, "sell", amount_usd=big)] == [pricey]   # фильтр «Сумма»
    b = TestClient(app)
    web_login(b, "buyer@example.com", "password123")
    for tab, text in (("orders", "Покупка 10.00 D"), ("profile", "В объявлениях, D"), ("ads", "Разместить объявление")):
        assert text in b.get(f"/panel/p2p?tab={tab}").text


def test_owner_sets_own_price_and_best_price_hint(conn, market):
    seller, buyer = market
    third = _user(conn, "third")
    for _ in range(3):
        _buy(conn, third, 100_000, cost=50_000)
    ad = p2p.create_ad(conn, seller, "sell", _px(conn, 105), 200 * dcoin.UNIT)
    p2p.create_ad(conn, third, "sell", _px(conn, 97), 100 * dcoin.UNIT)
    p2p.create_ad(conn, buyer, "buy", _px(conn, 92), 100 * dcoin.UNIT)
    best = p2p.best_prices(conn, seller)
    assert abs(best["min_sell"] - _px(conn, 97) / 10_000 / p2p.PRICE_SCALE) < 1e-12   # самая низкая у других
    assert best["max_buy"] is not None
    p2p.set_price(conn, seller, ad, _px(conn, 98))                            # владелец сам поменял цену
    assert conn.execute("SELECT pct FROM p2p_ads WHERE id = ?", (ad,)).fetchone()[0] == 98
    with pytest.raises(p2p.P2PError):
        p2p.set_price(conn, buyer, ad, _px(conn, 90))                         # чужое не поменять
    with pytest.raises(p2p.P2PError, match="рыночной"):
        p2p.set_price(conn, seller, ad, _px(conn, 10))                        # слишком дёшево — нельзя
    res = p2p.execute(conn, buyer, ad, 10 * dcoin.UNIT)
    assert res["number"].startswith("P2P-") and dcoin.balance(conn, buyer) == 10 * dcoin.UNIT
