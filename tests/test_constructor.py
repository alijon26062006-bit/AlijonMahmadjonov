"""Конструктор: нархи яклухт, фармоиши боти шарик, пайваст кардани бот, дастрасӣ."""

from __future__ import annotations

import asyncio
import functools
from dataclasses import replace
from types import SimpleNamespace

import pytest

from shop import costs, fulfillment, keyboards, tenants as tenants_mod, wholesale
from shop.db import ORDER_DONE, ORDER_REJECTED, Database
from shop.handlers import common as common_h
from shop.handlers import constructor as con_h
from shop.i18n import in_tenant, set_tenant
from shop.middlewares import TenantMiddleware
from shop.states import Constructor

from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    FakeBot,
    FakeCallback,
    FakeMessage,
    FakeSupplier,
    cfg,
    db,
    state,
)

PARTNER_ID = 777
BUYER_ID = 888
TOKEN = "123456789:AAH" + "x" * 32


@pytest.fixture
def cfg_api(cfg):
    return replace(cfg, supplier="fireloot", supplier_url="https://api.test", supplier_key="k")


@pytest.fixture(autouse=True)
def _fast_wait(monkeypatch):
    fast = functools.partialmethod(wholesale.WholesaleSupplier.wait_until_done, interval=0.01)
    monkeypatch.setattr(wholesale.WholesaleSupplier, "wait_until_done", fast)
    yield
    set_tenant(0)


def _prices(db, rate="10", markup="10"):
    """Курс 10, наценкаи яклухт 10%: pubg_60 (1.000 $) → 11.00 сомонӣ яклухт."""
    db.set_setting(costs.RATE_KEY, rate)
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, markup)
    db.set_cost("pubg_60", 1000)
    db.set_cost("pubg_325", 4500)
    db.set_cost("ffcis_110", 800)


async def _settle():
    for _ in range(100):
        tasks = [t for t in fulfillment._TASKS if not t.done()]
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture
async def platform(db, cfg_api, tmp_path):
    _prices(db)
    db.touch_user(PARTNER_ID, "partner", "Partner")
    supplier, bot = FakeSupplier(), FakeBot()
    plat = tenants_mod.Platform(db, cfg_api, supplier, bot)
    manager = tenants_mod.TenantManager(plat)
    yield SimpleNamespace(db=db, cfg=cfg_api, supplier=supplier, bot=bot, manager=manager)
    await _settle()
    for ctx in list(manager.contexts.values()):
        ctx.db.close()


async def _tenant(p, balance=10000):
    if balance:
        p.db.change_balance(PARTNER_ID, balance, "topup")
    tid = p.db.add_tenant(PARTNER_ID, 4242, "partner_shop_bot", "Shop", TOKEN)
    p.db.pay_subscription(tid, 0, 30)                  # обунаи пардохтшуда (бе пул)
    ctx = await p.manager.start(p.db.tenant(tid), poll=False)
    ctx.bot = FakeBot()
    return ctx


# ── нархҳо ────────────────────────────────────────────────────────────
def test_retail_price_rounds_up_to_half_somoni():
    assert wholesale.retail_price(1100, 15) == 1300        # 12.65 → 13.00
    assert wholesale.retail_price(1000, 0) == 1000
    assert wholesale.retail_price(1001, 0) == 1050


def test_wholesale_price_needs_cost_and_active(db):
    _prices(db)
    assert wholesale.wholesale_price(db, db.product("pubg_60")) == 1100
    assert wholesale.wholesale_price(db, db.product("pubg_660")) is None     # нархи харид нест
    db.set_active("pubg_60", False)
    assert wholesale.wholesale_price(db, db.product("pubg_60")) is None


async def test_reprice_hides_unavailable_and_keeps_manual_price(platform):
    ctx = await _tenant(platform)
    tdb = ctx.db
    assert tdb.product("pubg_60")["wholesale"] == 1100
    assert tdb.product("pubg_60")["price"] == 1300 and tdb.product("pubg_60")["active"]
    assert not tdb.product("pubg_660")["active"] and tdb.product("pubg_660")["auto_off"]

    tdb.set_price("pubg_60", 2000)
    tdb.set_setting(wholesale.PARTNER_MARKUP_KEY, "50")
    wholesale.reprice_tenant(platform.db, tdb)
    assert tdb.product("pubg_60")["price"] == 2000                 # дастӣ — намерасем
    assert tdb.product("pubg_325")["price"] == wholesale.retail_price(4950, 50)

    # Платформа нархи харидро гирифт — мол худкор бармегардад.
    platform.db.set_cost("pubg_660", 9000)
    wholesale.reprice_tenant(platform.db, tdb)
    assert tdb.product("pubg_660")["active"] and not tdb.product("pubg_660")["auto_off"]


