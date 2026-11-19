"""Мини-приложение: каталог, страница игры, покупка и заказ с кодами — всё внутри, без перехода на сайт."""

import hashlib
import hmac
import json
import time
from dataclasses import replace
from urllib.parse import urlencode

import pytest

from donatix import accounts, db

TOKEN = "123:app-token"


def _init(user):
    data = {"auth_date": str(int(time.time())), "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {"X-Tg-Init": urlencode(data)}


@pytest.fixture
def tc(app, config):
    app.state.config = replace(config, gift_bot_token=TOKEN)
    from fastapi.testclient import TestClient
    return TestClient(app)


H = _init({"id": 5501, "first_name": "Али", "username": "ali_t", "language_code": "ru"})


def test_catalog_and_game_page(tc):
    cat = tc.post("/tg/api/catalog", json={}, headers=H).json()
    assert cat["games"] and all(g["kind"] == "topup" for g in cat["games"])
    assert all(c["kind"] != "steam_gift" for c in cat["cards"])
    g = cat["games"][0]
    page = tc.post("/tg/api/game", json={"kind": g["kind"], "category": g["category"]}, headers=H).json()
    assert page["items"] and page["items"][0]["fields"]                  # ID игрока спрашиваем
    assert all("base_price" not in i for i in page["items"])             # закупочную цену не отдаём


def test_buy_needs_money_then_works_and_shows_order(tc, conn):
    cat = tc.post("/tg/api/catalog", json={}, headers=H).json()
    g = cat["games"][0]
    item = tc.post("/tg/api/game", json={"kind": g["kind"], "category": g["category"]}, headers=H).json()["items"][0]
    fields = {f["key"]: "123456789" for f in item["fields"]}
    r = tc.post("/tg/api/order", json={"product_id": item["product_id"], "fields": fields, "idem": "a1"}, headers=H).json()
    assert r["ok"] is False and r["need"] > 0                             # денег нет — предложим пополнить
    uid = conn.execute("SELECT user_id FROM shop_users WHERE tg_id = 5501").fetchone()[0]
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 100_000_000, "Пополнение")
    r = tc.post("/tg/api/order", json={"product_id": item["product_id"], "fields": fields, "idem": "a2"}, headers=H).json()
    assert r["ok"] and r["ref"]
    v = tc.post("/tg/api/order/view", json={"ref": r["ref"]}, headers=H).json()
    assert v["ref"] == r["ref"] and v["fields"]
    other = _init({"id": 5502, "first_name": "Чужой"})
    assert tc.post("/tg/api/order/view", json={"ref": r["ref"]}, headers=other).status_code == 404   # чужой заказ не видно


def test_ping_marks_online_and_reviews_open(tc):
    lob = tc.post("/tg/api/ping", json={}, headers=H).json()
    assert lob["online"] >= 1 and lob["rooms"] == []
    assert tc.post("/tg/api/reviews", json={}, headers=H).json()["total"] == 0
    assert tc.post("/tg/api/catalog", json={}).status_code == 403          # без подписи Telegram — нельзя


def test_app_demo_page_is_public_and_not_indexed(client):
    r = client.get("/app/demo")
    assert r.status_code == 200 and "ДЕМО" in r.text and 'name="robots" content="noindex"' in r.text


def test_site_app_uses_site_login_and_needs_session_token(client, conn):
    """Приложение сайта /app: те же данные, что в мини-приложении, но по входу на сайте и токену этой сессии."""
    from conftest import csrf_of, make_client, web_login
    assert client.get("/app", follow_redirects=False).headers["location"] == "/login"      # без входа — на вход
    uid = make_client(conn, login="appuser")[0]
    web_login(client, "appuser@example.com", "password123")
    page = client.get("/app")
    assert page.status_code == 200 and "Donatix" in page.text
    assert client.post("/tg/api/init", json={}).status_code == 403                          # вход есть, токена нет — нельзя
    assert client.post("/tg/api/init", json={}, headers={"X-Dx-App": "wrong"}).status_code == 403
    token = csrf_of(client.get("/panel/balance").text)
    d = client.post("/tg/api/init", json={}, headers={"X-Dx-App": token}).json()
    assert d["me"]["id"] == uid and d["me"]["name"] == "appuser" and d["gifts"] == []
    assert client.post("/tg/api/catalog", json={}, headers={"X-Dx-App": token}).json()["games"]


def test_mini_app_opens_same_p2p_under_same_account(tc, conn):
    """Кнопка «P2P · D-коин» в мини-приложении: вход по подписи Telegram → та же биржа, что на сайте, «Назад» — в приложение."""
    r = tc.post("/tg/api/session", json={"to": "p2p"}, headers=H).json()
    assert r["url"] == "/panel/p2p"
    page = tc.get("/panel/p2p").text
    assert "P2P" in page and 'href="/tg"' in page                       # стрелка назад — в мини-приложение
    assert tc.post("/tg/api/session", json={"to": "p2p"}).status_code == 403
    assert 'data-act="p2p"' in tc.get("/tg").text
