from datetime import datetime, timedelta, timezone
from itertools import pairwise

from conftest import balance, web_login
from fastapi.testclient import TestClient

from donatix import accounts, db, dcoin, finance, orders


def _buy(conn, uid, total, cost=None):
    """Заказ в обработке → выполнен: так же, как это делает сайт."""
    n = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO orders (public_id, user_id, product_id, kind, product_name, quantity, unit_price, total_micro, "
        "cost_micro, status, supplier_idem_key, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"dx-{n}", uid, "p", "topup", "x", 1, "1", total, cost if cost is not None else int(total * 0.92),
         "processing", f"k{n}", ts, ts))
    assert orders.complete(conn, cur.lastrowid, {})
    return cur.lastrowid


def _user(conn, login="coiner"):
    return accounts.create_user(conn, email=f"{login}@example.com", login=login, password="password123",
                                status="active")


def test_price_starts_at_zero_and_coins_come_from_purchases(conn):
    uid = _user(conn)
    assert dcoin.price(conn) == 0.0
    oid = _buy(conn, uid, 10_000)                                  # $1, прибыль 8 центов
    assert dcoin.balance(conn, uid) == 100 * dcoin.UNIT             # 100 D за $1
    s = dcoin.state(conn)
    assert s["pool"] == 80                                          # 10% прибыли = 0.8 цента
    assert abs(dcoin.price(conn) - 0.00008) < 1e-12
    orders.complete(conn, oid, {})                                  # повторно — ничего
    assert dcoin.balance(conn, uid) == 100 * dcoin.UNIT
    conn.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (oid,))
    assert dcoin.award(conn, oid) == 0                              # за заказ — один раз


def test_bigger_order_moves_up_smaller_moves_down(conn):
    uid = _user(conn)
    _buy(conn, uid, 10_000)
    p1 = dcoin.price(conn)
    _buy(conn, uid, 5_000)                                          # мельче обычного
    p2 = dcoin.price(conn)
    _buy(conn, uid, 30_000)                                         # крупнее обычного
    p3 = dcoin.price(conn)
    assert p2 < p1 < p3


def test_never_more_than_pool_and_owner_keeps_most(conn):
    uid = _user(conn)
    for total in (10_000, 3_000, 90_000, 1_000, 50_000):
        _buy(conn, uid, total)
    profit = conn.execute("SELECT SUM(total_micro - cost_micro) FROM orders").fetchone()[0]
    s = dcoin.state(conn)
    assert s["pool"] <= profit * 20 // 100                          # максимум 20% прибыли, остальное — наше
    everything = dcoin.quote(conn, s["supply"])
    assert everything <= s["pool"]                                  # все монеты сразу — не больше копилки


def test_zero_profit_order_gives_coins_but_not_money(conn):
    uid = _user(conn)
    _buy(conn, uid, 10_000)
    pool = dcoin.state(conn)["pool"]
    _buy(conn, uid, 10_000, cost=10_000)
    assert dcoin.state(conn)["pool"] == pool and dcoin.price(conn) < 0.00008


def test_exchange_opens_later_and_keeps_fee_in_pool(conn):
    uid = _user(conn)
    for _ in range(20):
        _buy(conn, uid, 1_000_000, cost=500_000)                    # $100 с прибылью $50
    units = dcoin.balance(conn, uid)
    try:
        dcoin.exchange(conn, uid, units)
        raise AssertionError("обмен должен быть закрыт первый месяц")
    except dcoin.ExchangeError as exc:
        assert "откроется" in str(exc)
    later = datetime.now(timezone.utc) + timedelta(days=31)
    before_price, before_bal = dcoin.price(conn), balance(conn, uid)
    half = units // 2
    pay = dcoin.exchange(conn, uid, half, now=later)
    assert pay > 0 and balance(conn, uid) == before_bal + pay
    assert dcoin.price(conn) > before_price                          # 5% остались в копилке — цена выросла
    try:
        dcoin.exchange(conn, uid, 100, now=later + timedelta(hours=1))
        raise AssertionError("раз в сутки")
    except dcoin.ExchangeError as exc:
        assert "раз в сутки" in str(exc)


def test_candles_and_page(app, config, conn):
    uid = _user(conn)
    _buy(conn, uid, 10_000)
    _buy(conn, uid, 40_000)
    data = dcoin.candles(conn, "1m")
    assert len(data["candles"]) == dcoin.CANDLES
    last = data["candles"][-1]
    assert last[4] == dcoin.price(conn) and last[2] >= last[4]

    client = TestClient(app)
    web_login(client, "coiner@example.com", "password123")
    page = client.get("/panel/dcoin").text
    assert "dc-canvas" in page and "D-коин" in page and "Обмен откроется" in page
    j = client.get("/panel/data/dcoin?tf=5m").json()
    assert j["tf"] == "5m" and j["price"] > 0 and len(j["candles"]) == dcoin.CANDLES
    assert "dc-card" in client.get("/panel").text                     # карточка на главной кабинета


def test_finance_counts_pool_as_expense(conn, config):
    uid = _user(conn)
    _buy(conn, uid, 100_000, cost=50_000)                            # прибыль $5
    a = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    b = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    assert finance.net_profit(conn, a, b) == 50_000 - dcoin.state(conn)["pool"]


def test_admin_settings(app, config, conn):
    admin = TestClient(app)
    token = web_login(admin, "admin@example.com", "adminpass123")
    page = admin.get("/admin/settings").text
    assert "dcoin_pool_pct" in page
    form = {"csrf": token, "dcoin_per_usd": "50", "dcoin_pool_pct": "8", "dcoin_open_days": "7"}
    admin.post("/admin/settings", data=form)
    assert (dcoin.per_usd(conn), dcoin.pool_pct(conn), dcoin.open_days(conn)) == (50, 8, 7)


def test_each_purchase_moves_price_softly(conn):
    uid = _user(conn)
    for total, cost in ((10_000, 9_900), (500_000, 200_000), (3_000, 2_990), (90_000, 60_000), (1_000, 1_000)):
        _buy(conn, uid, total, cost)
    prices = [r[0] for r in conn.execute("SELECT price FROM dcoin_points ORDER BY id")]
    for a, b in pairwise(prices[1:]):                          # после первой покупки — шаги не больше 3%
        assert abs(b - a) / a <= 0.0301, (a, b)
    profit = conn.execute("SELECT SUM(total_micro - cost_micro) FROM orders").fetchone()[0]
    assert dcoin.state(conn)["pool"] <= profit * 20 // 100