async def test_partner_disabled_product_stays_off(platform):
    ctx = await _tenant(platform)
    ctx.db.set_active("pubg_60", False)
    wholesale.reprice_tenant(platform.db, ctx.db)
    assert not ctx.db.product("pubg_60")["active"]


async def test_tenant_title_survives_reseed(platform):
    ctx = await _tenant(platform)
    ctx.db.rename_product("pubg_60", "UC арзон")
    ctx.db.seed_products()
    assert ctx.db.product("pubg_60")["title"] == "UC арзон"


# ── фармоиш дар боти шарик ────────────────────────────────────────────
def _buyer_order(ctx, code="pubg_60"):
    tdb = ctx.db
    tdb.touch_user(BUYER_ID, "buyer", "Buyer")
    tdb.change_balance(BUYER_ID, 5000, "topup")
    row = tdb.product(code)
    return tdb.create_order(
        user_id=BUYER_ID, product_code=code, category=row["category"], title=row["title"],
        price=row["price"], target="5123456789", nickname="Tester", sku=row["sku"],
        kind=row["kind"],
    )


async def test_tenant_order_charges_partner_wholesale_and_completes(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)

    await fulfillment.deliver_order(ctx.bot, ctx.db, ctx.cfg, ctx.supplier, order_id)
    await _settle()

    assert ctx.db.order(order_id)["status"] == ORDER_DONE
    assert ctx.db.order(order_id)["external_id"].startswith("W")
    main_order = platform.db.order(int(ctx.db.order(order_id)["external_id"][1:]))
    assert main_order["source"] == "tenant" and main_order["api_key_id"] == -ctx.id
    assert main_order["price"] == 1100 and main_order["status"] == ORDER_DONE
    assert platform.db.user(PARTNER_ID).balance == 10000 - 1100
    assert ctx.db.user(BUYER_ID).balance == 5000 - 1300
    # Харидор чекро аз боти шарик мегирад, на аз боти асосӣ.
    assert ctx.bot.to(BUYER_ID) and not platform.bot.to(BUYER_ID)
    assert platform.db.tenant_sales(ctx.id) == {"orders": 1, "revenue": 1100}


async def test_tenant_order_is_charged_once_on_retry(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)
    row = ctx.db.order(order_id)
    ref = f"{ctx.db.order_key_prefix()}{order_id}"

    first = await ctx.supplier.place_for(row, "5123456789", "", ref)
    second = await ctx.supplier.place_for(row, "5123456789", "", ref)
    await _settle()

    assert first.ok and second.ok and first.external_id == second.external_id
    assert platform.db.user(PARTNER_ID).balance == 10000 - 1100


async def test_empty_wholesale_balance_refunds_buyer_and_warns_partner(platform):
    ctx = await _tenant(platform, balance=0)
    order_id = _buyer_order(ctx)

    await fulfillment.deliver_order(ctx.bot, ctx.db, ctx.cfg, ctx.supplier, order_id)
    await _settle()

    assert ctx.db.order(order_id)["status"] == ORDER_REJECTED
    assert ctx.db.user(BUYER_ID).balance == 5000
    assert "кофӣ нест" in platform.bot.to(PARTNER_ID)


async def test_low_balance_warning_once(platform):
    ctx = await _tenant(platform, balance=1500)        # пас аз харид 4.00 < 50
    for _ in range(2):
        order_id = _buyer_order(ctx)
        row = ctx.db.order(order_id)
        await ctx.supplier.place_for(row, "5123456789", "", f"x{order_id}")
    await _settle()
    assert platform.bot.to(PARTNER_ID).count("кам монд") == 1


