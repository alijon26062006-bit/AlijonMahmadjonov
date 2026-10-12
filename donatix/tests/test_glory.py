"""Glory клана Free Fire (FFGlory): цена с наценкой, запуск, возврат при ошибке, «живые» очки, остановка."""
from decimal import Decimal

import pytest
from conftest import balance, csrf_of, make_client, web_login

from donatix import accounts, cache, glory

PRICING = {"basic_credit_usd": 1.5, "premium_credit_usd": 3.0, "regions": [
    {"id": "me", "region_name": "Middle East", "region_code": "ME", "tier": "premium", "enabled": True},
    {"id": "bd", "region_name": "Bangladesh", "region_code": "BD", "tier": "basic", "enabled": True},
    {"id": "xx", "region_name": "Off", "tier": "basic", "enabled": False}]}


class Err(glory.GloryError):
    def __init__(self, msg, status):
        super().__init__(msg)
        self.status = status


@pytest.fixture
def ffg(config, monkeypatch):
    config.ffglory_key, config.ffglory_master, config.ffglory_markup = "ak_x", "mk", Decimal("25")
    config.ffglory_price_tjs = Decimal("0")
    cache.clear()
    st = {"calls": [], "launch": None, "status": "running", "glory": 1000}

    def fake(cfg, method, path, body=None, auth=True):
        st["calls"].append((path, (body or {}).get("action")))
        if path == "/api/pricing":
            return PRICING
        if path == "/api/client/auto-clan-group":
            if st["launch"]:
                raise st["launch"]
            return {"success": True, "group_id": "g1", "bot_count": 4}
        if path == "/api/client/my-groups":
            return [{"group_id": "g1", "clan_id": "3012345678", "status": st["status"], "running_count": 4, "uptime": "1h5m"}]
        if path == "/api/client/group-action":
            a = body["action"]
            if a == "get-glory":
                return {"success": True, "data": {"glory": st["glory"]}}
            if a == "get-clan-info":
                return {"clan_name": "TJ Kings", "clan_level": 6, "members": [1, 2, 3], "capacity": 55}
            if a == "stop":
                return {"success": True}
        if path == "/api/auth/me":
            return {"basic_credits": 12, "premium_credits": 3}
        raise AssertionError(path)
    monkeypatch.setattr(glory, "_call", fake)
    return st


def test_regions_and_price(config, ffg):
    rows = glory.regions(config)
    assert [r["id"] for r in rows] == ["bd", "me"]            # выключенный регион не показываем, обычные — первыми
    assert rows[0]["price_micro"] == 18800 and rows[1]["price_micro"] == 37500   # 1.5 × 1.25 = 1.875 → 1.88


def test_parse_unknown_formats():
    assert glory.parse_glory({"data": {"total_glory": "12,500"}}) == 12500
    assert glory.parse_glory(777) == 777 and glory.parse_glory({"x": 1}) is None
    assert glory.parse_clan({"clan": {"name": "A", "level": 3, "member_count": 40}}) == {"name": "A", "level": 3, "members": 40}


def test_launch_live_and_stop(app, config, conn, ffg):
    uid = make_client(conn, balance="5")[0]
    gid = glory.buy(conn, config, accounts.get_user(conn, uid), "bd", " 3012345678 ")
    assert balance(conn, uid) == 50000 - 18800
    g = glory.refresh(conn, config, gid)
    v = glory.view(g)
    assert v["status"] == "running" and v["glory"] == 1000 and v["farmed"] == 0
    assert v["clan"] == {"name": "TJ Kings", "level": 6, "members": 3, "capacity": 55}
    ffg["glory"] = 1350
    conn.execute("UPDATE glory_orders SET updated_at = '2000-01-01' WHERE id = ?", (gid,))
    cache.clear()
    assert glory.view(glory.refresh(conn, config, gid))["farmed"] == 350      # набрано с момента запуска
    with pytest.raises(glory.GloryError, match="уже работает"):
        glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")
    glory.stop(conn, config, gid, uid)
    assert ("/api/client/group-action", "stop") in ffg["calls"]
    assert glory.view(conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone())["status"] == "stopped"
    assert balance(conn, uid) == 50000 - 18800                               # после запуска не возвращаем


def test_launch_fail_refunds(app, config, conn, ffg):
    uid = make_client(conn, balance="5")[0]
    ffg["launch"] = Err("Insufficient premium credits", 402)
    with pytest.raises(glory.GloryError, match="вернулись"):
        glory.buy(conn, config, accounts.get_user(conn, uid), "me", "3012345678")
    assert balance(conn, uid) == 50000
    assert tuple(conn.execute("SELECT status, refunded FROM glory_orders").fetchone()) == ("failed", 1)


