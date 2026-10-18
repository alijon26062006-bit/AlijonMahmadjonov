"""Акция: особая цена в сомони на N дней — только сайт и свой бот, не API."""
import time
from decimal import Decimal

from conftest import balance, make_client

from donatix import accounts, cache, catalog, db, orders, promo


def _ff(conn):
    return conn.execute("SELECT id FROM products WHERE id LIKE 'topup-ff-%' ORDER BY id LIMIT 1").fetchone()["id"]


def _start(conn, pid, price="49", days="3"):
    data = promo.save(conn, product_id=pid, price_tjs=price, days=days, title="Ваучер на месяц", on=True)
    cache.clear()
    return data


def test_site_price_is_exactly_49_tjs(conn, config):
    pid = _ff(conn)
    _start(conn, pid)
    user = accounts.get_user(conn, make_client(conn, "buyer")[0])
    product = catalog.get_product(conn, pid)
    rate = Decimal(str(config.tjs_rate))
    unit = promo.unit_usd(config, None, pid)
    assert unit == (Decimal(49) / rate).quantize(Decimal("0.0001"), rounding="ROUND_DOWN")
    view = catalog.public_view(product, Decimal(5), config=config, user=None)
    assert view["promo"] and Decimal(view["price_usd"]) == unit and "regular_usd" in view
    assert (unit * rate).quantize(Decimal("0.01"), rounding="ROUND_UP") == Decimal("49.00")
    assert user is not None


def test_api_partner_pays_regular_price(conn, config, shop):
    pid = _ff(conn)
    _start(conn, pid)
    api_user = conn.execute("SELECT u.*, k.id AS api_key_id FROM users u JOIN api_keys k ON k.user_id = u.id "
                            "WHERE u.id = ?", (shop["id"],)).fetchone()
    assert accounts.is_api(api_user)
    assert promo.unit_usd(config, api_user, pid) is None
    product = catalog.get_product(conn, pid)
    q = orders.quote(config, api_user, product, 1)
    assert q["unit_price"] != promo.unit_usd(config, None, pid)
    assert "promo" not in catalog.public_view(product, Decimal(8)) or not catalog.public_view(product, Decimal(8))["promo"]


def test_api_products_endpoint_ignores_promo(client, conn, config, shop):
    pid = _ff(conn)
    _start(conn, pid, price="1")
    items = client.get(f"/api/v1/products?q={pid}", headers=shop["h"]).json().get("items", [])
    for it in items:
        if it["product_id"] == pid:
            assert not it.get("promo")


def test_expired_promo_gone(conn, config):
    pid = _ff(conn)
    _start(conn, pid)
    p = promo.get(conn)
    p["ends"] = time.time() - 1
    import json
    db.set_setting(conn, promo.KEY, json.dumps(p))
    cache.clear()
    assert promo.active(conn) is None
    assert promo.unit_usd(config, None, pid) is None
    assert promo.banner(conn, config) is None


def test_stop_and_validation(conn, config):
    pid = _ff(conn)
    _start(conn, pid)
    promo.stop(conn)
    cache.clear()
    assert promo.unit_usd(config, None, pid) is None
    for bad in ({"price_tjs": "0"}, {"price_tjs": "abc"}, {"days": "99"}):
        args = {"product_id": pid, "price_tjs": "49", "days": "3", "title": "", "on": True, **bad}
        try:
            promo.save(conn, **args)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_timer_kept_when_saving_same(conn, config):
    pid = _ff(conn)
    a = _start(conn, pid)
    time.sleep(0.01)
    b = _start(conn, pid, days="5")
    assert b["starts"] == a["starts"] and b["ends"] == a["starts"] + 5 * 86400


def test_home_shows_banner(client, conn):
    pid = _ff(conn)
    assert "promo-hero" not in client.get("/").text
    _start(conn, pid)
    html = client.get("/").text
    assert "promo-hero" in html and f"/panel/buy/{pid}" in html and "Купить за 49 с." in html