async def test_sync_closes_order_finished_on_platform(platform):
    ctx = await _tenant(platform)
    platform.supplier._statuses = ["processing"]
    order_id = _buyer_order(ctx)
    row = ctx.db.order(order_id)
    result = await ctx.supplier.place_for(row, "5123456789", "", f"ref{order_id}")
    await _settle()
    ctx.db.set_order_status(order_id, "sent", external_id=result.external_id)

    platform.db.set_order_status(int(result.external_id[1:]), ORDER_DONE)
    closed = await platform.manager.sync_orders(ctx)

    assert closed == 1 and ctx.db.order(order_id)["status"] == ORDER_DONE


async def test_other_partner_cannot_read_wholesale_order(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)
    result = await ctx.supplier.place_for(ctx.db.order(order_id), "5123456789", "", "r1")
    await _settle()
    stranger = wholesale.WholesaleSupplier(platform.manager.platform, 99, 31337, ctx.db)
    assert (await stranger.order_status(result.external_id)).code == "order_not_found"


# ── танзимоти боти шарик ──────────────────────────────────────────────
async def test_tenant_cfg_hides_owner_secrets(platform):
    ctx = await _tenant(platform)
    ctx.db.set_setting(tenants_mod.OPERATORS_KEY, "55, 66")
    platform.manager.refresh(ctx.id)
    cfg = platform.manager.by_tenant(ctx.id).cfg
    assert cfg.is_tenant and cfg.admin_ids == (PARTNER_ID, 55, 66)
    assert not cfg.card_number and not cfg.supplier_key and not cfg.donatix_key
    assert not cfg.api_enabled and ADMIN_ID not in cfg.admin_ids


async def test_tenant_middleware_swaps_context(platform):
    ctx = await _tenant(platform)
    mw = TenantMiddleware(platform.manager.resolve)
    seen = {}

    async def handler(event, data):
        seen.update(data, tenant_flag=in_tenant())

    await mw(handler, None, {"bot": SimpleNamespace(id=4242), "db": platform.db,
                             "cfg": platform.cfg})
    assert seen["db"] is ctx.db and seen["cfg"] is ctx.cfg and seen["tenant_flag"]

    seen.clear()
    await mw(handler, None, {"bot": SimpleNamespace(id=1), "db": platform.db, "cfg": platform.cfg})
    assert seen["db"] is platform.db and not seen["tenant_flag"]


async def test_tenant_admin_keyboards_hide_owner_sections(platform):
    set_tenant(5)
    data = [b.callback_data for row in keyboards.admin_home().inline_keyboard for b in row]
    assert "a:supplier" not in data and "o:home" not in data
    set_tenant(0)
    data = [b.callback_data for row in keyboards.admin_home().inline_keyboard for b in row]
    assert "o:home" in data


def test_owner_only_filter_matches():
    pick = lambda d: any(d == k or (k.endswith(":") and d.startswith(k))  # noqa: E731
                         for k in con_h.OWNER_ONLY)
    assert pick("a:supplier") and pick("a:addfam:ff") and not pick("a:settings")


# ── менюи харидор ─────────────────────────────────────────────────────
async def test_menu_hides_empty_games_and_uses_custom_titles(platform):
    ctx = await _tenant(platform)
    for row in ctx.db.products("pubg", only_active=False):
        ctx.db.set_active(row["code"], False)
    ctx.db.set_setting("title:ff_cis", "🔥 FF арзон")
    msg = FakeMessage("/start", user_id=BUYER_ID)
    ctx.db.touch_user(BUYER_ID)

    await common_h.show_main_menu(msg, ctx.db, ctx.cfg, edit=False)

    labels = [b.text for row in msg.last_markup.inline_keyboard for b in row]
    data = [b.callback_data for row in msg.last_markup.inline_keyboard for b in row]
    assert "🔥 FF арзон" in labels
    assert not any(d and d.endswith(":pubg") for d in data)
    assert "c:home" not in data


async def test_constructor_button_only_for_allowed(platform):
    msg = FakeMessage("/start", user_id=BUYER_ID)
    platform.db.touch_user(BUYER_ID)
    await common_h.show_main_menu(msg, platform.db, platform.cfg, edit=False)
    assert "c:home" not in str(msg.last_markup)

    platform.db.grant_constructor(BUYER_ID, 1, ADMIN_ID)
    await common_h.show_main_menu(msg, platform.db, platform.cfg, edit=False)
    assert "c:home" in str(msg.last_markup)


