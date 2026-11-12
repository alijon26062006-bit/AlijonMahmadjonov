"""Сквозные сценарии через HTTP API в демо-режиме."""

ROOT_PW = "Str0ng!Root#Pass"


def topup(api, amount=100):
    assert api.post("/api/billing/topup", {"amount": amount}).status_code == 200


def order(api, **kw):
    body = {"plan": "start", "location": "fsn1", "image": "ubuntu-24.04", "name": "web-01", **kw}
    return api.post("/api/servers", body)


def test_auth_flow_and_csrf(api, client):
    api.signup()
    me = api.get("/api/me").json()
    assert me["email"] == "user@example.com" and me["balance"] == 0 and not me["is_admin"]
    # Без заголовка X-Requested-With изменения отклоняются
    assert client.post("/api/auth/logout").status_code == 403
    # Без CSRF-токена сессии — тоже
    r = client.post("/api/billing/topup", json={"amount": 5}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 403
    assert api.post("/api/auth/logout").status_code == 200
    assert api.get("/api/me").status_code == 401


def test_login_wrong_password_and_rate_limit(api):
    api.signup()
    api.post("/api/auth/logout")
    for _ in range(8):
        assert api.post("/api/auth/login", {"email": "user@example.com", "password": "nope-nope-1"}).status_code == 401
    assert api.post("/api/auth/login", {"email": "user@example.com", "password": "account-pass-1"}).status_code == 429


def test_admin_email_gets_admin(api):
    api.signup(email="boss@example.com")
    assert api.get("/api/me").json()["is_admin"]
    assert api.get("/api/admin/overview").status_code == 200


def test_order_requires_balance_then_succeeds(api):
    api.signup()
    r = order(api)
    assert r.status_code == 402
    topup(api, 20)
    r = order(api)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["root_password"]  # пароль не задан — показываем сгенерированный один раз
    assert data["server"]["plan"]["id"] == "start"
    bill = api.get("/api/billing").json()
    assert bill["balance"] == 20 - 7.90
    # имя уникально у клиента
    assert order(api).status_code == 400


def test_order_with_custom_password_applies_it(api):
    api.signup()
    topup(api)
    r = order(api, root_password=ROOT_PW)
    assert r.status_code == 200
    assert r.json()["root_password"] is None
    sid = r.json()["server"]["id"]
    assert api.get(f"/api/servers/{sid}").json()["server"]["password_state"] == "applied"


def test_order_rejects_weak_password_without_charging(api):
    api.signup()
    topup(api, 20)
    r = order(api, root_password="weak")
    assert r.status_code == 400 and r.json()["field"] == "root_password"
    assert api.get("/api/billing").json()["balance"] == 20


def test_root_password_change_needs_account_password(api):
    api.signup()
    topup(api)
    sid = order(api).json()["server"]["id"]
    api.get(f"/api/servers/{sid}")  # демо-сервер уже загрузился
    bad = api.post(f"/api/servers/{sid}/password", {"mode": "custom", "password": ROOT_PW, "account_password": "wrong"})
    assert bad.status_code == 403
    weak = api.post(f"/api/servers/{sid}/password", {"mode": "custom", "password": "short", "account_password": "account-pass-1"})
    assert weak.status_code == 400
    ok = api.post(f"/api/servers/{sid}/password", {"mode": "custom", "password": ROOT_PW, "account_password": "account-pass-1"})
    assert ok.status_code == 200 and ok.json() == {"mode": "custom"}
    gen = api.post(f"/api/servers/{sid}/password", {"mode": "generate", "account_password": "account-pass-1"})
    assert gen.status_code == 200 and gen.json()["mode"] == "generated" and len(gen.json()["password"]) >= 12


def test_power_and_metrics(api):
    api.signup()
    topup(api)
    sid = order(api).json()["server"]["id"]
    r = api.post(f"/api/servers/{sid}/power", {"action": "reboot"})
    assert r.status_code == 200 and r.json()["server"]["status"] == "rebooting"
    m = api.get(f"/api/servers/{sid}/metrics?range=1h").json()
    assert {"cpu", "net_bps_in", "net_bps_out", "mem"} <= set(m["series"])
    assert len(m["series"]["cpu"]) >= 50
    assert api.get(f"/api/servers/{sid}/metrics?range=1y").status_code == 400


def test_foreign_server_is_hidden(api, client):
    api.signup()
    topup(api)
    sid = order(api).json()["server"]["id"]
    from tests.conftest import Api
    other = Api(client)
    client.cookies.clear()
    other.signup(email="other@example.com")
    assert other.get(f"/api/servers/{sid}").status_code == 404
    assert other.post(f"/api/servers/{sid}/power", {"action": "stop"}).status_code == 404


def test_agent_report(api, hosting, db):
    api.signup()
    topup(api)
    sid = order(api).json()["server"]["id"]
    import secrets
    from app.security import sha256
    token = secrets.token_urlsafe(16)
    db.run("UPDATE servers SET agent_token_hash = ? WHERE id = ?", (sha256(token), sid))
    payload = {"server_id": sid, "mem_used": 2 * 2**30, "mem_total": 4 * 2**30, "disk_used": 10 * 2**30,
               "disk_total": 40 * 2**30, "load1": 0.42, "procs": [{"name": "nginx", "cpu": 3.2, "mem": 50_000_000}]}
    bad = api.c.post("/api/agent/report", json=payload, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    ok = api.c.post("/api/agent/report", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    m = api.get(f"/api/servers/{sid}/metrics?range=1h").json()
    assert m["agent"]["procs"][0]["name"] == "nginx"
    assert m["series"]["mem"][-1][1] == 50.0
    assert api.get(f"/api/servers/{sid}").json()["server"]["agent"] is True


def test_domains_and_dns(api, providers):
    api.signup()
    r = api.get("/api/domains/check?name=my-shop")
    assert r.status_code == 200 and len(r.json()["results"]) == 6
    # Существующий домен добавляется бесплатно
    d = api.post("/api/domains", {"domain": "https://www.Example.org/", "purchase": False}).json()["domain"]
    assert d["name"] == "example.org" and d["kind"] == "external"
    did = d["id"]
    assert api.post("/api/domains", {"domain": "example.org"}).status_code == 409

    ok = api.post(f"/api/domains/{did}/records", {"type": "A", "name": "@", "value": "203.0.113.24", "ttl": 3600})
    assert ok.status_code == 200
    assert providers.dns.zones["example.org"][("@", "A")]["values"] == ["203.0.113.24"]
    api.post(f"/api/domains/{did}/records", {"type": "A", "name": "@", "value": "203.0.113.25", "ttl": 300})
    assert providers.dns.zones["example.org"][("@", "A")] == {"ttl": 300, "values": ["203.0.113.24", "203.0.113.25"]}

    bad_ip = api.post(f"/api/domains/{did}/records", {"type": "A", "name": "www", "value": "999.1.1.1", "ttl": 3600})
    assert bad_ip.status_code == 400 and bad_ip.json()["field"] == "value"
    cname_conflict = api.post(f"/api/domains/{did}/records", {"type": "CNAME", "name": "@", "value": "x.com", "ttl": 3600})
    assert cname_conflict.status_code == 400  # CNAME на корень запрещён
    api.post(f"/api/domains/{did}/records", {"type": "CNAME", "name": "www", "value": "example.org", "ttl": 3600})
    clash = api.post(f"/api/domains/{did}/records", {"type": "A", "name": "www", "value": "203.0.113.1", "ttl": 3600})
    assert clash.status_code == 409
    mx = api.post(f"/api/domains/{did}/records", {"type": "MX", "name": "@", "value": "10 Mail.Example.org.", "ttl": 3600})
    assert mx.json()["record"]["value"] == "10 mail.example.org"

    recs = api.get(f"/api/domains/{did}").json()["records"]
    rid = next(r["id"] for r in recs if r["value"] == "203.0.113.24")
    assert api.delete(f"/api/domains/{did}/records/{rid}").status_code == 200
    assert providers.dns.zones["example.org"][("@", "A")]["values"] == ["203.0.113.25"]


def test_register_domain_charges(api):
    api.signup()
    topup(api, 50)
    r = api.post("/api/domains", {"domain": "brand-new-name-xyz.com", "purchase": True})
    if r.status_code == 409:  # детерминированная «занятость» демо-регистратора
        r = api.post("/api/domains", {"domain": "brand-new-name-abc.com", "purchase": True})
    assert r.status_code == 200, r.text
    assert r.json()["domain"]["kind"] == "registered" and r.json()["domain"]["expires_at"]
    assert api.get("/api/billing").json()["balance"] == round(50 - 12.99, 2)


def test_billing_suspends_and_resumes(api, hosting, db):
    api.signup()
    topup(api, 7.90)
    sid = order(api).json()["server"]["id"]
    # Оплата закончилась 4 дня назад, денег нет → сервер выключается
    db.run("UPDATE servers SET paid_until = strftime('%s','now') - 4*86400 WHERE id = ?", (sid,))
    stats = hosting.run_billing()
    assert stats["suspended"] == 1
    assert api.get(f"/api/servers/{sid}").json()["server"]["suspended"] is True
    assert api.post(f"/api/servers/{sid}/power", {"action": "start"}).status_code == 402
    # Пополнили — следующий проход продлевает и включает
    topup(api, 10)
    stats = hosting.run_billing()
    assert stats["renewed"] == 1 and stats["resumed"] == 1
    assert api.get(f"/api/servers/{sid}").json()["server"]["suspended"] is False


def test_pages_and_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert client.get("/app").status_code == 200
    assert client.get("/api/catalog").json()["plans"][0]["id"] == "start"
