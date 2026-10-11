"""«Живой» сайт: состояние для страницы (баланс, уведомления, заказы) и поток Server-Sent Events."""
from conftest import make_client, web_login

from donatix import accounts, db, live


def test_state_changes_when_balance_and_orders_change(app, config, conn):
    uid = make_client(conn, balance="5")[0]
    s1 = live.state(config, uid, False, "USD")
    assert s1["balance"] == 50000 and s1["balance_html"].startswith("$5")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, -10000, "Заказ")
    s2 = live.state(config, uid, False, "USD")
    assert s2["balance"] == 40000 and s2["sig"] != s1["sig"]                # новая запись — страница обновит списки
    assert "с." in live.state(config, uid, False, "TJS")["balance_html"]


def test_admin_sees_site_wide_changes(app, config, conn):
    admin = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]
    uid = make_client(conn, balance="5")[0]
    a1 = live.state(config, admin, True, "USD")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, -10000, "Заказ клиента")
    assert live.state(config, admin, True, "USD")["sig"] != a1["sig"]       # покупка любого клиента видна админу


def test_endpoint_once_and_login(app, client, conn):
    assert client.get("/panel/data/live?once=1").status_code == 401
    make_client(conn, balance="5")
    web_login(client, "shop1@example.com", "password123")
    d = client.get("/panel/data/live?once=1").json()
    assert d["balance"] == 50000 and "unread" in d
    page = client.get("/panel").text
    assert 'data-live="balance"' in page and "/panel/data/live" in page
