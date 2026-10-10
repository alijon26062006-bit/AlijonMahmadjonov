"""Виртуальные номера 5sim: цена с наценкой 12 %, покупка, код, возврат при неудаче — один раз."""
from decimal import Decimal

import pytest
from conftest import balance, make_client, web_login

from donatix import cache, fivesim

PRICES = {"telegram": {
    "indonesia": {"virtual21": {"cost": 0.25, "count": 120, "rate": 91.5}, "virtual4": {"cost": 0.4, "count": 3}},
    "usa": {"virtual12": {"cost": 1.1, "count": 0}},          # нет номеров — не показываем
    "tajikistan": {"any": {"cost": 0.5, "count": 7}}},
    "1day": {"indonesia": {"virtual21": {"cost": 1.0, "count": 5}, "virtual4": {"cost": 0.8, "count": 2}}}}


@pytest.fixture
def five(config, monkeypatch):
    config.fivesim_token, config.fivesim_markup = "eyJx.y.z", Decimal("12")
    cache.clear()
    state = {"check": {"status": "PENDING", "sms": []}, "buy": None, "calls": []}

    def fake(cfg, path, params=None):
        state["calls"].append(path)
        if path == "/guest/prices":
            if params.get("country"):
                return {params["country"]: {params["product"]: PRICES[params["product"]].get(params["country"], {})}}
            return {params["product"]: PRICES[params["product"]]}
        if path.startswith("/user/buy/hosting/"):
            return {"id": 777, "phone": "+6280000001", "status": "PENDING", "expires": "2030-01-02T00:00:00Z"}
        if path.startswith("/user/buy/"):
            if state["buy"]:
                raise fivesim.FiveSimError(state["buy"])
            return {"id": 555, "phone": "+6281234567", "operator": "virtual21", "status": "PENDING",
                    "expires": "2030-01-01T00:15:00Z"}
        if path.startswith("/user/check/"):
            return state["check"]
        if path.startswith("/user/cancel/"):
            return {"status": "CANCELED"}
        if path == "/guest/countries":
            return {"indonesia": {"iso": {"id": 1}, "prefix": {"+62": 1}}, "tajikistan": {"iso": {"tj": 1}}}
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


def test_flags_and_logos(app, client, config, conn, five):
    assert fivesim.flag(config, "tajikistan") == "🇹🇯" and fivesim.flag(config, "unknownland") == "🌐"
    make_client(conn, balance="5")
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/numbers?service=telegram").text
    assert "wa-logo" in page and "tg-logo" in page and "🇮🇩" in page and "🇹🇯" in page


def test_rent_number(app, client, config, conn, five):
    """Аренда на 1 день: у самого дешёвого оператора, все СМС сохраняются, отменить нельзя, по таймауту — без возврата."""
    from donatix import accounts
    uid = make_client(conn, balance="5")[0]
    vid = fivesim.buy(conn, config, accounts.get_user(conn, uid), "1day", "indonesia")
    assert "/user/buy/hosting/indonesia/virtual4/1day" in five["calls"]
    assert balance(conn, uid) == 50000 - 9000          # 0.80 × 1.12 = 0.896 → вверх до 0.90
    five["check"] = {"status": "RECEIVED", "sms": [{"sender": "Telegram", "text": "code 111", "code": "111"},
                                                    {"sender": "WhatsApp", "text": "code 222", "code": "222"}]}
    v = fivesim.refresh(conn, config, vid)
    import json
    assert [m["code"] for m in json.loads(v["sms_json"])] == ["111", "222"]
    with pytest.raises(fivesim.FiveSimError, match="Аренду отменить нельзя"):
        fivesim.cancel(conn, config, vid, uid)
    five["check"] = {"status": "TIMEOUT", "sms": []}
    fivesim.refresh(conn, config, vid)
    assert balance(conn, uid) == 50000 - 9000          # аренду 5sim не возвращает — и мы нет
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/numbers?service=1day").text
    assert "Аренда номера" in page and "1 день" in page and "🇮🇩" in page


def test_default_markup_is_25():
    from donatix.config import Config
    assert Config.__dataclass_fields__["fivesim_markup"].default == 25


def test_rent_shows_no_refund_warning(app, client, config, conn, five):
    make_client(conn, balance="5")
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/numbers?service=1day").text
    assert "Аренду отменить и вернуть деньги нельзя" in page and "АРЕНДУ ВЕРНУТЬ НЕЛЬЗЯ" in page
    assert "деньги вернутся на баланс" not in page   # на аренде не обещаем возврат
    assert "вернуть деньги нельзя" not in client.get("/panel/numbers?service=telegram").text
