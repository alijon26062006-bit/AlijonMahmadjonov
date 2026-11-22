"""Раздел VPS (Hetzner) в Sitora: Hetzner понарошку (httpx.MockTransport), SSH понарошку."""
import json
import logging
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from sitora import db
from sitora.tg import sign_init_data
from sitora.vps import billing, catalog, live, service
from sitora.vps.hetzner import Hetzner, HetznerError
from sitora.vps.store import Vps
from sitora.web import create_app

from conftest import TOKEN

HZ_TOKEN = "test-token"


class FakeHetzner:
    """Hetzner понарошку: каталог, серверы, действия, ошибки по заказу."""

    def __init__(self):
        self.calls = []
        self.fail_create = None          # код ошибки для POST /servers
        self.read_only = False
        self.servers = {}
        self.ssh_keys = []
        self.next_id = 1000
        self.password_resets = 0

    def response(self, status=200, data=None, headers=None):
        return httpx.Response(status, json=data or {}, headers={"RateLimit-Limit": "3600",
                                                                "RateLimit-Remaining": "3500", **(headers or {})})

    def error(self, code, status=400):
        return self.response(status, {"error": {"code": code, "message": code}})

    def handler(self, req: httpx.Request):
        path, method = req.url.path.replace("/v1", "", 1), req.method
        body = json.loads(req.content) if req.content else {}
        self.calls.append((method, path, body, dict(req.url.params)))
        if req.headers.get("authorization") != f"Bearer {HZ_TOKEN}":
            return self.error("unauthorized", 401)
        if method != "GET" and self.read_only:
            return self.error("forbidden", 403)
        if path == "/locations":
            return self.response(200, {"locations": [
                {"id": 1, "name": "fsn1", "city": "Falkenstein", "country": "DE"},
                {"id": 2, "name": "hel1", "city": "Helsinki", "country": "FI"}],
                "meta": {"pagination": {"next_page": None}}})
        if path == "/server_types":
            page = int(req.url.params.get("page", 1))
            if page == 1:   # проверяем пагинацию: два типа на первой странице, один на второй
                items = [
                    {"name": "cx22", "cores": 2, "memory": 4, "disk": 40, "architecture": "x86", "cpu_type": "shared",
                     "deprecation": None,
                     "locations": [{"name": "fsn1", "available": True, "deprecation": None},
                                   {"name": "hel1", "available": False, "deprecation": None}],
                     "prices": [{"location": "fsn1", "price_monthly": {"net": "3.7900000000", "gross": "4.51"},
                                 "price_hourly": {"net": "0.0060000000", "gross": "0.007"},
                                 "included_traffic": 21990232555520},
                                {"location": "hel1", "price_monthly": {"net": "3.7900000000"}}]},
                    {"name": "cx11", "cores": 1, "memory": 2, "disk": 20, "architecture": "x86", "cpu_type": "shared",
                     "deprecation": {"announced": "2024-06-06"},
                     "locations": [{"name": "fsn1", "available": True}],
                     "prices": [{"location": "fsn1", "price_monthly": {"net": "3.29"}}]},
                ]
                return self.response(200, {"server_types": items, "meta": {"pagination": {"next_page": 2}}})
            return self.response(200, {"server_types": [
                {"name": "cax11", "cores": 2, "memory": 4, "disk": 40, "architecture": "arm", "cpu_type": "shared",
                 "deprecation": None, "locations": [{"name": "fsn1", "available": True}],
                 "prices": [{"location": "fsn1", "price_monthly": {"net": "3.29"}, "price_hourly": {"net": "0.0053"}}]}],
                "meta": {"pagination": {"next_page": None}}})
        if path == "/images":
            return self.response(200, {"images": [
                {"name": "ubuntu-24.04", "description": "Ubuntu 24.04", "type": "system", "os_flavor": "ubuntu",
                 "architecture": "x86", "status": "available", "deprecated": None},
                {"name": "ubuntu-24.04", "description": "Ubuntu 24.04", "type": "system", "os_flavor": "ubuntu",
                 "architecture": "arm", "status": "available", "deprecated": None},
                {"name": "debian-10", "description": "Debian 10", "type": "system", "os_flavor": "debian",
                 "architecture": "x86", "status": "available", "deprecated": "2024-07-01"}],
                "meta": {"pagination": {"next_page": None}}})
        if path == "/pricing":
            return self.response(200, {"pricing": {"currency": "EUR", "primary_ips": [
                {"type": "ipv4", "prices": [{"location": "fsn1", "price_monthly": {"net": "0.5000000000"},
                                             "price_hourly": {"net": "0.0008"}}]},
                {"type": "ipv6", "prices": [{"location": "fsn1", "price_monthly": {"net": "0"}}]}]}})
        if path == "/ssh_keys" and method == "GET":
            name = req.url.params.get("name")
            keys = [k for k in self.ssh_keys if not name or k["name"] == name]
            return self.response(200, {"ssh_keys": keys, "meta": {"pagination": {"next_page": None}}})
        if path == "/ssh_keys" and method == "POST":
            if not body.get("name") or not body.get("public_key"):
                return self.error("invalid_input")
            self.ssh_keys.append({"name": body["name"], "public_key": body["public_key"]})
            return self.response(201, {"ssh_key": self.ssh_keys[-1]})
        if path == "/servers" and method == "POST":
            if self.fail_create:
                return self.error(self.fail_create, 412)
            self.next_id += 1
            s = {"id": self.next_id, "name": body["name"], "status": "running",
                 "labels": body.get("labels", {}),
                 "public_net": {"ipv4": {"ip": "203.0.113.10"}, "ipv6": {"ip": "2001:db8::/64"}},
                 "outgoing_traffic": 5 * 1024 ** 3, "ingoing_traffic": 1, "included_traffic": 20 * 1024 ** 4}
            self.servers[s["id"]] = s
            return self.response(201, {"server": s, "action": {"id": 1, "status": "running"}, "root_password": None})
        if path == "/servers" and method == "GET":
            return self.response(200, {"servers": list(self.servers.values()), "meta": {"pagination": {"next_page": None}}})
        parts = path.strip("/").split("/")
        if parts[0] == "servers" and len(parts) >= 2:
            sid = int(parts[1])
            if sid not in self.servers:
                return self.error("not_found", 404)
            if method == "DELETE":
                del self.servers[sid]
                return self.response(200, {"action": {"id": 9, "status": "running"}})
            if len(parts) == 2:
                return self.response(200, {"server": self.servers[sid]})
            if parts[2] == "actions":
                act = parts[3]
                if act == "reset_password":
                    self.password_resets += 1
                    return self.response(201, {"root_password": "Temp-Pass-123", "action": {"id": 3}})
                self.servers[sid]["status"] = {"poweroff": "off", "shutdown": "off", "poweron": "running"}.get(act, "running")
                return self.response(201, {"action": {"id": 2, "command": act, "status": "running"}})
            if parts[2] == "metrics":
                return self.response(200, {"metrics": {"time_series": {"cpu": {"values": [[1700000000, "150"]]}}}})
        return self.error("not_found", 404)




