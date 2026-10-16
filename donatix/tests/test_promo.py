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


def test_lost_money_comes_back_via_other_goods(conn, config, supplier, shop):
    pid = _ff(conn)
    other = conn.execute("SELECT id FROM products WHERE kind = 'topup' AND id != ? ORDER BY id LIMIT 1",
                         (pid,)).fetchone()["id"]
    _start(conn, pid, price="1")
    uid = accounts.create_user(conn, email="r@example.com", login="recoup1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 50_000_000, "Пополнение")
    user = accounts.get_user(conn, uid)
    regular_other = orders.quote(config, user, catalog.get_product(conn, other), 1)["total_micro"]
    assert promo.recoup_pct(config, user) is None            # пока ничего не продали — надбавки нет

    _buy(conn, config, supplier, uid, pid, "v1")              # ваучер по акции → минус
    t = promo.totals(conn)
    assert t["sold"] == 1 and t["lost"] > 0
    assert promo.recoup_pct(config, user) == promo.RECOUP_PCT
    api_user = conn.execute("SELECT u.*, k.id AS api_key_id FROM users u JOIN api_keys k ON k.user_id = u.id "
                            "WHERE u.id = ?", (shop["id"],)).fetchone()
    assert promo.recoup_pct(config, api_user) is None         # партнёры по API — без надбавки

    q = orders.quote(config, user, catalog.get_product(conn, other), 1)
    assert q["total_micro"] > regular_other and q["promo_micro"] < 0
    view = catalog.public_view(catalog.get_product(conn, other), accounts.markup_for(user, config, "topup"),
                               config=config, user=user)
    assert int(Decimal(view["price_usd"]) * 10_000) >= q["total_micro"] - 1

    n = 0
    while promo.totals(conn)["left"] > 0 and n < 2000:      # покупают другое — минус уходит
        _buy(conn, config, supplier, uid, other, f"o{n}")
        n += 1
    assert promo.totals(conn)["left"] == 0
    assert promo.recoup_pct(config, user) is None             # вернули — надбавка снялась
    assert orders.quote(config, user, catalog.get_product(conn, other), 1)["total_micro"] == regular_other


def test_failed_order_not_counted(conn, config, supplier):
    pid = _ff(conn)
    _start(conn, pid, price="1")
    uid = accounts.create_user(conn, email="f@example.com", login="failer1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 1_000_000, "Пополнение")
    order = _buy(conn, config, supplier, uid, pid, "f1")
    conn.execute("UPDATE orders SET status = 'failed' WHERE public_id = ?", (order["public_id"],))
    assert promo.totals(conn)["lost"] == 0


def test_recoup_stops_after_tail_days(conn, config, supplier):
    import json
    pid = _ff(conn)
    _start(conn, pid, price="1")
    uid = accounts.create_user(conn, email="t@example.com", login="tail1", password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 1_000_000, "Пополнение")
    _buy(conn, config, supplier, uid, pid, "t1")
    p = promo.get(conn)
    p["ends"] = time.time() - promo.RECOUP_DAYS * 86400 - 1
    db.set_setting(conn, promo.KEY, json.dumps(p))
    cache.clear()
    assert promo.totals(conn)["left"] > 0 and promo.recoup_pct(config, None) is None
