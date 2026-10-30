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


def _money_total(conn):
    return conn.execute("SELECT SUM(balance_micro) FROM users").fetchone()[0]


def _coins_total(conn):
    held = conn.execute("SELECT SUM(dcoin) FROM users").fetchone()[0]
    in_ads = conn.execute("SELECT COALESCE(SUM(remaining), 0) FROM p2p_ads WHERE status = 'open' AND side = 'sell'"
                          ).fetchone()[0]
    return held + in_ads


def test_sell_ad_then_buy_is_instant_and_zero_sum(conn, market):
    seller, buyer = market
    money0, coins0, pool0 = _money_total(conn), _coins_total(conn), dcoin.state(conn)["pool"]
    have = dcoin.balance(conn, seller)
    ad = p2p.create_ad(conn, seller, "sell", 110, 300 * dcoin.UNIT)       # продаю 300 D на 10% дороже копилки
    assert dcoin.balance(conn, seller) == have - 300 * dcoin.UNIT          # монеты ушли в объявление
    book = p2p.book(conn, "sell")
    assert book[0]["id"] == ad and book[0]["pct"] == 110 and book[0]["who"] == "sel***"
    with pytest.raises(p2p.P2PError, match="ваше"):
        p2p.take(conn, seller, ad, 10 * dcoin.UNIT)
    seller_bal, buyer_bal = balance(conn, seller), balance(conn, buyer)
    res = p2p.take(conn, buyer, ad, 100 * dcoin.UNIT)
    assert res["total"] > 0
    assert balance(conn, buyer) == buyer_bal - res["total"] and balance(conn, seller) == seller_bal + res["total"]
    assert dcoin.balance(conn, buyer) == 100 * dcoin.UNIT
    assert _money_total(conn) == money0 and _coins_total(conn) == coins0  # деньги и монеты только перешли
    assert dcoin.state(conn)["pool"] == pool0                              # копилку P2P не трогает
    p2p.cancel(conn, seller, ad)                                            # остаток 200 D вернулся
    assert dcoin.balance(conn, seller) == have - 100 * dcoin.UNIT
    with pytest.raises(p2p.P2PError, match="закрыто"):
        p2p.take(conn, buyer, ad, 10 * dcoin.UNIT)


def test_buy_ad_reserves_money_and_seller_gets_it(conn, market):
    seller, buyer = market
    money0 = _money_total(conn)
    bal0 = balance(conn, buyer)
    ad = p2p.create_ad(conn, buyer, "buy", 95, 200 * dcoin.UNIT)
    locked = bal0 - balance(conn, buyer)
    assert locked > 0                                                       # деньги в резерве
    s_bal = balance(conn, seller)
    res = p2p.take(conn, seller, ad, 200 * dcoin.UNIT)                       # продал всё
    assert balance(conn, seller) == s_bal + res["total"]
    assert dcoin.balance(conn, buyer) == 200 * dcoin.UNIT
    assert balance(conn, buyer) == bal0 - res["total"]                       # копейки резерва вернулись
    assert _money_total(conn) == money0
    assert conn.execute("SELECT status, locked_micro FROM p2p_ads WHERE id = ?", (ad,)).fetchone()[:] == ("done", 0)


def test_guards(conn, market):
    seller, buyer = market
    with pytest.raises(p2p.P2PError, match="от 80%"):
        p2p.create_ad(conn, seller, "sell", 300, 10 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError, match="свободных"):
        p2p.create_ad(conn, seller, "sell", 100, 10**9)
    with pytest.raises(p2p.P2PError, match="Не хватает денег"):
        p2p.create_ad(conn, buyer, "buy", 100, 10**9)
    assert conn.execute("SELECT COUNT(*) FROM p2p_ads").fetchone()[0] == 0    # неудачные — не сохранились
    ad = p2p.create_ad(conn, seller, "sell", 100, 50 * dcoin.UNIT, min_units=20 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError, match="Минимум"):
        p2p.take(conn, buyer, ad, 5 * dcoin.UNIT)
    with pytest.raises(p2p.P2PError):
        p2p.cancel(conn, buyer, ad)                                          # чужое не закрыть


def test_p2p_sale_does_not_block_daily_exchange(conn, market, monkeypatch):
    seller, buyer = market
    p2p.create_ad(conn, seller, "sell", 100, 10 * dcoin.UNIT)                # P2P-списание монет
    assert dcoin.exchange(conn, seller, dcoin.balance(conn, seller)) > 0      # обмен в копилку всё равно можно


def test_page_create_and_take(app, conn, market):
    seller, buyer = market
    s = TestClient(app)
    token = web_login(s, "seller@example.com", "password123")
    r = s.post("/panel/p2p/ad", data={"csrf": token, "side": "sell", "pct": "105", "amount": "100"})
    assert "размещено" in r.text and "Мои объявления" in r.text
    b = TestClient(app)
    token_b = web_login(b, "buyer@example.com", "password123")
    page = b.get("/panel/p2p").text
    assert "sel***" in page and "Мгновенно" in page and "Покупка" in page
    ad = conn.execute("SELECT id FROM p2p_ads").fetchone()[0]
    r = b.post(f"/panel/p2p/{ad}/take", data={"csrf": csrf_of(page), "amount": "40"})
    assert "Куплено 40.00 D" in r.text
    assert dcoin.balance(conn, buyer) == 40 * dcoin.UNIT
    assert token_b


def test_book_sort_amount_filter_and_tabs(app, conn, market):
    seller, buyer = market
    other = _user(conn, "third")
    for _ in range(3):
        _buy(conn, other, 100_000, cost=50_000)
    cheap = p2p.create_ad(conn, other, "sell", 90, 100 * dcoin.UNIT)
    pricey = p2p.create_ad(conn, seller, "sell", 120, 300 * dcoin.UNIT)
    p2p.take(conn, buyer, pricey, 10 * dcoin.UNIT)                      # у продавца есть сделка
    assert [a["id"] for a in p2p.book(conn, "sell")] == [cheap, pricey]   # по цене: сначала дешёвые
    by_deals = p2p.book(conn, "sell", sort="deals")
    assert by_deals[0]["id"] == pricey and by_deals[0].get("top")          # «Рекомендации» — больше сделок
    big = p2p.book(conn, "sell")[1]["max_usd"]
    assert [a["id"] for a in p2p.book(conn, "sell", amount_usd=big)] == [pricey]   # фильтр «Сумма»
    b = TestClient(app)
    web_login(b, "buyer@example.com", "password123")
    for tab, text in (("orders", "Покупка D-коина"), ("profile", "ордеров (100%)"), ("ads", "Разместить объявление")):
        assert text in b.get(f"/panel/p2p?tab={tab}").text