class SSH:
    def __init__(self):
        self.calls, self.reject_key = [], False

    def __call__(self, ip, password, key=None, login_password=None):
        from sitora.vps.sshkey import SSHFailed
        self.calls.append((ip, password, key is not None, login_password))
        if key is not None and self.reject_key:
            raise SSHFailed("ключ не подошёл: Authentication failed")


@pytest.fixture
def hz():
    return FakeHetzner()


@pytest.fixture
def ssh():
    return SSH()


@pytest.fixture
def vps(config, bot, hz, ssh):
    config.hetzner_token = HZ_TOKEN
    v = Vps(config, bot, hetzner_transport=httpx.MockTransport(hz.handler),
            http_transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"rates": {"USD": 1.1}})), ssh=ssh)
    v.fast = True
    conn = v.conn()
    db.set_setting(conn, "vps_eur_usd", "1.10")
    conn.close()
    live.hub.__init__()
    return v


@pytest.fixture
def client(config, bot, vps):
    with TestClient(create_app(config, bot, vps=vps, background=False)) as c:
        yield c


def who(uid, balance=0, name="Ali"):
    return {"X-Init-Data": sign_init_data({"id": uid, "first_name": name, "username": f"u{uid}"}, TOKEN)}


def give(client, config, uid, balance):
    client.get("/api/me", headers=who(uid))
    conn = db.connect(config.db_path)
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (balance, uid))
    conn.close()