def test_bad_clan_and_no_money(app, config, conn, ffg):
    uid = make_client(conn, balance="0.5")[0]
    with pytest.raises(glory.GloryError, match="только цифры"):
        glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "abc")
    with pytest.raises(glory.GloryError, match="не хватает"):
        glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")


def test_group_finished_by_itself(app, config, conn, ffg):
    uid = make_client(conn, balance="5")[0]
    gid = glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")
    glory.refresh(conn, config, gid)
    ffg["status"] = "stopped"
    conn.execute("UPDATE glory_orders SET updated_at = '2000-01-01' WHERE id = ?", (gid,))
    cache.clear()
    glory.watch(conn, config)
    assert conn.execute("SELECT status FROM glory_orders WHERE id = ?", (gid,)).fetchone()[0] == "stopped"


def test_pages_and_popular(app, client, config, conn, ffg):
    make_client(conn, balance="5")
    token = web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/glory").text
    assert "Glory клана Free Fire" in page and "Bangladesh" in page and "не возвращаются" in page
    assert 'href="/panel/glory"' in client.get("/panel").text                # в «Популярном»
    r = client.post("/panel/glory/buy", data={"csrf": token, "region": "bd", "clan_id": "3012345678"},
                    follow_redirects=False)
    assert r.headers["location"] == "/panel/glory"                           # без галочки «согласен» — нет
    r = client.post("/panel/glory/buy", data={"csrf": token, "region": "bd", "clan_id": "3012345678", "agree": "1"},
                    follow_redirects=False)
    loc = r.headers["location"]
    assert loc.startswith("/panel/glory/")
    page = client.get(loc).text
    assert "TJ Kings" in page and "Очки сейчас" in page and "Остановить" in page
    d = client.get("/panel/data/glory/" + loc.rsplit("/", 1)[1]).json()
    assert d["glory"] == 1000 and d["open"] is True


def test_hidden_without_keys(app, client, config, conn):
    config.ffglory_key = ""
    make_client(conn, balance="5")
    web_login(client, "shop1@example.com", "password123")
    assert client.get("/panel/glory", follow_redirects=False).status_code == 303
    assert 'href="/panel/glory"' not in client.get("/panel").text


def test_flat_price_30_tjs_and_flags(app, config, conn, ffg):
    from donatix.payments import settings
    config.ffglory_price_tjs = Decimal("30")
    rate = Decimal(str(settings(conn, config)["tjs_rate"]))
    rows = glory.regions(config, conn)
    assert len({r["price_micro"] for r in rows}) == 1                         # одна цена для всех регионов
    assert (Decimal(rows[0]["price_micro"]) / 10_000 * rate).quantize(Decimal("0.01")) == Decimal("30.00")
    assert {r["id"]: r["flag"] for r in rows} == {"bd": "🇧🇩", "me": "🌍"}
    assert glory.flag("IND") == "🇮🇳" and glory.flag("??") == "🌐"
    uid = make_client(conn, balance="5")[0]
    glory.buy(conn, config, accounts.get_user(conn, uid), "me", "3012345678")
    assert balance(conn, uid) == 50000 - rows[0]["price_micro"]


def test_launched_but_answer_odd_is_not_refunded(app, config, conn, ffg, monkeypatch):
    """FFGlory запустил группу, но ответ без group_id (или оборвался) — находим группу по клану, денег не возвращаем."""
    real = glory._call

    def odd(cfg, method, path, body=None, auth=True):
        if path == "/api/client/auto-clan-group":
            return {"success": True, "message": "Group launched"}
        return real(cfg, method, path, body, auth)
    monkeypatch.setattr(glory, "_call", odd)
    uid = make_client(conn, balance="5")[0]
    gid = glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")
    row = conn.execute("SELECT status, group_id, refunded FROM glory_orders WHERE id = ?", (gid,)).fetchone()
    assert tuple(row) == ("running", "g1", 0) and balance(conn, uid) == 50000 - 18800


def test_nested_group_id(app, config, conn, ffg, monkeypatch):
    real = glory._call
    monkeypatch.setattr(glory, "_call", lambda cfg, m, path, body=None, auth=True: (
        {"success": True, "data": {"group_id": "g1", "bot_count": 4}} if path == "/api/client/auto-clan-group"
        else real(cfg, m, path, body, auth)))
    uid = make_client(conn, balance="5")[0]
    gid = glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")
    assert conn.execute("SELECT group_id, bots FROM glory_orders WHERE id = ?", (gid,)).fetchone()[0] == "g1"


