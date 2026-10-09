"""Виртуальные номера 5sim: цена с наценкой 12 %, покупка, код, возврат при неудаче — один раз."""
from decimal import Decimal

import pytest
from conftest import balance, make_client, web_login

from donatix import cache, fivesim

PRICES = {"telegram": {
    "indonesia": {"virtual21": {"cost": 0.25, "count": 120, "rate": 91.5}, "virtual4": {"cost": 0.4, "count": 3}},
    "usa": {"virtual12": {"cost": 1.1, "count": 0}},          # нет номеров — не показываем
    "tajikistan": {"any": {"cost": 0.5, "count": 7}}}}


@pytest.fixture
def five(config, monkeypatch):
    config.fivesim_token, config.fivesim_markup = "eyJx.y.z", Decimal("12")
    cache.clear()
    state = {"check": {"status": "PENDING", "sms": []}, "buy": None, "calls": []}

    def fake(cfg, path, params=None):
        state["calls"].append(path)
        if path == "/guest/prices":
            if params.get("country"):
                return {params["country"]: {params["product"]: PRICES["telegram"].get(params["country"], {})}}
            return PRICES
        if path.startswith("/user/buy/"):
            if state["buy"]:
                raise fivesim.FiveSimError(state["buy"])
            return {"id": 555, "phone": "+6281234567", "operator": "virtual21", "status": "PENDING",
                    "expires": "2030-01-01T00:15:00Z"}
        if path.startswith("/user/check/"):
            return state["check"]
        if path.startswith("/user/cancel/"):
            return {"status": "CANCELED"}
        if path == "/user/profile":
            return {"balance": 3.5}
        raise AssertionError(path)
    monkeypatch.setattr(fivesim, "_get", fake)
    return state


def test_prices_with_markup(config, five):
    rows = fivesim.prices(config, "telegram")
    assert [r["country"] for r in rows] == ["indonesia", "tajikistan"]   # без номеров — не показываем
    assert rows[0]["price_micro"] == 2800          # 0.25 × 1.12 = 0.28 $
    assert rows[1]["title"] == "Таджикистан" and rows[1]["price_micro"] == 5600


def test_buy_code_and_no_refund(app, config, conn, five):
    uid = make_client(conn, balance="5")[0]
    from donatix import accounts
    vid = fivesim.buy(conn, config, accounts.get_user(conn, uid), "telegram", "indonesia")
    assert balance(conn, uid) == 50000 - 2800
    assert "/user/buy/activation/indonesia/any/telegram" in five["calls"]
    five["check"] = {"status": "RECEIVED", "sms": [{"text": "Telegram code 12345", "code": "12345"}]}
    v = fivesim.refresh(conn, config, vid)
    assert v["code"] == "12345" and v["phone"] == "+6281234567"
    five["check"] = {"status": "FINISHED", "sms": [{"code": "12345"}]}
    fivesim.refresh(conn, config, vid)
    assert balance(conn, uid) == 50000 - 2800      # код получен — денег не возвращаем


def test_timeout_refunds_once(app, config, conn, five):
    uid = make_client(conn, balance="5")[0]
    from donatix import accounts
    vid = fivesim.buy(conn, config, accounts.get_user(conn, uid), "telegram", "indonesia")
    five["check"] = {"status": "TIMEOUT", "sms": []}
    fivesim.refresh(conn, config, vid)
    fivesim.refresh(conn, config, vid)
    assert balance(conn, uid) == 50000


def test_buy_failure_refunds_and_no_money(app, config, conn, five):
    uid = make_client(conn, balance="5")[0]
    from donatix import accounts
    five["buy"] = "no free phones"
    with pytest.raises(fivesim.FiveSimError, match="закончились"):
        fivesim.buy(conn, config, accounts.get_user(conn, uid), "telegram", "indonesia")
    assert balance(conn, uid) == 50000
    poor = make_client(conn, login="poor", balance="0")[0]
    five["buy"] = None
    with pytest.raises(fivesim.FiveSimError, match="не хватает"):
        fivesim.buy(conn, config, accounts.get_user(conn, poor), "telegram", "indonesia")


def test_pages_and_cancel(app, client, config, conn, five):
    make_client(conn, balance="5")
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/numbers").text
    assert "Индонезия" in page and "Таджикистан" in page
    import re
    csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    r = client.post("/panel/numbers/buy", data={"csrf": csrf, "service": "telegram", "country": "indonesia"},
                    follow_redirects=False)
    vid = int(r.headers["location"].rsplit("/", 1)[1])
    assert "+6281234567" in client.get(f"/panel/numbers/{vid}").text
    client.post(f"/panel/numbers/{vid}/cancel", data={"csrf": csrf})
    assert balance(conn, conn.execute("SELECT id FROM users WHERE login='shop1'").fetchone()[0]) == 50000
    assert "Виртуальные номера" in client.get("/").text or "виртуальные номера" in client.get("/").text