def wait(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def row(config, sid):
    conn = db.connect(config.db_path)
    r = conn.execute("SELECT * FROM vps_servers WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return r


def balance(config, uid):
    conn = db.connect(config.db_path)
    b = conn.execute("SELECT balance FROM users WHERE id = ?", (uid,)).fetchone()[0]
    conn.close()
    return b


ORDER = {"location": "fsn1", "server_type": "cx22", "image": "ubuntu-24.04", "name": "web-1"}
PRICE = 6237   # (3.79 + 0.50 IPv4) € × 1.10 × 1.20 = 5.6628 $ → 5.67 $ → × 11 с. = 62.37 с.


def test_price_formula_rounds_up():
    from decimal import Decimal
    assert catalog.price_cents(Decimal("3.79"), Decimal("0.5"), Decimal("1.10"), 20) == 567
    assert catalog.to_diram(567, Decimal("11")) == PRICE


def test_catalog_only_available_and_priced_in_somoni(client, hz):
    d = client.get("/api/vps/catalog", headers=who(1)).json()
    assert [l["name"] for l in d["locations"]] == ["fsn1"]          # в hel1 cx22 недоступен
    plans = {p["name"]: p for p in d["locations"][0]["plans"]}
    assert set(plans) == {"cx22", "cax11"}                          # cx11 устарел — не показываем
    assert plans["cx22"]["price"] == PRICE and plans["cx22"]["price_usd"] == 567
    assert all(i["name"] != "debian-10" for i in d["images"])
    assert d["locations"][0]["country_ru"] == "Германия"
    assert any(c[3].get("page") == "2" for c in hz.calls if c[1] == "/server_types")   # пагинация
    client.get("/api/vps/catalog", headers=who(1))
    assert sum(1 for c in hz.calls if c[1] == "/locations") == 1                       # кэш 1 час


def test_me_shows_vps_only_with_token(client, config):
    assert client.get("/api/me", headers=who(1)).json()["vps"] is True
    config.hetzner_token = ""
    assert client.get("/api/me", headers=who(1)).json()["vps"] is False


def test_order_debits_creates_and_sets_password(client, config, hz, ssh):
    give(client, config, 1, 10_000)
    r = client.post("/api/vps/servers", json=ORDER, headers=who(1)).json()
    assert r["ok"] and len(r["password"]) >= 16 and r["balance"] == 10_000 - PRICE
    post = next(c for c in hz.calls if c[0] == "POST" and c[1] == "/servers")[2]
    assert post["labels"]["panel"] == "sitora" and post["ssh_keys"] and "#cloud-config" in post["user_data"]
    assert client.app.state.vps.agent_url == "wss://stars.example.tj/agent"
    assert wait(lambda: row(config, r["id"])["password_state"] == "set")
    assert ssh.calls[0][:3] == ("203.0.113.10", r["password"], True)
    s = row(config, r["id"])
    assert s["state"] == "active" and s["ipv4"] == "203.0.113.10" and s["price"] == PRICE
    assert r["password"] not in json.dumps(dict(s))              # пароль не хранится
    lst = client.get("/api/vps/servers", headers=who(1)).json()["items"]
    assert lst[0]["name"] == "web-1" and lst[0]["status"] == "running"


def test_own_password_and_bad_name(client, config):
    give(client, config, 1, 10_000)
    bad = client.post("/api/vps/servers", json={**ORDER, "name": "Плохое имя"}, headers=who(1))
    assert bad.status_code == 400
    weak = client.post("/api/vps/servers", json={**ORDER, "password": "123"}, headers=who(1))
    assert weak.status_code == 400 and balance(config, 1) == 10_000
    ok = client.post("/api/vps/servers", json={**ORDER, "password": "Very-Strong-Pass-2026"}, headers=who(1)).json()
    assert ok["password"] is None


def test_hetzner_error_refunds_immediately(client, config, hz):
    give(client, config, 1, 10_000)
    hz.fail_create = "resource_limit_exceeded"
    r = client.post("/api/vps/servers", json=ORDER, headers=who(1))
    assert r.status_code == 400 and "вернулись" in r.json()["detail"]
    assert balance(config, 1) == 10_000
    conn = db.connect(config.db_path)
    reasons = [x[0] for x in conn.execute("SELECT reason FROM ledger WHERE user_id = 1 ORDER BY id")]
    assert reasons == ["vps", "vps_refund"]


def test_not_enough_money_no_hetzner_call(client, config, hz):
    give(client, config, 1, PRICE - 1)
    r = client.post("/api/vps/servers", json=ORDER, headers=who(1))
    assert r.status_code == 400 and "Не хватает" in r.json()["detail"]
    assert not any(c[0] == "POST" and c[1] == "/servers" for c in hz.calls)
    assert row(config, 1) is None


def test_new_client_one_server_until_admin_approves(client, config):
    give(client, config, 1, 100_000)
    assert client.post("/api/vps/servers", json=ORDER, headers=who(1)).status_code == 200
    second = client.post("/api/vps/servers", json={**ORDER, "name": "web-2"}, headers=who(1))
    assert second.status_code == 400 and "1 сервер" in second.json()["detail"]
    assert client.post("/api/admin/vps/approve/1", json={"approved": True}, headers=who(1)).status_code == 403
    assert client.post("/api/admin/vps/approve/1", json={"approved": True}, headers=who(999)).status_code == 200
    assert client.post("/api/vps/servers", json={**ORDER, "name": "web-2"}, headers=who(1)).status_code == 200


def test_other_client_cannot_touch_server(client, config):
    give(client, config, 1, 10_000)
    sid = client.post("/api/vps/servers", json=ORDER, headers=who(1)).json()["id"]
    h2 = who(2)
    assert client.get(f"/api/vps/servers/{sid}", headers=h2).status_code == 404
    assert client.post(f"/api/vps/servers/{sid}/action", json={"action": "poweroff"}, headers=h2).status_code == 400
    assert client.post(f"/api/vps/servers/{sid}/delete", json={"confirm": "web-1"}, headers=h2).status_code == 400
    assert client.post(f"/api/vps/servers/{sid}/password", json={}, headers=h2).status_code == 400
    assert client.get(f"/api/vps/servers/{sid}/history", headers=h2).status_code == 404
    assert client.get("/api/vps/servers", headers=h2).json()["items"] == []
    assert client.get("/api/vps/servers", headers={"X-Init-Data": "bad"}).status_code == 401
    assert row(config, sid)["state"] == "active"


def test_actions_and_delete_need_server_name(client, config, hz):
    give(client, config, 1, 10_000)
    sid = client.post("/api/vps/servers", json=ORDER, headers=who(1)).json()["id"]
    h = who(1)
    assert client.post(f"/api/vps/servers/{sid}/action", json={"action": "shutdown"}, headers=h).json()["ok"]
    assert client.post(f"/api/vps/servers/{sid}/action", json={"action": "format"}, headers=h).status_code == 400
    assert client.post(f"/api/vps/servers/{sid}/delete", json={"confirm": "web"}, headers=h).status_code == 400
    assert client.post(f"/api/vps/servers/{sid}/rebuild", json={"image": "ubuntu-24.04", "confirm": ""},
                       headers=h).status_code == 400
    assert client.post(f"/api/vps/servers/{sid}/delete", json={"confirm": "WEB-1"}, headers=h).json()["ok"]
    assert row(config, sid)["state"] == "deleted" and not hz.servers


def test_password_fallback_reset_when_key_rejected(client, config, hz, ssh):
    ssh.reject_key = True
    give(client, config, 1, 10_000)
    sid = client.post("/api/vps/servers", json=ORDER, headers=who(1)).json()["id"]
    assert wait(lambda: row(config, sid)["password_state"] == "set")
    assert hz.password_resets == 1 and ssh.calls[-1][3] == "Temp-Pass-123"


@pytest.mark.anyio
async def test_token_access_read_only_detected(hz):
    h = Hetzner(HZ_TOKEN, "https://api.hetzner.cloud/v1", httpx.MockTransport(hz.handler))
    assert await h.access() == "rw"
    hz.read_only = True
    assert await h.access() == "ro"
    assert await Hetzner("wrong", "https://api.hetzner.cloud/v1", httpx.MockTransport(hz.handler)).access() == "bad"
    assert "токен" in HetznerError("unauthorized").text.lower()


def _order(client, config, uid=1):
    give(client, config, uid, PRICE)
    return client.post("/api/vps/servers", json=ORDER, headers=who(uid)).json()["id"]


@pytest.mark.anyio
async def test_billing_renews_from_balance(config, bot, vps):
    with TestClient(create_app(config, bot, vps=vps, background=False)) as client:
        sid = _order(client, config)
    s = row(config, sid)
    conn = db.connect(config.db_path)
    conn.execute("UPDATE users SET balance = ? WHERE id = 1", (PRICE + 5,))
    conn.close()
    rep = await billing.run_once(vps, s["paid_until"] + 1)
    assert rep["renewed"] == 1 and balance(config, 1) == 5
    assert row(config, sid)["paid_until"] == s["paid_until"] + service.PERIOD


@pytest.mark.anyio
async def test_billing_warns_suspends_deletes_and_resumes(config, bot, vps, hz):
    with TestClient(create_app(config, bot, vps=vps, background=False)) as client:
        sid = _order(client, config)
    s = row(config, sid)
    pu = s["paid_until"]
    assert (await billing.run_once(vps, pu - 2 * 86400))["warned"] == 1          # за 3 дня — предупреждение
    assert (await billing.run_once(vps, pu - 86400))["warned"] == 0              # второй раз не пишем
    await billing.run_once(vps, pu + 10)
    assert row(config, sid)["unpaid_since"] == pu and row(config, sid)["state"] == "active"
    assert (await billing.run_once(vps, pu + 3 * 86400 + 5))["suspended"] == 1   # через 3 дня — выключен
    assert row(config, sid)["state"] == "suspended" and hz.servers[s["hetzner_id"]]["status"] == "off"
    assert (await billing.run_once(vps, pu + 11 * 86400 + 5))["warned"] == 1      # за 3 дня до удаления
    conn = db.connect(config.db_path)
    conn.execute("UPDATE users SET balance = ? WHERE id = 1", (PRICE,))
    conn.close()
    rep = await billing.run_once(vps, pu + 12 * 86400)
    assert rep["resumed"] == 1 and row(config, sid)["state"] == "active"
    assert hz.servers[s["hetzner_id"]]["status"] == "running" and balance(config, 1) == 0


@pytest.mark.anyio
async def test_billing_deletes_after_14_days(config, bot, vps, hz):
    with TestClient(create_app(config, bot, vps=vps, background=False)) as client:
        sid = _order(client, config)
    pu = row(config, sid)["paid_until"]
    await billing.run_once(vps, pu + 1)
    assert (await billing.run_once(vps, pu + 14 * 86400 + 1))["deleted"] == 1
    assert row(config, sid)["state"] == "deleted" and not hz.servers


def test_agent_to_browser_live_and_history(client, config):
    give(client, config, 1, 10_000)
    client.post("/api/vps/servers", json=ORDER, headers=who(1))
    conn = db.connect(config.db_path)
    conn.execute("UPDATE vps_servers SET agent_hash = ? WHERE id = 1", (service.sha("agent-secret"),))
    conn.close()
    with client.websocket_connect("/ws/live") as browser:
        browser.send_text(json.dumps({"init": who(1)["X-Init-Data"], "server": 1}))
        assert json.loads(browser.receive_text())["type"] == "hello"
        with client.websocket_connect("/agent", headers={"Authorization": "Bearer agent-secret"}) as agent:
            agent.send_text(json.dumps({"cpu": 42.5, "ram_used": 1e9, "ram_total": 4e9, "disk_used": 5e9,
                                        "disk_total": 4e10, "load": [0.5, 0.4, 0.3], "top": [{"pid": 1, "name": "nginx", "cpu": 3}]}))
            msg = json.loads(browser.receive_text())
            assert msg["type"] == "sample" and msg["data"]["cpu"] == 42.5 and msg["data"]["top"][0]["name"] == "nginx"
            assert client.get("/api/vps/servers/1", headers=who(1)).json()["live"] is True
        assert json.loads(browser.receive_text())["type"] == "offline"
    hist = client.get("/api/vps/servers/1/history?range=1h", headers=who(1)).json()
    assert hist["points"] and hist["points"][0][1] == 42.5


def test_websockets_reject_strangers(client, config):
    give(client, config, 1, 10_000)
    client.post("/api/vps/servers", json=ORDER, headers=who(1))
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/agent", headers={"Authorization": "Bearer wrong"}) as ws:
            ws.receive_text()
    with client.websocket_connect("/ws/live") as ws:          # чужой клиент — закрываем
        ws.send_text(json.dumps({"init": who(2)["X-Init-Data"], "server": 1}))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_metrics_older_than_8_days_removed(vps):
    conn = vps.conn()
    now = int(time.time())
    conn.execute("INSERT INTO vps_metrics (server_id, ts, cpu) VALUES (1, ?, 1), (1, ?, 2)", (now - 9 * 86400, now - 60))
    live.cleanup(conn)
    assert conn.execute("SELECT COUNT(*) FROM vps_metrics").fetchone()[0] == 1


def test_hetzner_cpu_divided_by_cores(client, config):
    give(client, config, 1, 10_000)
    client.post("/api/vps/servers", json=ORDER, headers=who(1))
    d = client.get("/api/vps/servers/1/history?range=1h", headers=who(1)).json()
    assert d["hetzner_cpu"] == [[1700000000.0, 75.0]]          # 150% на 2 ядра → 75%


def test_admin_overview_and_settings(client, config):
    give(client, config, 1, 10_000)
    client.post("/api/vps/servers", json=ORDER, headers=who(1))
    assert client.get("/api/admin/vps", headers=who(1)).status_code == 403
    d = client.get("/api/admin/vps", headers=who(999)).json()
    assert d["revenue"] == PRICE and d["active"] == 1 and d["cost_usd"] >= 1 and d["markup"] == 20
    assert client.post("/api/admin/vps/settings", json={"markup": "abc"}, headers=who(999)).status_code == 400
    assert client.post("/api/admin/vps/settings", json={"markup": "30", "enabled": False}, headers=who(999)).json()["ok"]
    assert client.get("/api/vps/catalog", headers=who(1)).status_code == 404
    assert client.post("/api/admin/vps/check", headers=who(999)).json()["access"] == "rw"
    assert client.post("/api/admin/vps/servers/1", json={"action": "delete"}, headers=who(999)).json()["ok"]
    assert row(config, 1)["state"] == "deleted"


def test_hetzner_token_never_logged(client, config, caplog):
    caplog.set_level(logging.DEBUG)
    give(client, config, 1, 10_000)
    client.post("/api/vps/servers", json=ORDER, headers=who(1))
    client.get("/api/vps/servers/1", headers=who(1))
    assert HZ_TOKEN not in caplog.text
