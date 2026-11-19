import json
import os
import threading
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as dbmod
from app.main import create_app
from app.models import LedgerEntry, Order, User
from app.orders_service import sync_pending
from tests.conftest import register

OFFERS = {"ok": True, "kind": "topup", "category_id": "pubg", "name": "PUBG Mobile",
          "offers": [{"offer_id": "60uc", "name": "60 UC", "price_usd": "0.9077"},
                     {"offer_id": "big", "name": "8100 UC", "price_usd": "300.0000"}],
          "fields": [{"key": "player_id", "label": "Player ID", "type": "text"},
                     {"key": "server", "label": "Server", "type": "select", "options": [{"value": "eu"}, {"value": "asia"}]}]}
FIELDS = {"player_id": " 5123456789 ", "server": "eu"}


def setup_user(client, amount="5"):
    """Admin credits a buyer; returns buyer id. Leaves the buyer logged in."""
    register(client, email="boss@example.com", username="boss")
    client.cookies.clear()
    uid = register(client).json()["id"]
    buyer_cookie = client.cookies.get("session")
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "boss@example.com", "password": "password123"})
    assert client.post(f"/api/admin/users/{uid}/balance", json={"amount": amount, "note": "test credit"}).status_code == 200
    client.cookies.clear()
    client.cookies.set("session", buyer_cookie)
    return uid


def as_admin(client):
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "boss@example.com", "password": "password123"})


def balance(client):
    return client.get("/api/balance").json()["balance"]


_SESSIONS = []


def db():
    """A fresh DB session for checks; closed automatically after each test."""
    s = next(dbmod.get_db())
    _SESSIONS.append(s)
    return s


@pytest.fixture(autouse=True)
def _close_sessions(engine):
    yield
    while _SESSIONS:
        _SESSIONS.pop().close()


def test_topup_success_debits_and_uses_idempotency(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    route = mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "ord-77", "status": "processing"}})
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS,
                                               "expected_price": "1.00"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "processing" and body["price"] == "1.00" and "cost" not in body
    assert balance(client) == "4.0000"
    req = route.calls.last.request
    assert req.headers["Idempotency-Key"] == body["id"]
    sent = json.loads(req.content)
    assert sent == {"category_id": "pubg", "offer_id": "60uc", "fields": {"player_id": "5123456789", "server": "eu"}}
    # supplier finishes the order
    mock.get("/orders/ord-77").respond(json={"ok": True, "order": {"id": "ord-77", "status": "completed"}})
    s = db()
    assert sync_pending(s) == 1
    assert client.get(f"/api/orders/{body['id']}").json()["status"] == "completed"
    assert balance(client) == "4.0000"


def test_insufficient_funds_no_supplier_call(client, mock):
    setup_user(client, amount="0.50")
    mock.get("/topups/offers").respond(json=OFFERS)
    route = mock.post("/topups/order")
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS})
    assert r.status_code == 402
    assert route.call_count == 0 and balance(client) == "0.5000"
    assert client.get("/api/orders").json()["total"] == 0


def test_supplier_rejects_refunds_immediately(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(status_code=400, json={"ok": False, "error": "bad player", "code": "invalid_fields"})
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS})
    assert r.status_code == 201 and r.json()["status"] == "refunded"
    assert balance(client) == "5.0000"
    kinds = [(i["kind"], i["reason"]) for i in client.get("/api/balance").json()["items"]]
    assert kinds[:2] == [("credit", "refund"), ("debit", "order")]


def test_timeout_then_safe_retry_with_same_key(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    route = mock.post("/topups/order")
    route.mock(side_effect=httpx.ReadTimeout("slow"))
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS})
    oid = r.json()["id"]
    assert r.json()["status"] == "processing" and balance(client) == "4.0000"
    route.mock(side_effect=None)
    route.respond(json={"ok": True, "order": {"id": "ord-9", "status": "processing"}})
    sync_pending(db())
    assert route.call_count == 2
    assert {c.request.headers["Idempotency-Key"] for c in route.calls} == {oid}
    s = db()
    o = s.scalar(select(Order).where(Order.public_id == oid))
    assert o.supplier_order_id == "ord-9" and o.needs_check is False


def test_supplier_refund_is_credited_once(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "ord-5", "status": "processing"}})
    oid = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS}).json()["id"]
    mock.get("/orders/ord-5").respond(json={"ok": True, "order": {"id": "ord-5", "status": "refunded"}})
    sync_pending(db())
    sync_pending(db())
    client.get(f"/api/orders/{oid}")
    assert balance(client) == "5.0000"
    s = db()
    refunds = s.scalars(select(LedgerEntry).where(LedgerEntry.reason == "refund")).all()
    assert len(refunds) == 1


