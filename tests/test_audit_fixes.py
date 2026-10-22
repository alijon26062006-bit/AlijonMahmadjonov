"""Аудит: ҳар хатои ёфташуда — тест, то дигар барнагардад."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from shop import fulfillment, payments, tenants as tenants_mod
from shop.db import ORDER_DONE, ORDER_NEW, ORDER_REJECTED, price_of
from shop.handlers import admin as admin_h
from shop.handlers import constructor as con_h
from shop.handlers import menu as menu_h
from shop.handlers import purchase as buy_h
from shop.handlers import reviews as rev_h
from shop.handlers import settings as st
from shop.middlewares import NavClearsState, TenantMiddleware
from shop.states import Admin, Buy, Review

from test_constructor import BUYER_ID, PARTNER_ID, _buyer_order, _settle, _tenant, platform  # noqa: F401
from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    USER_ID,
    FakeBot,
    FakeCallback,
    FakeMessage,
    FakeSupplier,
    cfg,
    db,
    state,
)


@pytest.fixture
def cfg_api(cfg):
    return replace(cfg, supplier="fireloot", supplier_url="https://api.test", supplier_key="k")


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    import functools

    from shop import wholesale

    fast = functools.partialmethod(wholesale.WholesaleSupplier.wait_until_done, interval=0.01)
    monkeypatch.setattr(wholesale.WholesaleSupplier, "wait_until_done", fast)


def _paid(db, code="pubg_660", price=9370):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    row = db.product(code)
    return db.create_order(
        user_id=USER_ID, product_code=code, category=row["category"], title=row["title"],
        price=price, target="123456789", nickname="T", sku=row["sku"], kind=row["kind"],
    )


# ── конструктор ───────────────────────────────────────────────────────
async def test_update_of_stopped_tenant_bot_is_dropped(platform):
    ctx = await _tenant(platform)
    await platform.manager.stop(ctx.id)
    called = []

    async def handler(event, data):
        called.append(data["db"])

    mw = TenantMiddleware(platform.manager.resolve, lambda bot_id: bot_id == 1)
    await mw(handler, None, {"bot": SimpleNamespace(id=4242), "db": platform.db, "cfg": platform.cfg})
    assert called == []                       # бо базаи асосӣ коркард нашуд
    await mw(handler, None, {"bot": SimpleNamespace(id=1), "db": platform.db, "cfg": platform.cfg})
    assert called == [platform.db]


async def test_stopped_tenant_db_stays_usable_for_running_orders(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)
    await platform.manager.stop(ctx.id)
    assert ctx.db.order(order_id)["status"] == ORDER_NEW    # база баста нашуд


async def test_start_refused_when_constructor_off(platform):
    platform.db.set_setting(tenants_mod.CONSTRUCTOR_ON_KEY, "0")
    tid = platform.db.add_tenant(PARTNER_ID, 4242, "b", "B", "1:x")
    assert await platform.manager.start(platform.db.tenant(tid), poll=False) is None


async def test_sync_resends_interrupted_tenant_order_once(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)
    ctx.db.set_supplier_ref(order_id, f"{ctx.db.order_key_prefix()}-{order_id}")
    # Бот дар миёнаи харид қатъ шуд: фармоиш «нав» монд, пул аз шарик гирифта шуд.
    row = ctx.db.order(order_id)
    await ctx.supplier.place_for(row, "5123456789", "", row["supplier_ref"])
    await _settle()

    await platform.manager.sync_orders(ctx)
    await _settle()

    assert ctx.db.order(order_id)["status"] == ORDER_DONE
    assert platform.db.user(PARTNER_ID).balance == 10000 - 1100   # як бор


async def test_tenant_buyer_sees_no_internal_reason(platform):
    ctx = await _tenant(platform, balance=0)
    order_id = _buyer_order(ctx)
    await fulfillment.deliver_order(ctx.bot, ctx.db, ctx.cfg, ctx.supplier, order_id)
    await _settle()
    assert ctx.db.order(order_id)["status"] == ORDER_REJECTED
    assert "яклухт" not in ctx.bot.to(BUYER_ID) and "шарик" not in ctx.bot.to(BUYER_ID)


def test_operator_may_not_open_owner_sections():
    assert con_h._operator_forbidden("a:req")
    assert con_h._operator_forbidden("a:plus:5")
    assert con_h._operator_forbidden("a:card")
    assert con_h._operator_forbidden("a:ops")
    assert not con_h._operator_forbidden("a:orders")
    assert not con_h._operator_forbidden("a:odone:12")
    assert not con_h._operator_forbidden("a:tok:3")


async def test_operator_filter_uses_owner_ids(cfg):
    tcfg = replace(cfg, admin_ids=(PARTNER_ID, 55), owner_ids=(PARTNER_ID,), tenant_id=1)
    is_op = con_h.IsOperator()
    assert await is_op(FakeCallback("a:req", user_id=55), tcfg)
    assert not await is_op(FakeCallback("a:req", user_id=PARTNER_ID), tcfg)


async def test_group_toggle_in_tenant_skips_products_without_wholesale(platform):
    ctx = await _tenant(platform)
    ctx.db.set_group_products_active("pubg_uc", False)
    ctx.db.set_group_products_active("pubg_uc", True, only_available=True)
    assert ctx.db.product("pubg_60")["active"]            # нархи яклухт дорад
    assert not ctx.db.product("pubg_660")["active"]       # надорад


async def test_global_bot_cap_is_enforced(db, cfg, state):
    db.set_setting(tenants_mod.MAX_BOTS_KEY, "1")
    db.add_tenant(999, 1111, "x", "X", "1:x")
    db.touch_user(PARTNER_ID)
    db.grant_constructor(PARTNER_ID, 5, ADMIN_ID)
    cb = FakeCallback("c:new", user_id=PARTNER_ID)
    await con_h.cb_c_new(cb, state, db, cfg)
    assert await state.get_state() is None


async def test_setlang_does_not_mutate_callback(db, cfg):
    tid = db.add_tenant(PARTNER_ID, 4242, "b", "B", "1:x")
    cb = FakeCallback(f"c:setlang:{tid}:ru", user_id=PARTNER_ID)
    await con_h.cb_c_setlang(cb, db, cfg, None)          # FakeCallback тағйирнопазир аст
    assert db.tenant(tid)["lang"] == "ru"


# ── фармоишҳо ва пул ──────────────────────────────────────────────────
async def test_supplier_failure_after_manual_done_alerts_admin(db, cfg_api):
    bot = FakeBot()
    order_id = _paid(db)
    db.set_order_status(order_id, ORDER_DONE)
    await fulfillment._refund(bot, cfg_api, db, order_id, "failed")
    assert db.order(order_id)["status"] == ORDER_DONE
    assert "рад кард" in bot.to(ADMIN_ID)


async def test_admin_cannot_close_order_while_bot_sends_it(db, cfg):
    order_id = _paid(db)
    key = fulfillment.busy_key(db, order_id)
    fulfillment._BUSY.add(key)
    try:
        cb = FakeCallback(f"a:orej:{order_id}", user_id=ADMIN_ID)
        await admin_h.cb_order_action(cb, db, cfg, FakeBot())
    finally:
        fulfillment._BUSY.discard(key)
    assert db.order(order_id)["status"] == ORDER_NEW
    assert db.user(USER_ID).balance == 20000 - 9370


async def test_buy_refuses_changed_price(db, cfg, state):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    await state.set_state(Buy.confirming)
    await state.update_data(code="pubg_60", target="5123456789", nickname="T", price=1000)
    db.set_price("pubg_60", 1500)
    cb = FakeCallback("b:ok", user_id=USER_ID)
    await buy_h.cb_buy(cb, state, db, cfg, FakeBot(), FakeSupplier())
    assert db.user_orders(USER_ID, 5) == []
    assert any(a and "Нарх иваз шуд" in a for a in cb.answers)


def test_partner_price_never_above_normal(db):
    db.set_partner_price("pubg_60", 950)
    db.set_price("pubg_60", 900)
    assert price_of(db.product("pubg_60"), partner=True) == 900


def test_topup_codes_are_unique_among_waiting():
    busy = {f"{n}" for n in range(1000, 9999)}           # ҳама ба ҷуз 9999 банд
    assert payments.make_code(busy) == "9999"


async def test_stale_orders_are_reported_to_admin(db, cfg_api):
    bot = FakeBot()
    order_id = _paid(db)
    db._run("UPDATE orders SET updated_at = '2020-01-01T00:00:00' WHERE id = ?", (order_id,))
    counts = await fulfillment.resume_open_orders(bot, db, cfg_api, FakeSupplier())
    assert counts == {"old": 1}
    assert f"#{order_id}" in bot.to(ADMIN_ID)


# ── панел ва менюҳо ───────────────────────────────────────────────────
async def test_command_during_admin_input_cancels_instead_of_saving(db, cfg, state):
    await state.set_state(Admin.waiting_holder)
    msg = FakeMessage("/bekor", user_id=ADMIN_ID)
    await menu_h.command_during_input(msg, state, db, cfg)
    assert await state.get_state() is None
    assert db.setting("card_holder") != "/bekor"


async def test_in_state_filter():
    f = menu_h.InState()
    assert await f(FakeMessage("/x"), raw_state="Admin:waiting_holder")
    assert not await f(FakeMessage("/x"), raw_state=None)


async def test_too_long_review_is_refused(db, cfg, state):
    db.touch_user(USER_ID)
    await state.set_state(Review.waiting_text)
    msg = FakeMessage("а" * 5000)
    await rev_h.got_review(msg, state, db, cfg, FakeBot())
    assert "дароз" in msg.last and db.pending_reviews() == []


def test_broadcast_buttons_reject_bad_urls():
    assert st.parse_buttons("Сайт | https://example.com") is not None
    assert st.parse_buttons("Сайт | https://exa mple.com") is None
    assert st.parse_buttons("Сайт | https://") is None
    assert st.parse_buttons("Канал | tg://resolve?domain=x") is not None


async def test_broadcast_stops_if_telegram_rejects_preview(db, state):
    from aiogram.exceptions import TelegramBadRequest

    db.touch_user(USER_ID)

    class Rejecting(FakeBot):
        async def copy_message(self, chat_id, **kwargs):
            raise TelegramBadRequest(method=None, message="BUTTON_URL_INVALID")

    bot = Rejecting()
    await state.set_data({"body_id": 7, "source_chat": ADMIN_ID})
    cb = FakeCallback("a:bcgo", user_id=ADMIN_ID)
    await st.cb_broadcast_send(cb, state, db, bot)
    assert "қабул накард" in cb.message.all_text()
    assert bot.to(USER_ID) == ""


async def test_empty_payment_method_does_not_block_turning_off_other(db, cfg):
    blank = replace(cfg, alif_account="", card_number="")
    db.set_setting("card_number", "8888 1234 1234 1234")
    db.set_setting("alif_account", "")
    cb = FakeCallback("a:dctoggle", user_id=ADMIN_ID)
    await st.cb_toggle_method(cb, db, blank)
    # Alif бе ҳисоб кор намекунад — DC охирин тарзи воқеӣ аст, хомӯш намешавад.
    assert db.setting("dc_enabled", "1") == "1"


async def test_navigation_clears_pending_admin_input(state):
    await state.set_state(Admin.waiting_plus)
    seen = []

    async def handler(event, data):
        seen.append(await data["state"].get_state())

    await NavClearsState()(handler, SimpleNamespace(data="a:stats"), {"state": state})
    assert seen == [None]


def test_find_user_with_huge_number_does_not_crash(db):
    assert db.find_user("9" * 25) is None


async def test_safe_edit_on_inaccessible_message():
    from shop.handlers.common import safe_edit

    sent = []

    class Bot:
        async def send_message(self, chat_id, text, reply_markup=None):
            sent.append(chat_id)

    cb = SimpleNamespace(message=SimpleNamespace(chat=None), bot=Bot(),
                         from_user=SimpleNamespace(id=5))
    await safe_edit(cb, "hi")
    assert sent == [5]


# ── API ───────────────────────────────────────────────────────────────
def test_idempotency_survives_new_api_key(db):
    from shop import devapi
    from shop.db import DuplicateRequest

    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    devapi.issue_key(db, USER_ID)
    first = db.active_api_key(USER_ID)["id"]
    row = db.product("pubg_60")
    args = dict(user_id=USER_ID, product_code="pubg_60", category=row["category"],
                title=row["title"], price=1000, target="1", nickname=None, sku="", kind="game",
                source="api")
    order_id = db.create_order(**args, api_key_id=first, idem=("k1", "h"))
    devapi.issue_key(db, USER_ID)                          # калиди нав
    second = db.active_api_key(USER_ID)["id"]
    with pytest.raises(DuplicateRequest) as dup:
        db.create_order(**args, api_key_id=second, idem=("k1", "h"))
    assert dup.value.order_id == order_id
    assert db.user(USER_ID).balance == 19000


def test_prefix_rotates_and_donatix_keeps_ref(db):
    from shop.donatix import DonatixSupplier

    old = db.order_key_prefix()
    new = db.rotate_order_key_prefix()
    assert new != old and db.order_key_prefix() == new
    dx = DonatixSupplier("k", key_prefix=new)
    assert dx.idempotency_key(f"{old}-5") == f"{old}-5"      # калиди фармоиши кушода иваз намешавад
    assert dx.idempotency_key("5") == f"{new}-order-5"
