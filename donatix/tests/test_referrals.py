import re

from conftest import csrf_of, make_client, web_login

from donatix import db, orders, referrals


def _order(conn, uid, n, total, cost):
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO orders (public_id, user_id, product_id, kind, product_name, quantity, unit_price, total_micro, "
        "cost_micro, status, supplier_idem_key, created_at, updated_at) "
        "VALUES (?, ?, 'tg-stars', 'telegram_stars', 'Stars', 1, '1', ?, ?, 'processing', ?, ?, ?)",
        (f"dx-r{n}", uid, total, cost, f"r{n}", ts, ts))
    return cur.lastrowid


def _register(client, login, email, ref_url="/register"):
    page = client.get(ref_url).text
    return client.post("/register", data={"csrf": csrf_of(page), "email": email, "login": login,
                                          "password": "password123", "password2": "password123"},
                       follow_redirects=False)


def test_register_by_link_and_bonus_once(app, client, conn):
    from fastapi.testclient import TestClient
    inviter, _ = make_client(conn, "inviter", balance="0")
    code = referrals.code_for(conn, inviter)
    friend_client = TestClient(app)
    r = _register(friend_client, "friend1", "friend1@example.com", f"/register?ref={code}")
    assert r.status_code == 303
    friend = conn.execute("SELECT id, referred_by FROM users WHERE login = 'friend1'").fetchone()
    assert friend["referred_by"] == inviter

    oid = _order(conn, friend["id"], 1, total=120_000, cost=100_000)      # прибыль $2
    assert orders.complete(conn, oid, {}, "completed")
    bal = conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter,)).fetchone()[0]
    assert bal == 4_000                                                   # 20% от $2 = $0.40
    orders.complete(conn, oid, {}, "completed")                           # повтор — второй раз не начисляется
    assert referrals.award(conn, oid) == 0
    assert conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter,)).fetchone()[0] == 4_000


def test_no_bonus_without_profit_or_when_off(conn):
    inviter, _ = make_client(conn, "inv2", balance="0")
    friend, _ = make_client(conn, "fr2", balance="0")
    conn.execute("UPDATE users SET referred_by = ? WHERE id = ?", (inviter, friend))
    loss = _order(conn, friend, 2, total=100_000, cost=100_000)
    orders.complete(conn, loss, {}, "completed")
    db.set_setting(conn, "referral.percent", "0")
    off = _order(conn, friend, 3, total=200_000, cost=100_000)
    orders.complete(conn, off, {}, "completed")
    assert conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter,)).fetchone()[0] == 0


def test_cannot_refer_self_or_reattach(conn):
    a, _ = make_client(conn, "selfy", balance="0")
    b, _ = make_client(conn, "other", balance="0")
    assert not referrals.attach(conn, a, referrals.code_for(conn, a))
    assert referrals.attach(conn, b, referrals.code_for(conn, a))
    c, _ = make_client(conn, "third", balance="0")
    assert not referrals.attach(conn, b, referrals.code_for(conn, c))     # уже закреплён
    assert not referrals.attach(conn, b, "../bad code")


def test_referrals_page(client, conn):
    make_client(conn)
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/referrals").text
    assert "Пригласить друзей" in page and re.search(r"/register\?ref=[a-z0-9]{8}", page)