# ── пайваст кардани бот ───────────────────────────────────────────────
@pytest.fixture
def fake_me(monkeypatch):
    found = {}

    async def fetch(token):
        if token.endswith("bad" + "x" * 29):
            raise RuntimeError("Unauthorized")
        return SimpleNamespace(id=found.get("id", 4242), username="partner_shop_bot",
                               first_name="Shop")

    monkeypatch.setattr(con_h, "fetch_me", fetch)
    return found


class _Manager:
    def __init__(self):
        self.started, self.stopped = [], []

    async def start(self, row, **_):
        self.started.append(row["id"])

    async def stop(self, tenant_id):
        self.stopped.append(tenant_id)


async def test_partner_without_access_cannot_add_bot(db, cfg, state):
    db.touch_user(PARTNER_ID)
    cb = FakeCallback("c:new", user_id=PARTNER_ID)
    await con_h.cb_c_new(cb, state, db, cfg)
    assert await state.get_state() is None and cb.answers


async def test_partner_connects_bot(db, cfg, state, fake_me):
    db.touch_user(PARTNER_ID)
    db.change_balance(PARTNER_ID, 6000, "topup")
    db.grant_constructor(PARTNER_ID, 1, ADMIN_ID)
    await state.set_state(Constructor.waiting_token)
    manager = _Manager()
    msg = FakeMessage(TOKEN, user_id=PARTNER_ID)

    await con_h.got_token(msg, state, db, cfg, SimpleNamespace(id=1), manager)

    row = db.tenant_by_bot(4242)
    assert row is not None and row["owner_id"] == PARTNER_ID and row["status"] == "active"
    assert db.user(PARTNER_ID).balance == 1000 and row["paid_until"]     # моҳи аввал: 50 с.
    assert manager.started == [row["id"]]
    assert "тайёр" in msg.all_text() and TOKEN not in msg.all_text()

    # Ҳадди 1 бот — дуюмӣ намешавад.
    fake_me["id"] = 5555
    await state.set_state(Constructor.waiting_token)
    msg2 = FakeMessage("987654321:AAH" + "y" * 32, user_id=PARTNER_ID)
    await con_h.got_token(msg2, state, db, cfg, SimpleNamespace(id=1), manager)
    assert db.tenant_by_bot(5555) is None


async def test_bad_token_and_main_bot_are_refused(db, cfg, state, fake_me):
    db.touch_user(PARTNER_ID)
    db.grant_constructor(PARTNER_ID, 3, ADMIN_ID)
    await state.set_state(Constructor.waiting_token)

    msg = FakeMessage("not a token", user_id=PARTNER_ID)
    await con_h.got_token(msg, state, db, cfg, SimpleNamespace(id=1), None)
    assert "монанд нест" in msg.last

    msg = FakeMessage("123456789:AAHbad" + "x" * 29, user_id=PARTNER_ID)
    await con_h.got_token(msg, state, db, cfg, SimpleNamespace(id=1), None)
    assert "қабул накард" in msg.last

    msg = FakeMessage(TOKEN, user_id=PARTNER_ID)
    await con_h.got_token(msg, state, db, cfg, SimpleNamespace(id=4242), None)
    assert "асосӣ" in msg.last and db.tenant_by_bot(4242) is None


async def test_partner_cannot_manage_foreign_bot(db, cfg):
    tid = db.add_tenant(PARTNER_ID, 4242, "shop_bot", "Shop", TOKEN)
    cb = FakeCallback(f"c:pause:{tid}", user_id=BUYER_ID)
    await con_h.cb_c_pause(cb, db, cfg, None)
    assert db.tenant(tid)["status"] == "active"

    cb = FakeCallback(f"c:pause:{tid}", user_id=PARTNER_ID)
    manager = _Manager()
    await con_h.cb_c_pause(cb, db, cfg, manager)
    assert db.tenant(tid)["status"] == "paused" and manager.stopped == [tid]