def test_site_order_charged_promo_price(conn, config, supplier):
    pid = _ff(conn)
    _start(conn, pid)
    uid = accounts.create_user(conn, email="b@example.com", login="buyer1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 100_000, "Пополнение")
    user = accounts.get_user(conn, uid)
    product = catalog.get_product(conn, pid)
    fields = {f["key"]: "123456789" for f in product["fields"]}
    order, _ = orders.create_order(conn, config, supplier, user, product_id=pid, quantity=1, fields=fields,
                                   client_idem_key="t1", source="panel")
    unit = promo.unit_usd(config, None, pid)
    assert order["total_micro"] == int(unit * 10_000)
    assert balance(conn, uid) == 100_000 - int(unit * 10_000)


def test_admin_page(client, conn):
    from conftest import web_login
    token = web_login(client, "admin@example.com", "adminpass123")
    assert client.get("/admin/promo").status_code == 200
    r = client.post("/admin/promo", data={"csrf": token, "product_id": _ff(conn), "price_tjs": "49", "days": "3",
                                          "title": "Ваучер на месяц"}, follow_redirects=False)
    assert r.status_code == 303
    assert promo.active(conn) is not None


def _buy(conn, config, supplier, uid, pid, key):
    user = accounts.get_user(conn, uid)
    product = catalog.get_product(conn, pid)
    fields = {f["key"]: "123456789" for f in product["fields"]}
    order, _ = orders.create_order(conn, config, supplier, user, product_id=pid, quantity=1, fields=fields,
                                   client_idem_key=key, source="panel")
    cache.clear()
    return order


def _dcoin_on(conn):
    from donatix import dcoin
    db.set_setting(conn, "dcoin.per_usd", "100")
    db.set_setting(conn, "dcoin.pool_pct", "10")
    s = dcoin.state(conn)
    dcoin._point(conn, 50_000, s["supply"] or 1_000_000, "seed", reserve=s["reserve"])   # в копилке $5
    return dcoin


def test_other_goods_price_unchanged(conn, config, supplier):
    pid = _ff(conn)
    other = conn.execute("SELECT id FROM products WHERE kind = 'topup' AND id != ? ORDER BY id LIMIT 1",
                         (pid,)).fetchone()["id"]
    uid = accounts.create_user(conn, email="r@example.com", login="recoup1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 50_000_000, "Пополнение")
    user = accounts.get_user(conn, uid)
    before = orders.quote(config, user, catalog.get_product(conn, other), 1)["total_micro"]
    _start(conn, pid, price="1")
    _buy(conn, config, supplier, uid, pid, "v1")
    assert orders.quote(config, user, catalog.get_product(conn, other), 1)["total_micro"] == before


def test_loss_taken_from_dcoin_pool_on_completion(conn, config, supplier):
    dcoin = _dcoin_on(conn)
    pid = _ff(conn)
    _start(conn, pid, price="1")
    uid = accounts.create_user(conn, email="d@example.com", login="dcoin1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 1_000_000, "Пополнение")
    order = _buy(conn, config, supplier, uid, pid, "d1")
    t = promo.totals(conn)
    assert t["sold"] == 1 and t["lost"] > 0 and t["back"] == 0     # заказ ещё в работе — копилку не трогаем
    pool_before, price_before = dcoin.state(conn)["pool"], dcoin.price(conn)

    orders.process_pending(conn, supplier)                          # выполнен
    assert conn.execute("SELECT status FROM orders WHERE id = ?", (order["id"],)).fetchone()[0] == "completed"
    t = promo.totals(conn)
    assert t["back"] == t["lost"] and t["left"] == 0
    s = dcoin.state(conn)
    assert s["pool"] < pool_before + 1 and dcoin.price(conn) < price_before + 1e-18
    assert conn.execute("SELECT 1 FROM dcoin_points WHERE reason = 'promo'").fetchone()
    assert promo.settle(conn, order["id"]) == 0                    # второй раз — не забираем


def test_failed_order_not_counted(conn, config, supplier):
    pid = _ff(conn)
    _start(conn, pid, price="1")
    uid = accounts.create_user(conn, email="f@example.com", login="failer1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 1_000_000, "Пополнение")
    order = _buy(conn, config, supplier, uid, pid, "f1")
    conn.execute("UPDATE orders SET status = 'failed' WHERE public_id = ?", (order["public_id"],))
    assert promo.totals(conn)["lost"] == 0
    assert promo.settle(conn, order["id"]) == 0


def test_take_never_empties_pool(conn):
    dcoin = _dcoin_on(conn)
    pool = dcoin.state(conn)["pool"]
    taken = dcoin.take_for_promo(conn, pool * 10)
    assert taken == int(pool * dcoin.PROMO_MAX_TAKE) and dcoin.state(conn)["pool"] > 0


def test_one_promo_voucher_per_buyer(conn, config, supplier, monkeypatch):
    """По акции — 1 раз на покупателя (аккаунт сайта или бота; покупки до правила тоже в счёт).
    Дальше — обычная цена с объяснением; 2 шт. сразу — отказ с причиной; другой покупатель — по акции."""
    pid = _ff(conn)
    _start(conn, pid)
    product = catalog.get_product(conn, pid)

    def make(login):
        uid = accounts.create_user(conn, email=f"{login}@example.com", login=login, password="password123",
                                   status="active")
        with db.tx(conn):
            accounts.post_ledger(conn, uid, 1_000_000, "Пополнение")
        return uid

    def buy(uid, key, qty=1):
        fields = {f["key"]: "111222333" for f in product["fields"]}
        order, _ = orders.create_order(conn, config, supplier, accounts.get_user(conn, uid), product_id=pid,
                                       quantity=qty, fields=fields, client_idem_key=key, source="panel")
        cache.clear()
        return order
    unit = int(promo.unit_usd(config, None, pid) * 10_000)
    a, b = make("promo_a"), make("promo_b")
    first = buy(a, "k1")
    assert first["total_micro"] == unit and promo.used(conn, a) == first["public_id"]
    assert promo.unit_usd(config, accounts.get_user(conn, a), pid) is None      # ему — уже обычная цена
    assert buy(a, "k2")["total_micro"] != unit                                  # купил, но не по цене акции
    assert buy(b, "k3")["total_micro"] == unit                                  # тот же игровой ID — можно
    # Два заказа разом (корзина): цена ещё «акционная» в кеше — второй отказ с причиной, деньги целы
    c = make("promo_c")
    fields = {f["key"]: "111222333" for f in product["fields"]}
    orders.create_order(conn, config, supplier, accounts.get_user(conn, c), product_id=pid, quantity=1,
                        fields=fields, client_idem_key="c1", source="panel")
    left = balance(conn, c)
    monkeypatch.setattr(promo, "_used_cached", lambda *a: False)   # как будто кеш ещё не знает о покупке
    try:
        orders.create_order(conn, config, supplier, accounts.get_user(conn, c), product_id=pid, quantity=1,
                            fields=fields, client_idem_key="c2", source="panel")
        raise AssertionError("должен быть отказ")
    except orders.OrderError as exc:
        assert exc.code == "promo_limit" and "1 раз" in str(exc) and "dx-" in str(exc)
    assert balance(conn, c) == left
    assert promo.banner(conn, config)["limit"]
