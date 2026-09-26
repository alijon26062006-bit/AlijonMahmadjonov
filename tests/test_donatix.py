"""Donatix: Stars ва Premium. Шабака иваз карда шудааст — пул намеравад."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from shop import catalog
from shop.db import ORDER_DONE, ORDER_NEW, ORDER_REJECTED, ORDER_SENT
from shop.donatix import DonatixSupplier
from shop.fulfillment import deliver_order, pick_supplier, resume_open_orders
from shop.supplier import ManualSupplier, RouterSupplier

from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    USER_ID,
    FakeMessage,
    FakeSupplier,
    bot,
    cfg,
    cfg_api,
    db,
    state,
)

STARS = {
    "product_id": "tg-stars", "kind": "telegram_stars", "name": "Telegram Stars",
    "unit": "star", "price_usd": "0.016605", "min_quantity": 50, "max_quantity": 10000,
    "fields": [{"key": "telegram_username", "label": "Telegram @username", "type": "text"}],
}
PREMIUM_BY_NAME = [
    {"product_id": "tg-prem-3", "name": "Telegram Premium 3 месяца", "price_usd": "12.5",
     "min_quantity": 1, "max_quantity": 1},
    {"product_id": "tg-prem-6", "name": "Telegram Premium 6 месяцев", "price_usd": "16",
     "min_quantity": 1, "max_quantity": 1},
    {"product_id": "tg-prem-12", "name": "Telegram Premium 1 год", "price_usd": "29",
     "min_quantity": 1, "max_quantity": 1},
]


class FakeDonatix(DonatixSupplier):
    """Donatix бе шабака: ҷавобҳо аз рӯйхат, ҳар дархост сабт мешавад."""

    def __init__(self, replies=None, *, premium=None, stars=None):
        super().__init__("dx_live_test", key_prefix="pfx", retry_pause=0)
        self.replies = list(replies or [])
        self.premium = PREMIUM_BY_NAME if premium is None else premium
        self.stars = [STARS] if stars is None else stars
        self.requests: list[dict] = []

    async def _request(self, method, path, *, headers=None, **kwargs):
        self.requests.append({"method": method, "path": path, "headers": headers or {}, **kwargs})
        if path == "/products":
            kind = kwargs.get("params", {}).get("kind")
            items = self.stars if kind == "telegram_stars" else self.premium
            return 200, {"ok": True, "items": items}, {}
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        status, data = reply[:2]
        return status, data, (reply[2] if len(reply) > 2 else {})

    def orders_sent(self):
        return [r for r in self.requests if r["path"] == "/orders" and r["method"] == "POST"]


def _order(status="processing", oid="dx-1042"):
    return 200, {"ok": True, "order": {"order_id": oid, "status": status}}


# ── каталог ───────────────────────────────────────────────────────────
async def test_stars_quantity_is_star_count():
    item, qty = await FakeDonatix().resolve("stars", 100)
    assert item["product_id"] == "tg-stars" and qty == 100


async def test_stars_outside_limits_are_not_sold():
    assert await FakeDonatix().resolve("stars", 20) is None


@pytest.mark.parametrize("months,pid", [(3, "tg-prem-3"), (6, "tg-prem-6"), (12, "tg-prem-12")])
async def test_premium_matched_by_duration_in_name(months, pid):
    item, qty = await FakeDonatix().resolve("premium", months)
    assert item["product_id"] == pid and qty == 1


async def test_premium_single_product_with_months_as_quantity():
    one = [{"product_id": "tg-premium", "name": "Telegram Premium", "unit": "month",
            "min_quantity": 1, "max_quantity": 12, "price_usd": "4"}]
    item, qty = await FakeDonatix(premium=one).resolve("premium", 6)
    assert item["product_id"] == "tg-premium" and qty == 6


async def test_unknown_premium_is_not_guessed():
    odd = [{"product_id": "tg-premium", "name": "Telegram Premium", "unit": "pcs",
            "min_quantity": 1, "max_quantity": 1}]
    assert await FakeDonatix(premium=odd).resolve("premium", 3) is None


async def test_cost_for_admin_panel():
    assert await FakeDonatix().cost_usd("stars", 100) == pytest.approx(1.6605)
    assert await FakeDonatix().cost_usd("premium", 12) == pytest.approx(29)


# ── фармоиш ───────────────────────────────────────────────────────────
async def test_order_uses_fixed_idempotency_key_and_username_field():
    dx = FakeDonatix([_order()])
    result = await dx.place_order(kind="stars", sku="stars_100", target="@ali_2006",
                                  amount=100, order_id="42")
    assert result.ok and result.external_id == "dx-1042"
    sent = dx.orders_sent()[0]
    assert sent["headers"]["Idempotency-Key"] == "pfx-order-42"
    assert sent["json"] == {"product_id": "tg-stars", "quantity": 100,
                            "fields": {"telegram_username": "@ali_2006"}}


async def test_premium_order_sends_right_product():
    dx = FakeDonatix([_order()])
    await dx.place_order(kind="premium", sku="", target="ali_2006", amount=6, order_id="7")
    assert dx.orders_sent()[0]["json"]["product_id"] == "tg-prem-6"
    assert dx.orders_sent()[0]["json"]["fields"]["telegram_username"] == "@ali_2006"


async def test_timeout_is_retried_with_same_key():
    """Таймаут — ҳамон калид такрор мешавад: Donatix пулро дубора намегирад."""
    dx = FakeDonatix([asyncio.TimeoutError(), _order()])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert result.ok
    keys = {r["headers"]["Idempotency-Key"] for r in dx.orders_sent()}
    assert keys == {"pfx-order-9"} and len(dx.orders_sent()) == 2


async def test_no_answer_at_all_is_uncertain_not_failed():
    dx = FakeDonatix([asyncio.TimeoutError()])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert not result.ok and result.uncertain


async def test_server_error_is_uncertain():
    dx = FakeDonatix([(502, {})])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert result.uncertain


async def test_insufficient_balance_is_a_clear_refusal():
    dx = FakeDonatix([(402, {"ok": False, "error": "Недостаточно средств", "code": "insufficient_balance"})])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert not result.ok and not result.uncertain
    assert result.error == "Баланси таъминкунанда кофӣ нест"


async def test_reused_key_means_order_may_exist():
    dx = FakeDonatix([(409, {"ok": False, "error": "reused", "code": "idempotency_key_reused"})])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert result.uncertain


async def test_rate_limit_waits_and_retries():
    dx = FakeDonatix([(429, {"ok": False, "code": "rate_limited"}, {"Retry-After": "0"}), _order()])
    result = await dx.place_order(kind="stars", sku="", target="@ali_2006", amount=100, order_id="9")
    assert result.ok and len(dx.orders_sent()) == 2


async def test_missing_product_is_refused_without_calling_api():
    dx = FakeDonatix([_order()], premium=[])
    result = await dx.place_order(kind="premium", sku="", target="@a_lijon", amount=3, order_id="9")
    assert not result.ok and not result.uncertain
    assert dx.orders_sent() == []


async def test_status_and_lookup():
    dx = FakeDonatix([_order(status="completed")])
    assert (await dx.order_status("dx-1042")).status == "completed"
    lookup = await dx.order_status("42", by_external=True)
    assert not lookup.ok and lookup.code == "lookup_unsupported"


# ── санҷиши username ──────────────────────────────────────────────────
async def test_check_returns_name():
    dx = FakeDonatix([(200, {"ok": True, "supported": True, "valid": True, "player_name": "Alijon"})])
    result = await dx.check(kind="stars", sku="", target="@ali_2006", amount=50)
    assert result.ok and result.nickname == "Alijon"


async def test_check_unsupported_lets_buyer_confirm():
    dx = FakeDonatix([(200, {"ok": True, "supported": False})])
    result = await dx.check(kind="premium", sku="", target="@ali_2006", amount=3)
    assert result.ok and result.nickname is None


async def test_check_invalid_account():
    dx = FakeDonatix([(200, {"ok": True, "supported": True, "valid": False})])
    result = await dx.check(kind="stars", sku="", target="@nobody_x", amount=50)
    assert not result.ok


# ── ҳидоят ────────────────────────────────────────────────────────────
def test_router_sends_stars_and_premium_to_donatix_only():
    main, dx = FakeSupplier(), FakeDonatix()
    router = RouterSupplier(main, dx)
    assert router.for_kind("premium") is dx
    assert router.for_kind("stars", "stars_50") is dx
    assert router.for_kind("game", "pubg_uc_60") is main
    assert router.for_kind("manual", "x") is None


def test_router_without_donatix_keeps_old_behaviour():
    main = FakeSupplier()
    router = RouterSupplier(main, None)
    assert router.for_kind("stars", "stars_50") is main
    assert router.for_kind("premium") is None           # Premium — дастӣ


def test_donatix_alone_without_fireloot():
    router = RouterSupplier(ManualSupplier(), FakeDonatix())
    assert router.for_kind("game", "pubg_uc_60") is None
    assert router.for_kind("premium") is not None


# ── иҷрои фармоиш ─────────────────────────────────────────────────────
def _paid(db, code, price, target="@ali_2006"):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 100000, "topup")
    row = db.product(code)
    return db.create_order(
        user_id=USER_ID, product_code=code, category=row["category"], title=row["title"],
        price=price, target=target, nickname=None, sku=row["sku"], kind=row["kind"],
    )


async def test_premium_is_delivered_automatically_via_donatix(db, cfg, bot):
    order_id = _paid(db, "prem_3", 16500)
    dx = FakeDonatix([_order(), _order(status="completed")])
    router = RouterSupplier(ManualSupplier(), dx)

    await deliver_order(bot, db, cfg, router, order_id)

    assert db.order(order_id)["status"] == ORDER_DONE
    assert db.order(order_id)["external_id"] == "dx-1042"
    assert "ЧЕКИ ХАРИД" in bot.to(USER_ID)
    assert dx.orders_sent()[0]["json"]["product_id"] == "tg-prem-3"


async def test_stars_go_to_donatix_not_fireloot(db, cfg_api, bot):
    order_id = _paid(db, "stars_100", 2100)
    main, dx = FakeSupplier(), FakeDonatix([_order(status="completed")])

    await deliver_order(bot, db, cfg_api, RouterSupplier(main, dx), order_id)

    assert main.calls == []                              # FireLoot нагирифт
    assert db.order(order_id)["status"] == ORDER_DONE


async def test_games_still_go_to_fireloot(db, cfg_api, bot):
    order_id = _paid(db, "pubg_660", 9370, target="123456789")
    main, dx = FakeSupplier(), FakeDonatix([_order()])

    await deliver_order(bot, db, cfg_api, RouterSupplier(main, dx), order_id)

    assert len(main.calls) == 1 and dx.orders_sent() == []
    assert db.order(order_id)["status"] == ORDER_DONE


async def test_donatix_failed_order_refunds_buyer(db, cfg, bot):
    order_id = _paid(db, "prem_6", 22500)
    dx = FakeDonatix([_order(), _order(status="failed")])

    await deliver_order(bot, db, cfg, RouterSupplier(ManualSupplier(), dx), order_id)

    assert db.order(order_id)["status"] == ORDER_REJECTED
    assert db.user(USER_ID).balance == 100000


async def test_donatix_refusal_refunds_at_once(db, cfg, bot):
    order_id = _paid(db, "stars_100", 2100)
    dx = FakeDonatix([(402, {"ok": False, "error": "x", "code": "insufficient_balance"})])

    await deliver_order(bot, db, cfg, RouterSupplier(ManualSupplier(), dx), order_id)

    assert db.order(order_id)["status"] == ORDER_REJECTED
    assert db.user(USER_ID).balance == 100000
    assert "Баланси таъминкунанда кофӣ нест" in bot.to(ADMIN_ID)


async def test_donatix_silence_never_refunds(db, cfg, bot, monkeypatch):
    """Donatix хомӯш монд — пул намегардад, админ медонад (шояд фармоиш рафта бошад)."""
    from shop import fulfillment

    monkeypatch.setattr(fulfillment, "UNCERTAIN_DELAY", 0)
    order_id = _paid(db, "stars_100", 2100)
    dx = FakeDonatix([asyncio.TimeoutError()])

    await deliver_order(bot, db, cfg, RouterSupplier(ManualSupplier(), dx), order_id)

    assert db.order(order_id)["status"] == ORDER_SENT
    assert db.user(USER_ID).balance == 100000 - 2100
    assert "Donatix санҷед" in bot.to(ADMIN_ID)
    # Ҳамаи кӯшишҳо бо ҳамон калид — ҳатто агар ҳамааш расида бошад, як фармоиш.
    assert {r["headers"]["Idempotency-Key"] for r in dx.orders_sent()} == {f"pfx-order-{order_id}"}


async def test_immediate_completed_answer_skips_waiting(db, cfg, bot):
    order_id = _paid(db, "stars_100", 2100)
    dx = FakeDonatix([_order(status="completed")])

    await deliver_order(bot, db, cfg, RouterSupplier(ManualSupplier(), dx), order_id)

    assert db.order(order_id)["status"] == ORDER_DONE
    assert [r["path"] for r in dx.requests if r["path"].startswith("/orders/")] == []


async def test_resume_resends_with_same_key(db, cfg, bot):
    """Бот дар мобайни фармоиш хомӯш шуд — такрор бо ҳамон калид, пул як бор."""
    order_id = _paid(db, "prem_12", 39000)
    dx = FakeDonatix([_order(status="completed")])

    counts = await resume_open_orders(bot, db, cfg, RouterSupplier(ManualSupplier(), dx))

    assert counts == {"resent": 1}
    assert db.order(order_id)["status"] == ORDER_DONE
    assert dx.orders_sent()[0]["headers"]["Idempotency-Key"] == f"pfx-order-{order_id}"


async def test_old_manual_premium_orders_stay_manual(db, cfg, bot):
    """Фармоишҳои Premium-и пеш аз Donatix («manual») ба Donatix намераванд."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    order_id = db.create_order(
        user_id=USER_ID, product_code="prem_3", category=catalog.CAT_PREMIUM,
        title="Premium", price=16500, target="@ali_2006", nickname=None, sku="", kind="manual",
    )
    dx = FakeDonatix([_order()])
    await resume_open_orders(bot, db, cfg, RouterSupplier(ManualSupplier(), dx))
    assert dx.orders_sent() == []
    assert db.order(order_id)["status"] == ORDER_NEW


