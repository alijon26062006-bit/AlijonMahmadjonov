"""API для партнёров: виртуальные номера и подарки Telegram. Деньги, возвраты, права — как на сайте."""
from decimal import Decimal

import pytest
from conftest import balance, make_client

from donatix import cache, db, fivesim, tggifts
from donatix.money import fmt

PRICES = {"telegram": {"indonesia": {"virtual21": {"cost": 0.25, "count": 120, "rate": 91.5}}}}


@pytest.fixture
def numbers(config, monkeypatch):
    config.fivesim_token, config.fivesim_markup = "eyJx.y.z", Decimal("12")
    config.fivesim_rub_rate = 0   # без пересчёта: cost = USD
    cache.clear()
    state = {"check": {"status": "PENDING", "sms": []}, "buy_error": None}

    def fake(cfg, path, params=None):
        if path == "/guest/prices":
            return {params["product"]: PRICES["telegram"]} if not params.get("country") else \
                {params["country"]: {params["product"]: PRICES["telegram"].get(params["country"], {})}}
        if path == "/guest/countries":
            return {"indonesia": {"name": "indonesia", "iso": {}, "prefix": {}}}
        if path.startswith("/user/buy/"):
            if state["buy_error"]:
                raise fivesim.FiveSimError(state["buy_error"])
            return {"id": 555, "phone": "+6281234567", "operator": "virtual21", "status": "PENDING",
                    "expires": "2030-01-01T00:15:00Z"}
        if path.startswith("/user/check/"):
            return state["check"]
        if path.startswith("/user/cancel/"):
            return {"status": "CANCELED"}
        raise AssertionError(path)
    monkeypatch.setattr(fivesim, "_get", fake)
    return state


def test_numbers_need_key(client):
    assert client.get("/api/v1/numbers/services").status_code == 401


def test_services_and_countries(client, shop, config, numbers):
    s = client.get("/api/v1/numbers/services", headers=shop["h"]).json()
    assert s["ok"] and {"service": "telegram", "title": "Telegram"} in s["items"]
    c = client.get("/api/v1/numbers/countries?service=telegram", headers=shop["h"]).json()
    assert c["items"][0]["country"] == "indonesia" and c["items"][0]["available"] == 120
    assert c["items"][0]["price_usd"] == fmt(fivesim.sale_micro(config, 0.25))
    bad = client.get("/api/v1/numbers/countries?service=nope", headers=shop["h"])
    assert bad.status_code == 400 and bad.json()["code"] == "unknown_service"


def test_buy_number_charges_site_price_and_returns_code(client, conn, shop, config, numbers):
    r = client.post("/api/v1/numbers/orders", headers=shop["h"], json={"service": "telegram", "country": "indonesia"})
    assert r.status_code == 201, r.text
    order = r.json()["order"]
    assert order["phone"] == "+6281234567" and order["status"] == "PENDING"
    assert balance(conn, shop["id"]) < 100_000_000       # деньги списаны с баланса партнёра
    numbers["check"] = {"status": "RECEIVED", "sms": [{"code": "4815", "text": "Your code 4815"}]}
    got = client.get(f"/api/v1/numbers/orders/{order['id']}", headers=shop["h"]).json()["order"]
    assert got["code"] == "4815" and got["sms"] == "Your code 4815"


def test_number_price_equals_site_price(client, conn, shop, config, numbers):
    expect = fivesim.quote(config, "telegram", "indonesia")["price_micro"]
    before = balance(conn, shop["id"])
    client.post("/api/v1/numbers/orders", headers=shop["h"], json={"service": "telegram", "country": "indonesia"})
    assert before - balance(conn, shop["id"]) == expect


def test_failed_purchase_is_refunded(client, conn, shop, config, numbers):
    before = balance(conn, shop["id"])
    numbers["buy_error"] = "no free phones"
    r = client.post("/api/v1/numbers/orders", headers=shop["h"], json={"service": "telegram", "country": "indonesia"})
    assert r.status_code == 400 and r.json()["code"] == "order_failed"
    assert balance(conn, shop["id"]) == before              # деньги не ушли