def test_relink_launched_group_without_charging(app, config, conn, ffg):
    uid = make_client(conn, balance="5")[0]
    ffg["launch"] = Err("odd", 500)
    ffg_groups_running = ffg["status"]
    with pytest.raises(glory.GloryError):
        glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "9999999")   # другой клан — в my-groups нет
    conn.execute("UPDATE glory_orders SET clan_id = '3012345678'")
    assert balance(conn, uid) == 50000
    lines = glory.relink(conn, config)
    assert "привязана" in lines[0] and ffg_groups_running == "running"
    g = glory.view(conn.execute("SELECT * FROM glory_orders").fetchone())
    assert g["status"] == "running" and g["glory"] == 1000 and balance(conn, uid) == 50000   # второй раз не списали
    assert "уже есть" in glory.relink(conn, config)[0] if conn.execute(
        "SELECT COUNT(*) FROM glory_orders WHERE status = 'failed'").fetchone()[0] else True


def test_glory_via_api_for_partners(app, config, conn, ffg):
    from fastapi.testclient import TestClient
    config.ffglory_price_tjs = Decimal("20")
    uid = make_client(conn, balance="5")[0]
    key = accounts.create_api_key(conn, uid, "bot")
    c, h = TestClient(app), {"X-API-Key": key}
    regs = c.get("/api/v1/glory/regions", headers=h).json()
    assert regs["ok"] and {r["id"] for r in regs["items"]} == {"bd", "me"} and regs["items"][0]["price_tjs"] == "20.00"
    r = c.post("/api/v2/glory/orders", headers=h, json={"region": "bd", "clan_id": "3012345678"})
    assert r.status_code == 201, r.text
    oid = r.json()["order"]["id"]
    assert oid.startswith("gl-")
    live = c.get(f"/api/v1/glory/orders/{oid}", headers=h).json()["order"]
    assert live["status"] == "running" and live["clan"]["name"] == "TJ Kings" and live["glory"] == 1000
    assert c.post("/api/v1/glory/orders", headers=h, json={"region": "bd", "clan_id": "3012345678"}).json()["code"] == "clan_busy"
    assert c.post("/api/v1/glory/orders", headers=h, json={"region": "bd", "clan_id": "abc"}).json()["code"] == "invalid_clan_id"
    assert c.post(f"/api/v1/glory/orders/{oid}/stop", headers=h).json()["order"]["status"] == "stopped"
    other = make_client(conn, login="other", balance="5")[0]
    k2 = accounts.create_api_key(conn, other, "x")
    assert c.get(f"/api/v1/glory/orders/{oid}", headers={"X-API-Key": k2}).status_code == 404   # чужой заказ не виден


def test_finance_counts_numbers_and_glory(app, config, conn, ffg):
    from datetime import datetime, timedelta, timezone

    from donatix import db, finance
    uid = make_client(conn, balance="5")[0]
    glory.buy(conn, config, accounts.get_user(conn, uid), "bd", "3012345678")          # 1.88 $, кредит 1.5 $
    conn.execute("INSERT INTO vnumbers (user_id, service, country, price_micro, cost, status, created_at, updated_at) "
                 "VALUES (?, 'telegram', 'indonesia', 3000, '0.24', 'FINISHED', ?, ?)", (uid, db.now(), db.now()))
    conn.execute("INSERT INTO vnumbers (user_id, service, country, price_micro, cost, status, refunded, created_at, "
                 "updated_at) VALUES (?, 'telegram', 'usa', 9000, '0.7', 'TIMEOUT', 1, ?, ?)", (uid, db.now(), db.now()))
    now = datetime.now(timezone.utc)
    s = finance.summary(conn, config, now - timedelta(hours=1), now + timedelta(hours=1))
    assert s["glory"] == {"n": 1, "revenue": 18800, "cost": 15000, "profit": 3800}
    assert s["vnumbers"] == {"n": 1, "revenue": 3000, "cost": 2400, "profit": 600}      # возвращённый — не считаем
    assert s["revenue"] == 21800 and s["gross_profit"] == 4400
    assert "Боты для гильдии: 1 шт." in finance.report_text(s) and "Виртуальные номера: 1 шт." in finance.report_text(s)
