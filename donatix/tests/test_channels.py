"""Аналитика админа: продажи по каналам (сайт, наш бот, боты партнёров, API) и по партнёрам."""
from conftest import web_login

from donatix import analytics, db


def _order(conn, uid, source, key=None, total=10_000, cost=8_000, status="completed"):
    ts = db.now()
    conn.execute("INSERT INTO orders (user_id, product_id, kind, product_name, quantity, fields_json, unit_price, "
                 "total_micro, cost_micro, status, supplier_idem_key, idempotent_supply, client_idem_key, source, "
                 "created_at, updated_at, api_key_id) VALUES (?, 'p', 'topup', 'x', 1, '{}', '1', ?, ?, ?, ?, 0, NULL, "
                 "?, ?, ?, ?)", (uid, total, cost, status, f"k{ts}{source}{key}{total}", source, ts, ts, key))


def test_channels_split(conn, shop):
    from donatix import accounts
    uid = shop["id"]
    bot_key = conn.execute("SELECT id FROM api_keys WHERE user_id = ?", (uid,)).fetchone()["id"]
    accounts.create_api_key(conn, uid, "Мой сайт")
    site_key = conn.execute("SELECT id FROM api_keys WHERE user_id = ? AND name = 'Мой сайт'", (uid,)).fetchone()["id"]
    conn.execute("INSERT INTO bots (user_id, token_enc, username, admin_ids, api_key_id, created_at, updated_at) "
                 "VALUES (?, 'x', 'partnershop_bot', '1', ?, ?, ?)", (uid, bot_key, db.now(), db.now()))
    _order(conn, uid, "panel", total=10_000)
    _order(conn, uid, "quick", total=20_000)
    _order(conn, uid, "shopbot", total=30_000)
    _order(conn, uid, "api", bot_key, total=40_000)
    _order(conn, uid, "api", site_key, total=50_000)
    _order(conn, uid, "api", site_key, total=99_000, status="failed")   # не выполнен — не в выручке
    a = analytics.build(conn, "30d")
    ch = {c["key"]: c for c in a["channels"]}
    assert ch["site"]["turnover"] == 30_000 and ch["site"]["done"] == 2
    assert ch["ourbot"]["turnover"] == 30_000
    assert ch["pbots"]["turnover"] == 40_000
    assert ch["api"]["turnover"] == 50_000 and ch["api"]["created"] == 2
    assert round(sum(c["share"] for c in a["channels"])) == 100
    p = {x["ch"]: x for x in a["partners"]}
    assert p["pbots"]["bot"] == "partnershop_bot" and p["pbots"]["turnover"] == 40_000
    assert p["api"]["key_name"] == "Мой сайт" and p["api"]["profit"] == 50_000 - 8_000


def test_client_stats_no_channels(conn, shop):
    assert analytics.build(conn, "30d", user_id=shop["id"])["channels"] == []


def test_admin_page_shows_blocks(client, conn):
    web_login(client, "admin@example.com", "adminpass123")
    html = client.get("/admin/stats").text
    assert "Откуда продажи" in html and "Партнёры: боты и API" in html