async def test_owner_revoke_blocks_partner_bots(db, cfg):
    db.touch_user(PARTNER_ID)
    db.grant_constructor(PARTNER_ID, 2, ADMIN_ID)
    tid = db.add_tenant(PARTNER_ID, 4242, "shop_bot", "Shop", TOKEN)
    manager = _Manager()
    await con_h.cb_o_revoke(FakeCallback(f"o:revoke:{PARTNER_ID}", user_id=ADMIN_ID),
                            db, cfg, manager)
    assert db.constructor_access(PARTNER_ID) is None
    assert db.tenant(tid)["status"] == "blocked" and manager.stopped == [tid]


async def test_owner_grants_access_by_id(db, cfg, state):
    db.touch_user(PARTNER_ID, "partner")
    await con_h.got_access(FakeMessage(f"{PARTNER_ID} 3", user_id=ADMIN_ID), state, db, cfg,
                           FakeBot())
    assert db.constructor_access(PARTNER_ID)["max_bots"] == 3


async def test_token_revoked_disables_and_notifies(platform):
    ctx = await _tenant(platform)
    await platform.manager._token_revoked(ctx)
    await asyncio.sleep(0)
    assert platform.db.tenant(ctx.id)["status"] == "disabled"
    assert "хомӯш шуд" in platform.bot.to(PARTNER_ID)


def test_tenant_db_is_separate(tmp_path):
    a, b = Database(tmp_path / "a.sqlite3"), Database(tmp_path / "b.sqlite3")
    try:
        a.touch_user(1)
        a.change_balance(1, 500, "x")
        assert b.user(1) is None
    finally:
        a.close()
        b.close()


# ── нест кардани боти шарик ───────────────────────────────────────────
class _DocBot(FakeBot):
    def __init__(self):
        super().__init__()
        self.documents = []

    async def send_document(self, chat_id, document, caption=None, **kwargs):
        from pathlib import Path

        self.documents.append((chat_id, Path(document.path).read_bytes()[:16]))


async def test_owner_deletes_tenant_bot_completely(platform):
    ctx = await _tenant(platform)
    _buyer_order(ctx)
    path = platform.manager.db_path(ctx.bot_id)
    assert path.exists()

    cb = FakeCallback(f"o:del:{ctx.id}", user_id=ADMIN_ID)
    await con_h.cb_o_delete(cb, platform.db, platform.cfg, platform.manager)
    assert "баргашт надорад" in cb.message.last and "Харидорон: <b>1</b>" in cb.message.last

    bot = _DocBot()
    cb = FakeCallback(f"o:delok:{ctx.id}", user_id=ADMIN_ID)
    await con_h.cb_o_delete_ok(cb, platform.db, platform.cfg, bot, platform.manager)

    assert platform.db.tenant(ctx.id) is None and platform.db.tenant_by_bot(ctx.bot_id) is None
    assert not path.exists()
    assert platform.manager.resolve(ctx.bot_id) is None
    assert bot.documents and bot.documents[0][0] == ADMIN_ID
    assert bot.documents[0][1].startswith(b"SQLite format 3")    # нусхаи база ба соҳиб
    assert not list((path.parent.parent / "deleted").glob("*"))  # дар сервер намонд
    assert "нест карда шуд" in bot.to(PARTNER_ID)
    assert len(cb.answers) == 1


async def test_delete_refused_while_order_is_being_sent(platform):
    ctx = await _tenant(platform)
    order_id = _buyer_order(ctx)
    key = fulfillment.busy_key(ctx.db, order_id)
    fulfillment._BUSY.add(key)
    try:
        cb = FakeCallback(f"o:delok:{ctx.id}", user_id=ADMIN_ID)
        await con_h.cb_o_delete_ok(cb, platform.db, platform.cfg, _DocBot(), platform.manager)
    finally:
        fulfillment._BUSY.discard(key)
    assert platform.db.tenant(ctx.id) is not None
    assert platform.manager.db_path(ctx.bot_id).exists()


async def test_partner_can_add_same_bot_again_after_delete(platform):
    ctx = await _tenant(platform)
    await platform.manager.remove(platform.db.tenant(ctx.id), platform.manager.data_dir / "x")
    tid = platform.db.add_tenant(PARTNER_ID, ctx.bot_id, "partner_shop_bot", "Shop", TOKEN)
    platform.db.pay_subscription(tid, 0, 30)
    new = await platform.manager.start(platform.db.tenant(tid), poll=False)
    assert new.db.stats()["users"] == 0                           # база нав, тоза