def test_price_changed_and_validation(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    route = mock.post("/topups/order")
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS,
                                               "expected_price": "0.95"})
    assert r.status_code == 409 and "Цена изменилась" in r.json()["detail"]
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": {"server": "eu"}})
    assert r.status_code == 422
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc",
                                               "fields": {"player_id": "1", "server": "mars"}})
    assert r.status_code == 422
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "nope", "fields": FIELDS})
    assert r.status_code == 409
    assert route.call_count == 0 and balance(client) == "5.0000"


def test_stop_sales_and_limits(client, mock):
    uid = setup_user(client, amount="1000")
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "x", "status": "processing"}})
    buyer = client.cookies.get("session")
    as_admin(client)
    assert client.put("/api/admin/settings/sales", json={"enabled": False}).json() == {"enabled": False}
    client.cookies.clear(); client.cookies.set("session", buyer)
    assert client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS}).status_code == 503
    as_admin(client)
    client.put("/api/admin/settings/sales", json={"enabled": True})
    client.cookies.clear(); client.cookies.set("session", buyer)
    r = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "big", "fields": FIELDS})
    assert r.status_code == 400 and "лимит" in r.json()["detail"]  # 330 > 200 default
    assert balance(client) == "1000.0000"


def test_telegram_unknown_outcome_goes_to_review_not_retried(client, mock):
    setup_user(client)
    mock.get("/telegram/stars").respond(json={"ok": True, "kind": "telegram_stars", "price_per_star": "0.0153750",
                                             "min_amount": 50, "max_amount": 100000, "rates_updated_at": "x"})
    buy = mock.post("/telegram/stars/buy")
    buy.mock(side_effect=httpx.ConnectError("down"))
    r = client.post("/api/orders/telegram-stars", json={"username": "@durov_fan", "quantity": 100,
                                                         "expected_price": "1.70"})
    assert r.status_code == 201, r.text  # 100*0.015375=1.5375 *1.1 = 1.69125 -> 1.70
    oid = r.json()["id"]
    assert r.json()["status"] == "processing" and balance(client) == "3.3000"
    sync_pending(db())
    client.get(f"/api/orders/{oid}")
    assert buy.call_count == 1  # never retried automatically (no idempotency for Telegram)
    as_admin(client)
    item = client.get("/api/admin/orders", params={"needs_review": True}).json()["items"][0]
    assert item["id"] == oid and item["cost"] == "1.5375"
    assert client.post(f"/api/admin/orders/{oid}/refund", json={"note": "checked: not delivered"}).status_code == 200
    assert client.post(f"/api/admin/orders/{oid}/refund", json={"note": "again"}).status_code == 409
    s = db()
    assert s.get(User, item["user_id"]).balance == Decimal("5.0000")


def test_telegram_username_validation(client, mock):
    setup_user(client)
    r = client.post("/api/orders/telegram-premium", json={"username": "a b", "months": 3})
    assert r.status_code == 422


def test_orders_are_private(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "o1", "status": "processing"}})
    oid = client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS}).json()["id"]
    client.cookies.clear()
    register(client, email="other@example.com", username="other")
    assert client.get(f"/api/orders/{oid}").status_code == 404
    assert client.get("/api/orders").json()["total"] == 0


def test_admin_stats_profit(client, mock):
    setup_user(client)
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "o1", "status": "completed"}})
    client.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc", "fields": FIELDS})
    as_admin(client)
    assert client.get("/api/admin/stats").json() == {"completed_orders": 1, "revenue": "1.0000", "cost": "0.9077",
                                                     "profit": "0.0923", "orders_need_review": 0}


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
                    reason="row locks need PostgreSQL")
def test_no_double_spend_under_concurrency(client, mock):
    setup_user(client, amount="1.50")  # enough for ONE order of $1.00
    buyer = client.cookies.get("session")
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.post("/topups/order").respond(json={"ok": True, "order": {"id": "c", "status": "processing"}})
    results = []

    def buy():
        with TestClient(create_app()) as c:
            c.cookies.set("session", buyer)
            results.append(c.post("/api/orders/topup", json={"category_id": "pubg", "offer_id": "60uc",
                                                             "fields": FIELDS}).status_code)

    threads = [threading.Thread(target=buy) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201, 402, 402, 402, 402, 402]
    assert balance(client) == "0.5000"
