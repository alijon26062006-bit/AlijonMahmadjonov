"""ИИ читает чек: тот же перевод второй раз не пройдёт, новый — уходит админу с данными чека."""
import json

import httpx
from conftest import RECEIPT_PNG, web_login
from fastapi.testclient import TestClient

from donatix import accounts, receipt_ai

SEEN = {"is_receipt": True, "bank": "Алиф", "amount": 545, "currency": "TJS", "datetime": "2026-10-01 14:32",
        "txn_id": "AB-1234567", "recipient": "+992 90 000 00 00", "status": "success"}


def _client(app, config, conn, n):
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00"}
    accounts.create_user(conn, email=f"r{n}@example.com", login=f"rcpt{n}", password="password123", status="active")
    c = TestClient(app)
    return c, web_login(c, f"r{n}@example.com", "password123")


def _send(c, token, body):
    return c.post("/panel/balance", data={"csrf": token, "method": "alif", "amount": "50"},
                  files={"receipt": ("chek.png", body, "image/png")})


def test_same_transfer_cannot_be_used_twice(app, config, conn, monkeypatch):
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    monkeypatch.setattr(receipt_ai, "read", lambda cfg, data, ext: receipt_ai.clean(SEEN))
    a, ta = _client(app, config, conn, 1)
    assert "Заявка #1 создана" in _send(a, ta, RECEIPT_PNG).text
    row = conn.execute("SELECT receipt_txn, receipt_fp, receipt_ai FROM payments WHERE id = 1").fetchone()
    assert row["receipt_txn"] == "AB1234567" and row["receipt_fp"] and json.loads(row["receipt_ai"])["bank"] == "Алиф"
    b, tb = _client(app, config, conn, 2)
    r = _send(b, tb, RECEIPT_PNG + b"other-screenshot")                 # другой файл, тот же перевод
    assert "Чек не прошёл проверку" in r.text and "заявка" not in r.text.split("Чек не прошёл")[1][:80]
    assert conn.execute("SELECT COUNT(*) FROM payments WHERE receipt_file IS NOT NULL").fetchone()[0] == 1


def test_same_amount_time_bank_without_number_is_caught(app, config, conn, monkeypatch):
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    no_number = {**SEEN, "txn_id": ""}
    monkeypatch.setattr(receipt_ai, "read", lambda cfg, data, ext: receipt_ai.clean(no_number))
    a, ta = _client(app, config, conn, 1)
    _send(a, ta, RECEIPT_PNG)
    b, tb = _client(app, config, conn, 2)
    assert "Чек не прошёл проверку" in _send(b, tb, RECEIPT_PNG + b"x").text


def test_new_receipt_goes_to_admin_with_what_ai_read(app, config, conn, monkeypatch):
    captions = []
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda cfg, caption, *a, **k: captions.append(caption))
    config.openai_api_key = "sk-test"
    config.alert_telegram_chat_id = "777"
    monkeypatch.setattr(receipt_ai, "read", lambda cfg, data, ext: receipt_ai.clean(SEEN))
    a, ta = _client(app, config, conn, 1)
    assert "Заявка #1 создана" in _send(a, ta, RECEIPT_PNG).text
    assert captions and "🤖 Чек: Алиф · 545 TJS · 2026-10-01 14:32 · № AB-1234567" in captions[-1]
    admin = TestClient(app)
    web_login(admin, "admin@example.com", "adminpass123")
    assert "🤖 Чек: Алиф" in admin.get("/admin/payments?status=pending").text


def test_amount_check_and_reading_via_openai():
    assert receipt_ai.amount_matches(receipt_ai.clean(SEEN), "545", "TJS") is True
    assert receipt_ai.amount_matches(receipt_ai.clean(SEEN), "600", "TJS") is False
    assert "НЕ совпадает" in receipt_ai.summary(receipt_ai.clean(SEEN), "600", "TJS")
    assert receipt_ai.txn_key({"txn_id": "12"}) == ""                       # слишком короткий — не надёжен

    seen_body = {}

    def handler(request):
        seen_body.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(SEEN)}}]})

    from donatix.config import Config
    cfg = Config(secret_key="x", db_path="x", openai_api_key="sk-test")
    got = receipt_ai.read(cfg, RECEIPT_PNG, "png", transport=httpx.MockTransport(handler))
    assert got["txn_id"] == "AB-1234567" and got["amount"] == 545.0
    url = seen_body["messages"][0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert receipt_ai.read(cfg, b"%PDF-1.4", "pdf") is None                 # PDF не читаем — проверит админ
    assert receipt_ai.read(Config(secret_key="x", db_path="x"), RECEIPT_PNG, "png") is None   # без ключа


def test_client_page_tells_nothing_about_how_receipts_are_checked(app, config, conn):
    a, _ = _client(app, config, conn, 1)
    page = a.get("/panel/balance").text
    assert "Проверяем чек" in page
    for secret in ("ИИ", "в базе", "номер операции", "Читаем чек", "OpenAI", "ChatGPT"):
        assert secret not in page, secret
