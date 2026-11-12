"""Всё, что нужно для продаж: профиль, заявки на оплату, лимиты, цены, готовность, NS, напоминания, документы."""
from tests.test_api import PROFILE, order, topup
from tests.conftest import Api


def admin_api(client):
    a = Api(client)
    client.cookies.clear()
    return a.signup(email="boss@example.com")


def test_profile_validation_and_normalization(api):
    api.signup()
    bad = api.post("/api/profile", {**PROFILE, "country": "Tajikistan"})
    assert bad.status_code == 422 or bad.json()["field"] == "country"
    bad_phone = api.post("/api/profile", {**PROFILE, "phone": "12"})
    assert bad_phone.status_code == 400 and bad_phone.json()["field"] == "phone"
    ok = api.post("/api/profile", {**PROFILE, "phone": "+992 (900) 12-34-56"}).json()
    assert ok["profile"]["phone"] == "992 900123456" and ok["profile"]["country"] == "TJ"


def test_topup_request_approve_and_reject(api, client, hosting):
    api.signup()
    assert api.post("/api/billing/requests", {"amount": 20, "method": "PayPal", "reference": "x"}).status_code == 400
    assert api.post("/api/billing/requests", {"amount": 20, "method": "Алиф", "reference": " "}).status_code == 400
    r1 = api.post("/api/billing/requests", {"amount": 20, "method": "Алиф", "reference": "перевод 14:05"})
    r2 = api.post("/api/billing/requests", {"amount": 5, "method": "Душанбе Сити", "reference": "чек 123"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert any("Заявка на пополнение" in m[2] for m in hosting.notify.sent)
    user_csrf = api.csrf

    boss = admin_api(client)
    assert len(boss.get("/api/admin/topups").json()["requests"]) == 2
    rid1, rid2 = r1.json()["request"]["id"], r2.json()["request"]["id"]
    assert boss.post(f"/api/admin/topups/{rid1}", {"approve": True}).status_code == 200
    assert boss.post(f"/api/admin/topups/{rid1}", {"approve": True}).status_code == 409  # дважды не зачислить
    assert boss.post(f"/api/admin/topups/{rid2}", {"approve": False, "note": "не нашли"}).status_code == 200
    assert any(m[0] == "email" and "Баланс пополнен" in m[2] for m in hosting.notify.sent)

    client.cookies.clear()
    user = Api(client)
    assert user.post("/api/auth/login", {"email": "user@example.com", "password": "account-pass-1"}).status_code == 200
    user.csrf = user.get("/api/me").json()["csrf"]
    bill = user.get("/api/billing").json()
    assert bill["balance"] == 20
    assert [r["status"] for r in bill["requests"]] == ["rejected", "approved"]
    assert user_csrf  # пользователь существовал до входа админа


def test_non_admin_cannot_decide(api):
    api.signup()
    rid = api.post("/api/billing/requests", {"amount": 20, "method": "Алиф", "reference": "x1"}).json()["request"]["id"]
    assert api.post(f"/api/admin/topups/{rid}", {"approve": True}).status_code == 403


def test_new_user_server_limit_and_verify(api, client):
    api.signup()
    topup(api, 100)
    assert order(api, name="one").status_code == 200
    limited = order(api, name="two")
    assert limited.status_code == 403 and "поддержку" in limited.json()["error"]
    uid = api.get("/api/me").json()["id"]
    boss = admin_api(client)
    assert boss.post(f"/api/admin/users/{uid}/verify", {"value": True}).status_code == 200
    client.cookies.clear()
    api.post("/api/auth/login", {"email": "user@example.com", "password": "account-pass-1"})
    api.csrf = api.get("/api/me").json()["csrf"]
    assert api.get("/api/me").json()["verified"] is True
    assert order(api, name="two").status_code == 200


def test_admin_catalog_edit(api, client, hosting):
    boss = admin_api(client)
    cat = boss.get("/api/admin/catalog").json()
    plans = [{**p, "price_month": 9.5 if p["id"] == "start" else p["price_month"], "enabled": p["id"] != "ultra"} for p in cat["plans"]]
    tlds = [{"zone": "com", "price_year": 11}, {"zone": "tj", "price_year": 30}]
    r = boss.post("/api/admin/catalog", {"plans": plans, "tlds": tlds})
    assert r.status_code == 200, r.text
    public = boss.get("/api/catalog").json()
    assert [p["id"] for p in public["plans"]] == ["start", "base", "pro"]
    assert public["plans"][0]["price_month"] == 9.5
    assert [t["zone"] for t in public["tlds"]] == ["com", "tj"]
    # отключённый тариф нельзя заказать
    topup(boss, 100)
    assert order(boss, plan="ultra").status_code == 400
    bad = boss.post("/api/admin/catalog", {"plans": plans, "tlds": [{"zone": "c om", "price_year": 1}]})
    assert bad.status_code == 400
    # переживает перезапуск: новый Hosting читает цены из базы
    from app.services import Hosting
    from app.catalog import Catalog
    again = Hosting(hosting.s, hosting.db, Catalog.load(), hosting.p)
    assert again.catalog.plan("start")["price_month"] == 9.5


def test_readiness_in_demo(client):
    boss = admin_api(client)
    data = boss.get("/api/admin/readiness").json()
    keys = {c["key"]: c for c in data["checks"]}
    assert data["ready"] is False
    assert keys["vps"]["ok"] is False and "Демо" in keys["vps"]["detail"]
    assert keys["payments"]["ok"] is False and "DEMO_PAYMENTS" in keys["payments"]["detail"]


def test_registered_domain_nameservers(api, providers):
    api.signup()
    topup(api, 50)
    api.post("/api/profile", PROFILE)
    r = api.post("/api/domains", {"domain": "fresh-domain-abc.com", "purchase": True})
    if r.status_code == 409:
        r = api.post("/api/domains", {"domain": "fresh-domain-xyz.com", "purchase": True})
    d = r.json()["domain"]
    did = d["id"]
    assert providers.registrar.nameservers[d["name"]] == d["default_nameservers"]
    assert api.post(f"/api/domains/{did}/nameservers", {"nameservers": ["ns1.only.com"]}).status_code == 400
    ok = api.post(f"/api/domains/{did}/nameservers", {"nameservers": ["Ana.NS.Cloudflare.com.", "bob.ns.cloudflare.com"]})
    assert ok.status_code == 200 and ok.json()["domain"]["custom_ns"] is True
    assert providers.registrar.nameservers[d["name"]] == ["ana.ns.cloudflare.com", "bob.ns.cloudflare.com"]
    back = api.post(f"/api/domains/{did}/nameservers", {"nameservers": None}).json()["domain"]
    assert back["custom_ns"] is False and back["nameservers"] == back["default_nameservers"]
    ext = api.post("/api/domains", {"domain": "external-one.org"}).json()["domain"]
    assert api.post(f"/api/domains/{ext['id']}/nameservers", {"nameservers": None}).status_code == 400


def test_reminders_sent_once(api, hosting, db):
    api.signup()
    topup(api, 7.90)
    sid = order(api).json()["server"]["id"]
    db.run("UPDATE servers SET paid_until = strftime('%s','now') + 2*86400 WHERE id = ?", (sid,))
    before = len([m for m in hosting.notify.sent if m[0] == "email"])
    assert hosting.run_billing()["reminders"] == 1
    assert hosting.run_billing()["reminders"] == 0
    mails = [m for m in hosting.notify.sent if m[0] == "email"][before:]
    assert len(mails) == 1 and "Пополните баланс" in mails[0][2]


def test_legal_pages(client):
    for doc in ("offer", "privacy", "rules"):
        r = client.get(f"/legal/{doc}")
        assert r.status_code == 200 and "<h2>" in r.text
    assert "COMPANY_NAME" in client.get("/legal/offer").text  # подсказка, если реквизиты не заданы
    assert client.get("/legal/nope").status_code == 404


def test_config_exposes_payments_and_support(client):
    cfg = client.get("/api/config").json()
    assert cfg["payment_methods"] == ["Алиф", "Душанбе Сити"] and "support" in cfg
