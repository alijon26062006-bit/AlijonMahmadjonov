"""API барои барномасозон: калидҳо, харид, такрори бехатар, хатоҳо, ҳуҷҷатҳо."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from aiohttp.test_utils import TestClient, TestServer

from shop import devapi, fulfillment, keyboards
from shop.db import ORDER_DONE, ORDER_REJECTED
from shop.supplier import OrderResult

from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    USER_ID,
    FakeBot,
    FakeCallback,
    FakeSupplier,
    cfg,
    db,
)


@pytest.fixture
def cfg_api(cfg):
    return replace(cfg, supplier="fireloot", supplier_url="https://api.test", supplier_key="k")


@pytest.fixture
async def api(db, cfg_api):
    supplier, bot = FakeSupplier(), FakeBot()
    client = TestClient(TestServer(devapi.build_app(db, cfg_api, supplier, bot)))
    await client.start_server()
    try:
        yield client, supplier, bot
    finally:
        await client.close()


def _user(db, balance=20000):
    db.touch_user(USER_ID, "ali", "Alijon")
    if balance:
        db.change_balance(USER_ID, balance, "topup")
    return devapi.issue_key(db, USER_ID)


async def _settle():
    """Иҷрои фармоиш дар паси парда то охир мерасад."""
    for _ in range(50):
        tasks = [t for t in fulfillment._TASKS if not t.done()]
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)


# ── калидҳо ───────────────────────────────────────────────────────────
def test_key_is_stored_only_as_hash(db):
    plain = _user(db)
    row = db.active_api_key(USER_ID)
    assert plain.startswith("ak_live_") and len(plain) > 40
    assert row["key_hash"] == devapi.key_hash(plain) and plain not in row["key_hash"]
    assert row["hint"].startswith("ak_live_") and "…" in row["hint"]


def test_new_key_revokes_old(db):
    old = _user(db)
    new = devapi.issue_key(db, USER_ID)
    assert db.api_key_by_hash(devapi.key_hash(old)) is None
    assert db.api_key_by_hash(devapi.key_hash(new)) is not None


async def test_ping_needs_no_key(api):
    client, _, _ = api
    resp = await client.get("/api/v1/ping")
    assert resp.status == 200 and (await resp.json())["ok"] is True


async def test_requests_without_or_with_bad_key_are_refused(api, db):
    client, _, _ = api
    _user(db)
    assert (await client.get("/api/v1/balance")).status == 401
    bad = await client.get("/api/v1/balance", headers={"X-API-Key": "ak_live_wrong"})
    assert bad.status == 401 and (await bad.json())["code"] == "unauthorized"


async def test_balance_with_key_and_bearer(api, db):
    client, _, _ = api
    key = _user(db, balance=25050)
    for headers in ({"X-API-Key": key}, {"Authorization": f"Bearer {key}"}):
        data = await (await client.get("/api/v1/balance", headers=headers)).json()
        assert data == {"ok": True, "balance": "250.50", "currency": "TJS"}


async def test_revoked_key_stops_working(api, db):
    client, _, _ = api
    key = _user(db)
    db.revoke_api_keys(USER_ID)
    assert (await client.get("/api/v1/balance", headers={"X-API-Key": key})).status == 401


async def test_blocked_user_is_refused(api, db):
    client, _, _ = api
    key = _user(db)
    db.set_blocked(USER_ID, True)
    resp = await client.get("/api/v1/balance", headers={"X-API-Key": key})
    assert resp.status == 403 and (await resp.json())["code"] == "account_blocked"


async def test_owner_can_switch_api_off(api, db):
    client, _, _ = api
    key = _user(db)
    db.set_setting(devapi.API_ON_KEY, "0")
    resp = await client.get("/api/v1/balance", headers={"X-API-Key": key})
    assert resp.status == 503 and (await resp.json())["code"] == "api_disabled"


# ── молҳо ва санҷиш ───────────────────────────────────────────────────
async def test_products_show_buyer_price_and_fields(api, db):
    client, _, _ = api
    key = _user(db)
    db.set_active("pubg_325", False)
    data = await (await client.get("/api/v1/products", headers={"X-API-Key": key})).json()
    by_id = {i["id"]: i for i in data["items"]}

    assert by_id["pubg_60"]["price"] == "10.00" and by_id["pubg_60"]["currency"] == "TJS"
    assert "pubg_325" not in by_id                              # хомӯш — нест
    assert [f["key"] for f in by_id["stars_100"]["fields"]] == ["username"]
    assert [f["key"] for f in by_id["pubg_60"]["fields"]] == ["player_id"]


async def test_partner_sees_partner_price(api, db):
    client, _, _ = api
    key = _user(db)
    db.add_partner(USER_ID)
    db.set_partner_price("pubg_60", 900)
    data = await (await client.get("/api/v1/products?category=pubg",
                                   headers={"X-API-Key": key})).json()
    assert {i["id"]: i["price"] for i in data["items"]}["pubg_60"] == "9.00"
    assert {i["category"] for i in data["items"]} == {"pubg"}


async def test_check_returns_nickname(api, db):
    client, _, _ = api
    key = _user(db)
    data = await (await client.post("/api/v1/check", headers={"X-API-Key": key},
                                    json={"product": "pubg_60", "player_id": "5123456789"})).json()
    assert data == {"ok": True, "supported": True, "valid": True, "nickname": "Tester"}


async def test_check_premium_without_donatix_is_not_supported(api, db):
    client, _, _ = api
    key = _user(db)
    data = await (await client.post("/api/v1/check", headers={"X-API-Key": key},
                                    json={"product": "prem_3", "username": "@ali_2006"})).json()
    assert data["supported"] is False


# ── харид ─────────────────────────────────────────────────────────────
async def test_order_charges_and_completes_without_telegram_spam(api, db):
    client, supplier, bot = api
    key = _user(db)
    resp = await client.post("/api/v1/orders", headers={"X-API-Key": key},
                             json={"product": "pubg_60", "player_id": "5123456789"})
    data = await resp.json()

    assert resp.status == 201 and data["order"]["status"] == "processing"
    assert data["balance"] == "190.00"
    order_id = data["order"]["id"]
    assert db.order(order_id)["source"] == "api"

    await _settle()
    assert db.order(order_id)["status"] == ORDER_DONE
    assert bot.to(USER_ID) == ""                       # харидор чекро аз API мегирад
    assert "API" in bot.to(ADMIN_ID)                   # админ медонад, ки аз API аст

    status = await (await client.get(f"/api/v1/orders/{order_id}",
                                     headers={"X-API-Key": key})).json()
    assert status["order"]["status"] == "completed"


async def test_failed_order_is_refunded_and_reported(api, db):
    client, supplier, _ = api
    supplier._place = OrderResult(ok=False, error="insufficient_balance")
    key = _user(db)
    data = await (await client.post("/api/v1/orders", headers={"X-API-Key": key},
                                    json={"product": "pubg_60", "player_id": "5123456789"})).json()
    await _settle()
    order = (await (await client.get(f"/api/v1/orders/{data['order']['id']}",
                                     headers={"X-API-Key": key})).json())["order"]
    assert order["status"] == "failed" and "возвращены" in order["error"]
    assert db.order(order["id"])["status"] == ORDER_REJECTED
    assert db.user(USER_ID).balance == 20000


async def test_not_enough_money(api, db):
    client, _, _ = api
    key = _user(db, balance=500)
    resp = await client.post("/api/v1/orders", headers={"X-API-Key": key},
                             json={"product": "pubg_60", "player_id": "5123456789"})
    data = await resp.json()
    assert resp.status == 402 and data["code"] == "insufficient_balance"
    assert "10.00" in data["error"] and "5.00" in data["error"]
    assert db.user_orders(USER_ID) == []


async def test_same_idempotency_key_charges_once(api, db):
    client, _, _ = api
    key = _user(db)
    headers = {"X-API-Key": key, "Idempotency-Key": "shop-1001"}
    body = {"product": "pubg_60", "player_id": "5123456789"}
    first = await (await client.post("/api/v1/orders", headers=headers, json=body)).json()
    again = await (await client.post("/api/v1/orders", headers=headers, json=body)).json()

    assert again["duplicate"] is True and again["order"]["id"] == first["order"]["id"]
    assert len(db.user_orders(USER_ID)) == 1
    assert db.user(USER_ID).balance == 20000 - 1000


async def test_idempotency_key_with_other_body_is_rejected(api, db):
    client, _, _ = api
    key = _user(db)
    headers = {"X-API-Key": key, "Idempotency-Key": "shop-1001"}
    await client.post("/api/v1/orders", headers=headers,
                      json={"product": "pubg_60", "player_id": "5123456789"})
    resp = await client.post("/api/v1/orders", headers=headers,
                             json={"product": "pubg_60", "player_id": "5999999999"})
    assert resp.status == 409 and (await resp.json())["code"] == "idempotency_key_reused"
    assert len(db.user_orders(USER_ID)) == 1


async def test_parallel_retries_with_same_key_make_one_order(api, db):
    client, _, _ = api
    key = _user(db)
    headers = {"X-API-Key": key, "Idempotency-Key": "race-1"}
    body = {"product": "pubg_60", "player_id": "5123456789"}
    await asyncio.gather(*(client.post("/api/v1/orders", headers=headers, json=body)
                           for _ in range(5)))
    assert len(db.user_orders(USER_ID)) == 1


@pytest.mark.parametrize("body,code", [
    ({"player_id": "5123456789"}, "missing_field"),
    ({"product": "pubg_60"}, "missing_field"),
    ({"product": "pubg_60", "player_id": "abc"}, "invalid_field"),
    ({"product": "stars_100", "username": "x!"}, "invalid_field"),
    ({"product": "nope", "player_id": "5123456789"}, "product_not_found"),
])
async def test_bad_order_requests(api, db, body, code):
    client, _, _ = api
    key = _user(db)
    resp = await client.post("/api/v1/orders", headers={"X-API-Key": key}, json=body)
    assert (await resp.json())["code"] == code
    assert db.user(USER_ID).balance == 20000


async def test_server_field_required_for_mobile_legends(api, db):
    client, _, _ = api
    key = _user(db)
    db.set_active("mlbb_diamonds_32", True)
    resp = await client.post("/api/v1/orders", headers={"X-API-Key": key},
                             json={"product": "mlbb_diamonds_32", "player_id": "123456789"})
    assert (await resp.json())["field"] == "server"
    ok = await client.post("/api/v1/orders", headers={"X-API-Key": key},
                           json={"product": "mlbb_diamonds_32", "player_id": "123456789",
                                 "server": "2001"})
    order = (await ok.json())["order"]
    assert order["target"] == "123456789" and order["server"] == "2001"


async def test_invalid_json_body(api, db):
    client, _, _ = api
    key = _user(db)
    resp = await client.post("/api/v1/orders", headers={"X-API-Key": key}, data=b"{oops")
    assert resp.status == 400 and (await resp.json())["code"] == "invalid_json"


async def test_cannot_see_other_users_orders(api, db):
    client, _, _ = api
    key = _user(db)
    db.touch_user(777)
    db.change_balance(777, 5000, "topup")
    other = db.create_order(user_id=777, product_code="pubg_60", category="pubg",
                            title="60 UC", price=1000, target="5123456789", nickname=None)
    resp = await client.get(f"/api/v1/orders/{other}", headers={"X-API-Key": key})
    assert resp.status == 404


async def test_history_lists_only_api_orders(api, db):
    client, _, _ = api
    key = _user(db)
    db.create_order(user_id=USER_ID, product_code="pubg_60", category="pubg",
                    title="60 UC", price=1000, target="5123456789", nickname=None)  # аз бот
    await client.post("/api/v1/orders", headers={"X-API-Key": key},
                      json={"product": "pubg_60", "player_id": "5123456789"})
    data = await (await client.get("/api/v1/orders?limit=5", headers={"X-API-Key": key})).json()
    assert len(data["items"]) == 1 and data["limit"] == 5


def test_rate_limiter():
    limiter = devapi.Limiter(2)
    assert limiter.allow(1, 0) and limiter.allow(1, 1)
    assert not limiter.allow(1, 2)
    assert limiter.allow(2, 2)                          # калиди дигар
    assert limiter.allow(1, 61)                         # дақиқа гузашт


# ── ҳуҷҷатҳо ──────────────────────────────────────────────────────────
async def test_docs_page_shows_real_address(api):
    client, _, _ = api
    resp = await client.get("/api/docs")
    page = await resp.text()
    assert resp.status == 200 and "API для разработчиков" in page
    assert "{{" not in page
    assert f"http://{client.host}:{client.port}/api/v1" in page


async def test_docs_use_configured_public_url(db, cfg_api):
    app = devapi.build_app(db, replace(cfg_api, api_public_url="http://89.207.254.178:8080"),
                           FakeSupplier(), FakeBot())
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        page = await (await client.get("/api/docs")).text()
        assert "http://89.207.254.178:8080/api/v1" in page
    finally:
        await client.close()


async def test_root_redirects_to_docs(api):
    client, _, _ = api
    resp = await client.get("/", allow_redirects=False)
    assert resp.status == 302 and resp.headers["Location"] == "/api/docs"


# ── тугмаҳои бот ──────────────────────────────────────────────────────
async def test_bot_screen_creates_and_shows_key_once(db, cfg):
    from shop.handlers import apikeys

    db.touch_user(USER_ID)
    cb = FakeCallback(keyboards.CB_API)
    await apikeys.cb_api(cb, db, cfg)
    assert "ҳанӯз нест" in cb.message.last

    cb = FakeCallback(keyboards.CB_API_NEW)
    await apikeys.cb_api_new(cb, db, cfg)
    assert "ak_live_" in cb.message.last and "нусха бардоред" in cb.message.last

    # Калиди дуюм — аввал пурсиш, баъд иваз.
    ask = FakeCallback(keyboards.CB_API_NEW)
    await apikeys.cb_api_new(ask, db, cfg)
    assert "Калиди нав созем" in ask.message.last
    old_hash = db.active_api_key(USER_ID)["key_hash"]
    await apikeys.cb_api_new_ok(FakeCallback(keyboards.CB_API_NEW_OK), db, cfg)
    assert db.active_api_key(USER_ID)["key_hash"] != old_hash


async def test_bot_revoke_key(db, cfg):
    from shop.handlers import apikeys

    db.touch_user(USER_ID)
    devapi.issue_key(db, USER_ID)
    await apikeys.cb_api_del_ok(FakeCallback(keyboards.CB_API_DEL_OK), db, cfg)
    assert db.active_api_key(USER_ID) is None


async def test_bot_refuses_new_key_when_api_closed(db, cfg):
    from shop.handlers import apikeys

    db.touch_user(USER_ID)
    db.set_setting(devapi.API_ON_KEY, "0")
    cb = FakeCallback(keyboards.CB_API_NEW)
    await apikeys.cb_api_new(cb, db, cfg)
    assert db.active_api_key(USER_ID) is None
    assert cb.answers[-1] == "API ҳоло хомӯш аст."


def test_menu_button_follows_admin_switch():
    with_api = keyboards.main_menu(api=True)
    without = keyboards.main_menu(api=False)
    labels = lambda kb: [b.text for row in kb.inline_keyboard for b in row]  # noqa: E731
    from shop import texts
    assert texts.BTN_API in labels(with_api) and texts.BTN_API not in labels(without)


async def test_admin_toggle_switches_api(db, cfg):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage
    from shop.handlers import settings as st

    state = FSMContext(storage=MemoryStorage(),
                       key=StorageKey(bot_id=1, chat_id=ADMIN_ID, user_id=ADMIN_ID))
    cb = FakeCallback("a:apitoggle", user_id=ADMIN_ID)
    await st.cb_api_toggle(cb, state, db, cfg)
    assert devapi.api_open(db, cfg) is False
    assert "хомӯш" in cb.message.last
    await st.cb_api_toggle(FakeCallback("a:apitoggle", user_id=ADMIN_ID), state, db, cfg)
    assert devapi.api_open(db, cfg) is True