def test_insufficient_balance_is_402(client, conn, shop, config, numbers):
    uid, key = make_client(conn, login="poor", balance="0")
    r = client.post("/api/v1/numbers/orders", headers={"X-API-Key": key},
                    json={"service": "telegram", "country": "indonesia"})
    assert r.status_code == 402 and r.json()["code"] == "insufficient_balance"


def test_number_belongs_to_owner_only(client, conn, shop, config, numbers):
    r = client.post("/api/v1/numbers/orders", headers=shop["h"], json={"service": "telegram", "country": "indonesia"})
    oid = r.json()["order"]["id"]
    _, other = make_client(conn, login="other")
    assert client.get(f"/api/v1/numbers/orders/{oid}", headers={"X-API-Key": other}).status_code == 404
    assert client.post(f"/api/v1/numbers/orders/{oid}/cancel", headers={"X-API-Key": other}).status_code == 404


def test_cancel_number(client, conn, shop, config, numbers):
    oid = client.post("/api/v1/numbers/orders", headers=shop["h"],
                      json={"service": "telegram", "country": "indonesia"}).json()["order"]["id"]
    r = client.post(f"/api/v1/numbers/orders/{oid}/cancel", headers=shop["h"])
    assert r.status_code == 200 and r.json()["order"]["status"] == "CANCELED"


# ── подарки ──────────────────────────────────────────────


@pytest.fixture
def gifts(config, conn):
    config.gift_bot_token = "123:gift-token"
    config.kind_markups = {}
    tggifts.ensure(conn)
    with db.tx(conn):
        conn.execute("INSERT INTO tg_gifts (id, star_count, emoji, active, hidden, sort, updated_at) "
                     "VALUES ('g15', 15, '🧸', 1, 0, 1, ?)", (db.now(),))
        conn.execute("INSERT INTO tg_gifts (id, star_count, emoji, active, hidden, sort, updated_at) "
                     "VALUES ('g25', 25, '🌹', 1, 1, 2, ?)", (db.now(),))   # скрыт админом — не отдаём
    return config


def test_gift_list_hides_hidden(client, shop, gifts):
    items = client.get("/api/v1/gifts", headers=shop["h"]).json()["items"]
    assert [g["gift_id"] for g in items] == ["g15"]


def test_gift_to_known_user_is_paid_and_queued(client, conn, shop, gifts):
    uid, key = make_client(conn, login="friend", balance="0")
    conn.execute("INSERT INTO gift_users (tg_id, username, updated_at) VALUES (777, 'friend', ?)", (db.now(),))
    r = client.post("/api/v1/gifts/orders", headers=shop["h"],
                    json={"gift_id": "g15", "recipient": "@friend"})
    assert r.status_code == 201, r.text
    o = r.json()["order"]
    assert o["status"] == "paid" and o["stars"] == 15 and o["link"] is None
    assert balance(conn, shop["id"]) < 100_000_000
    got = client.get(f"/api/v1/gifts/orders/{o['id']}", headers=shop["h"]).json()["order"]
    assert got["id"] == o["id"]


def test_gift_without_known_recipient_gives_link(client, conn, shop, gifts):
    db.set_setting(conn, "gifts.bot_username", "donatixgiftbot")
    r = client.post("/api/v1/gifts/orders", headers=shop["h"], json={"gift_id": "g15"})
    o = r.json()["order"]
    assert o["status"] == "awaiting_recipient"
    assert o["link"].startswith("https://t.me/donatixgiftbot?start=g_")


def test_gift_hidden_or_missing_is_rejected(client, shop, gifts):
    r = client.post("/api/v1/gifts/orders", headers=shop["h"], json={"gift_id": "g25"})
    assert r.status_code == 400 and r.json()["code"] == "order_failed"


def test_gift_other_user_cannot_read(client, conn, shop, gifts):
    o = client.post("/api/v1/gifts/orders", headers=shop["h"], json={"gift_id": "g15"}).json()["order"]
    _, other = make_client(conn, login="snoop")
    assert client.get(f"/api/v1/gifts/orders/{o['id']}", headers={"X-API-Key": other}).status_code == 404
