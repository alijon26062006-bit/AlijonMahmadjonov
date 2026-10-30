"""SmartPay: инвойс и сразу страница оплаты со всеми банками, webhook — только с токеном и подписью, точная сумма, одно зачисление."""

import pytest
from conftest import balance, csrf_of, web_login
from fastapi.testclient import TestClient

from donatix import accounts, payments, smartpay

TOKEN = "a" * 64
SECRET = "s3cr3t-key"


@pytest.fixture
def sp(config, conn, monkeypatch):
    config.smartpay_key, config.smartpay_mode = "test-key", "sandbox"
    config.smartpay_hook_token, config.smartpay_hook_secret = TOKEN, SECRET
    payments.save_methods(conn, [{"code": "sp", "title": "SmartPay", "currency": "TJS", "details": "",
                                  "enabled": True, "auto": "smartpay"}])
    calls = []

    def fake_call(cfg, method, path, body=None):
        calls.append((method, path, body))
        if path == "/health":
            return {"merchant_unit_uuid": "m-uuid-1"}
        if path == "/invoices":
            if body["amount"] < 2:
                raise smartpay.SmartPayError("Минимальная сумма инвойса должна быть 2 сомони")
            return {"result": 200, "message": "Инвойс создан", "invoice_uuid": "inv-" + body["order_id"],
                    "order_id": body["order_id"], "smartpay_id": "003000000125",
                    "payment_link": f"https://smartpay.tj/invoice/{body['order_id']}"}
        raise AssertionError(path)

    monkeypatch.setattr(smartpay, "_call", fake_call)
    config.calls = calls
    return config


def _client(app, conn):
    uid = accounts.create_user(conn, email="sp@example.com", login="spuser", password="password123", status="active")
    c = TestClient(app)
    return uid, c, web_login(c, "sp@example.com", "password123")


def _pay(c, token, tjs="100"):
    return c.post("/panel/balance", data={"csrf": token, "method": "sp", "amount_tjs": tjs}, follow_redirects=False)


def _hook(payment_id, amount_diram, **over):
    body = {"payment_date": "2026-03-05T03:31:51.879779", "amount": amount_diram,
            "order_id": f"dx{payment_id}", "bank_id": 8, "invoice_number": "001-000042",
            "invoice_uuid": f"inv-dx{payment_id}", "payment_id": 78901, "bank": "Алиф Банк"}
    body.update(over)
    body["signature"] = smartpay.signature(SECRET, body)
    return body


def test_amount_opens_smartpay_page_with_all_banks(app, conn, sp):
    uid, c, token = _client(app, conn)
    r = _pay(c, token)
    p = conn.execute("SELECT * FROM payments").fetchone()
    link = f"https://smartpay.tj/invoice/dx{p['id']}"
    assert p["auto_kind"] == "smartpay" and p["pay_url"] == link
    assert r.status_code == 303 and r.headers["location"] == link       # сразу страница SmartPay — там все банки
    body = next(b for m, path, b in sp.calls if path == "/invoices")
    assert body["order_id"] == f"dx{p['id']}" and body["amount"] == 100.0 and body["lifetime"] == 1800
    assert "deeplink_bank_id" not in body
    assert body["return_url"].endswith(f"/panel/balance/{p['id']}/pay")
    page = c.get(f"/panel/balance/{p['id']}/pay").text                  # вернулся с SmartPay — кнопка ещё раз
    assert link in page and "Оплатить" in page


def test_webhook_credits_once_only_with_token_and_signature(app, conn, sp):
    uid, c, token = _client(app, conn)
    _pay(c, token)
    p = conn.execute("SELECT * FROM payments").fetchone()
    hook = TestClient(app)
    before = balance(conn, uid)
    # чужой токен — не зачисляется
    assert hook.post("/pay/smartpay/webhook", json=_hook(p["id"], 10000), headers={"X-Api-Token": "b" * 64}).status_code == 403
    # верный токен, подделанная подпись — не зачисляется
    forged = _hook(p["id"], 10000)
    forged["amount"] = 999999
    assert hook.post("/pay/smartpay/webhook", json=forged, headers={"X-Api-Token": TOKEN}).status_code == 403
    assert balance(conn, uid) == before
    # не та сумма — не зачисляется
    r = hook.post("/pay/smartpay/webhook", json=_hook(p["id"], 9900), headers={"X-Api-Token": TOKEN})
    assert r.json()["status"] == "amount_mismatch" and balance(conn, uid) == before
    # всё верно — зачислено
    r = hook.post("/pay/smartpay/webhook", json=_hook(p["id"], 10000), headers={"X-Api-Token": TOKEN})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    after = balance(conn, uid)
    assert after == before + p["amount_micro"]
    row = conn.execute("SELECT status, ext_id FROM payments WHERE id = ?", (p["id"],)).fetchone()
    assert row["status"] == "paid" and row["ext_id"] == "sp:78901"
    # повтор того же webhook — второй раз не зачисляется
    r = hook.post("/pay/smartpay/webhook", json=_hook(p["id"], 10000), headers={"X-Api-Token": TOKEN})
    assert r.status_code == 200 and balance(conn, uid) == after


def test_signature_date_format_and_no_hook_settings(sp):
    payload = _hook(5, 10000)
    line_date = smartpay._sign_date(payload["payment_date"])
    assert line_date == "2026-03-05 03:31:51"                       # без «T» и микросекунд
    assert smartpay.verify(sp, TOKEN, payload)
    sp.smartpay_hook_secret = ""
    assert not smartpay.verify(sp, TOKEN, payload)                    # не настроено — не верим никому


def test_min_amount_and_expire(app, conn, sp):
    uid, c, token = _client(app, conn)
    _pay(c, token, "50")
    pid = conn.execute("SELECT id FROM payments WHERE status = 'pending'").fetchone()[0]
    conn.execute("UPDATE payments SET pay_amount = '1.50' WHERE id = ?", (pid,))
    with pytest.raises(smartpay.SmartPayError, match="от 2"):
        smartpay.create(conn, sp, pid)                                 # меньше 2 сомони SmartPay не берёт
    conn.execute("UPDATE payments SET created_at = '2020-01-01T00:00:00.000Z' WHERE id = ?", (pid,))
    assert smartpay.expire(conn) == 1                                  # 30 минут прошли — заявка закрыта
    assert conn.execute("SELECT admin_note FROM payments WHERE id = ?", (pid,)).fetchone()[0] == smartpay.EXPIRED_NOTE


def test_admin_check_button(app, conn, sp):
    c = TestClient(app)
    token = web_login(c, "admin@example.com", "adminpass123")
    page = c.get("/admin/pay-settings").text
    assert "SmartPay — оплата из любого банка" in page and "/pay/smartpay/webhook" in page
    r = c.post("/admin/pay-settings/smartpay-check", data={"csrf": csrf_of(page)})
    assert "ключ работает, мерчант m-uuid-1" in r.text
    assert token
