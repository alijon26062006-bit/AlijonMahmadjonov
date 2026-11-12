"""Пополнение переводом: счета с номером, пересчёт в сомони, чек, просмотр чека админом."""
import base64

from tests.conftest import Api
from tests.test_selling import admin_api

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
ACCOUNTS = [{"name": "Алиф Моби", "number": "0000 1111 2222 3333", "holder": "А. Махмаджонов"},
            {"name": "Душанбе Сити", "number": "+992 900 00 00 00", "holder": ""}]


def setup_accounts(client, **extra):
    boss = admin_api(client)
    r = boss.post("/api/admin/settings", {"payment_accounts": ACCOUNTS, **extra})
    assert r.status_code == 200, r.text
    return boss


def user_api(client):
    client.cookies.clear()
    return Api(client).signup(email="payer@example.com")


def test_accounts_and_rate_shown_to_client(client):
    setup_accounts(client)
    u = user_api(client)
    b = u.get("/api/billing").json()
    assert [a["number"] for a in b["payment_accounts"]] == ["0000 1111 2222 3333", "+992 900 00 00 00"]
    assert b["pay"]["currency"] == "TJS" and b["pay"]["currency_name"] == "сомони"
    assert b["pay"]["rate"]["rate"] == 10.9 and b["pay"]["rate"]["source"] == "auto"


def test_manual_rate_wins(client):
    setup_accounts(client, exchange_rate="11,25")
    u = user_api(client)
    assert u.get("/api/billing").json()["pay"]["rate"] == {"rate": 11.25, "source": "manual", "updated_at": None}


def test_request_with_receipt_and_admin_view(client, hosting):
    boss = setup_accounts(client)
    u = user_api(client)
    assert u.post("/api/billing/requests", {"amount": 20, "method": "Алиф Моби"}).json()["field"] == "receipt"
    bad = u.post("/api/billing/requests", {"amount": 20, "method": "Алиф Моби",
                                           "receipt_data": base64.b64encode(b"<html>not an image").decode()})
    assert bad.status_code == 400 and bad.json()["field"] == "receipt"
    ok = u.post("/api/billing/requests", {"amount": 20, "method": "Алиф Моби", "receipt_data": base64.b64encode(PNG).decode(),
                                          "receipt_name": "чек.png"})
    assert ok.status_code == 200, ok.text
    req = ok.json()["request"]
    assert req["pay_amount"] == 218.0 and req["pay_currency"] == "TJS" and req["receipt"].endswith(".png")
    assert any(m[0] == "telegram_file" and "218" in m[2] for m in hosting.notify.sent)
    # клиент не может смотреть чеки через админку
    assert u.get(f"/api/admin/topups/{req['id']}/receipt").status_code == 403
    client.cookies.clear()
    boss.post("/api/auth/login", {"email": "boss@example.com", "password": "account-pass-1"})
    boss.csrf = boss.get("/api/me").json()["csrf"]
    r = boss.get(f"/api/admin/topups/{req['id']}/receipt")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == PNG
    assert boss.get("/api/admin/topups/999/receipt").status_code == 404


def test_receipt_too_big(client):
    setup_accounts(client)
    u = user_api(client)
    big = base64.b64encode(PNG + b"\x00" * (5 * 1024 * 1024)).decode()
    r = u.post("/api/billing/requests", {"amount": 5, "method": "Алиф Моби", "receipt_data": big})
    assert r.status_code == 400 and "5 МБ" in r.json()["error"]


def test_accounts_validation(client):
    boss = admin_api(client)
    r = boss.post("/api/admin/settings", {"payment_accounts": [{"name": "Алиф", "number": ""}]})
    assert r.status_code == 400
    assert boss.post("/api/admin/settings", {"pay_currency": "сомони"}).status_code == 400


def test_rates_fallback_to_saved(db):
    from app.rates import Rates
    calls = []

    def flaky(base, quote):
        calls.append(1)
        if len(calls) > 1:
            raise ValueError("offline")
        return 10.5
    r = Rates(db, fetch=flaky)
    assert r.get("USD", "TJS")["rate"] == 10.5
    r._mem.clear()
    assert r.get("USD", "TJS") == {"rate": 10.5, "source": "saved", "updated_at": r.get("USD", "TJS")["updated_at"]}
    assert r.get("USD", "USD")["rate"] == 1.0