def test_premium_catalog_kind(db):
    assert db.product("prem_3")["kind"] == "premium"


def test_pick_supplier_without_router_keeps_premium_manual(cfg_api):
    assert pick_supplier(cfg_api, FakeSupplier(), "premium", "") is None
    assert pick_supplier(cfg_api, FakeSupplier(), "stars", "stars_50") is not None


# ── харид аз меню ─────────────────────────────────────────────────────
async def test_premium_username_is_checked_when_donatix_on(db, cfg, state):
    from shop.handlers import purchase as buy_h
    from shop.states import Buy

    await state.set_state(Buy.waiting_target)
    await state.update_data(code="prem_3")
    dx = FakeDonatix([(200, {"ok": True, "supported": True, "valid": True, "player_name": "Alijon"})])
    message = FakeMessage("@ali_2006")

    await buy_h.got_target(message, state, db, cfg, RouterSupplier(ManualSupplier(), dx))

    assert "Alijon" in message.all_text()
    assert (await state.get_data())["nickname"] == "Alijon"


# ── танзим ────────────────────────────────────────────────────────────
def test_order_key_prefix_is_stable_per_database(db, cfg):
    from shop.main import build_shop_supplier

    on = replace(cfg, donatix_key="dx_live_x")
    first = build_shop_supplier(on, db).telegram.key_prefix
    second = build_shop_supplier(on, db).telegram.key_prefix
    assert first == second and first.startswith("almaz-")


def test_without_key_there_is_no_donatix(db, cfg):
    from shop.main import build_shop_supplier

    assert build_shop_supplier(cfg, db).telegram is None


def test_config_reads_donatix_key(tmp_path, monkeypatch):
    from shop.config import load_config

    monkeypatch.setenv("SHOP_BOT_TOKEN", "1:x")
    monkeypatch.setenv("SHOP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOP_DONATIX_KEY", " dx_live_abc ")
    cfg = load_config(tmp_path / "none.env")
    assert cfg.donatix_key == "dx_live_abc" and cfg.has_donatix
