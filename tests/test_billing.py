"""Обунаи моҳонаи конструктор: пардохт, пардохти худкор, огоҳӣ, хомӯшӣ."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from shop import billing, wholesale
from shop.db import NotEnoughMoney
from shop.handlers import constructor as con_h
from shop.states import Admin

from test_constructor import PARTNER_ID, TOKEN, _Manager, cfg_api, platform  # noqa: F401
from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    FakeBot,
    FakeCallback,
    FakeMessage,
    cfg,
    db,
    state,
)


def _iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


def _partner_bot(db, balance=0, *, owner=PARTNER_ID, paid_days=None, auto=False):
    db.touch_user(owner)
    if balance:
        db.change_balance(owner, balance, "topup")
    tid = db.add_tenant(owner, 4242, "shop_bot", "Shop", TOKEN)
    if paid_days is not None:
        db.set_tenant(tid, paid_until=_iso(paid_days))
    if auto:
        db.set_tenant(tid, auto_renew=1)
    return tid


class _Mgr:
    """TenantManager-и сохта барои billing.check_all."""

    def __init__(self, db, admin_ids=(ADMIN_ID,)):
        self.platform = SimpleNamespace(db=db, cfg=SimpleNamespace(admin_ids=admin_ids))
        self.stopped, self.messages = [], []

    async def stop(self, tenant_id):
        self.stopped.append(tenant_id)

    async def tell(self, user_id, text):
        self.messages.append((user_id, text))


# ── пардохт ───────────────────────────────────────────────────────────
def test_default_price_and_zero_markup(db):
    assert billing.price(db) == 5000
    assert wholesale.wholesale_markup(db) == 0          # яклухт = нархи харид


def test_payment_charges_and_extends_from_current_end(db):
    tid = _partner_bot(db, balance=12000, paid_days=10)
    before = billing.paid_until(db.tenant(tid))
    until = billing.charge(db, db.tenant(tid))
    assert db.user(PARTNER_ID).balance == 7000
    assert abs((datetime.fromisoformat(until) - before).days - 30) <= 1   # 10 + 30 рӯз


def test_payment_after_expiry_starts_from_now_and_reactivates(db):
    tid = _partner_bot(db, balance=5000, paid_days=-5)
    db.set_tenant(tid, status="expired")
    until = billing.charge(db, db.tenant(tid))
    assert 29 <= billing.days_left(db.tenant(tid)) <= 30
    assert db.tenant(tid)["status"] == "active" and until


def test_not_enough_money_changes_nothing(db):
    tid = _partner_bot(db, balance=4000, paid_days=-1)
    with pytest.raises(NotEnoughMoney):
        billing.charge(db, db.tenant(tid))
    assert db.user(PARTNER_ID).balance == 4000
    assert not billing.is_paid(db.tenant(tid))


async def test_unpaid_bot_does_not_start(platform):
    tid = platform.db.add_tenant(PARTNER_ID, 4242, "b", "B", TOKEN)
    assert await platform.manager.start(platform.db.tenant(tid), poll=False) is None
    assert platform.db.tenant(tid)["status"] == "expired"


async def test_owner_own_bot_needs_no_subscription(platform):
    tid = platform.db.add_tenant(ADMIN_ID, 4242, "b", "B", TOKEN)
    ctx = await platform.manager.start(platform.db.tenant(tid), poll=False)
    assert ctx is not None


# ── санҷиши даврӣ ─────────────────────────────────────────────────────
async def test_expired_without_auto_stops_bot_and_tells_partner(db):
    tid = _partner_bot(db, balance=9000, paid_days=-0.1)
    mgr = _Mgr(db)
    counts = await billing.check_all(mgr)
    assert counts == {"expired": 1} and mgr.stopped == [tid]
    assert db.tenant(tid)["status"] == "expired"
    assert db.user(PARTNER_ID).balance == 9000            # бе розигӣ пул намегирем
    assert "тамом шуд" in mgr.messages[0][1]


async def test_auto_renew_charges_and_keeps_bot_running(db):
    tid = _partner_bot(db, balance=9000, paid_days=-0.1, auto=True)
    mgr = _Mgr(db)
    assert await billing.check_all(mgr) == {"renewed": 1}
    assert db.user(PARTNER_ID).balance == 4000 and mgr.stopped == []
    assert db.tenant(tid)["status"] == "active" and billing.days_left(db.tenant(tid)) > 29


async def test_auto_renew_without_money_expires(db):
    tid = _partner_bot(db, balance=1000, paid_days=-0.1, auto=True)
    mgr = _Mgr(db)
    assert await billing.check_all(mgr) == {"expired": 1}
    assert db.tenant(tid)["status"] == "expired" and db.user(PARTNER_ID).balance == 1000


async def test_reminders_once_at_three_and_one_day(db):
    tid = _partner_bot(db, balance=0, paid_days=2.5)
    mgr = _Mgr(db)
    await billing.check_all(mgr)
    await billing.check_all(mgr)
    assert len(mgr.messages) == 1 and "тамом мешавад" in mgr.messages[0][1]
    db.set_tenant(tid, paid_until=_iso(0.5), sub_notice=f"{_iso(0.5)}:3")
    await billing.check_all(mgr)
    await billing.check_all(mgr)
    assert len(mgr.messages) == 2


async def test_auto_renew_reminder_warns_about_low_balance(db):
    _partner_bot(db, balance=1000, paid_days=2, auto=True)
    mgr = _Mgr(db)
    await billing.check_all(mgr)
    assert "кофӣ нест" in mgr.messages[0][1]


async def test_admin_bot_and_blocked_bot_are_skipped(db):
    _partner_bot(db, owner=ADMIN_ID, paid_days=-3)
    mgr = _Mgr(db)
    assert await billing.check_all(mgr) == {}


def test_migration_gives_grace_and_zero_markup_once(db):
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, "10")
    tid = _partner_bot(db)
    billing.migrate(db)
    assert wholesale.wholesale_markup(db) == 0
    assert 2.9 < billing.days_left(db.tenant(tid)) <= 3
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, "7")   # соҳиб баъдтар иваз кард
    billing.migrate(db)
    assert wholesale.wholesale_markup(db) == 7             # дубора намерасем


# ── тугмаҳо ───────────────────────────────────────────────────────────
async def test_new_bot_needs_money_for_first_month(db, cfg, state):
    db.touch_user(PARTNER_ID)
    db.grant_constructor(PARTNER_ID, 1, ADMIN_ID)
    cb = FakeCallback("c:new", user_id=PARTNER_ID)
    await con_h.cb_c_new(cb, state, db, cfg)
    assert await state.get_state() is None and "пур кунед" in cb.answers[0]


async def test_pay_button_charges_and_starts_bot(db, cfg):
    tid = _partner_bot(db, balance=6000)
    db.set_tenant(tid, status="expired")
    manager = _Manager()
    cb = FakeCallback(f"c:payok:{tid}", user_id=PARTNER_ID)
    await con_h.cb_c_pay_ok(cb, db, cfg, manager)
    assert db.tenant(tid)["status"] == "active" and manager.started == [tid]
    assert db.user(PARTNER_ID).balance == 1000


async def test_pay_screen_without_money_offers_topup(db, cfg):
    tid = _partner_bot(db, balance=100)
    cb = FakeCallback(f"c:pay:{tid}", user_id=PARTNER_ID)
    await con_h.cb_c_pay(cb, db, cfg)
    assert "кофӣ нест" in cb.message.last
    assert "c:payok" not in str(cb.message.last_markup)


async def test_auto_renew_toggle(db, cfg):
    tid = _partner_bot(db, paid_days=10)
    cb = FakeCallback(f"c:auto:{tid}", user_id=PARTNER_ID)
    await con_h.cb_c_auto(cb, db, cfg)
    assert db.tenant(tid)["auto_renew"] == 1 and len(cb.answers) == 1
    await con_h.cb_c_auto(FakeCallback(f"c:auto:{tid}", user_id=PARTNER_ID), db, cfg)
    assert db.tenant(tid)["auto_renew"] == 0


async def test_stranger_cannot_pay_or_toggle(db, cfg):
    tid = _partner_bot(db, balance=6000, paid_days=1)
    await con_h.cb_c_auto(FakeCallback(f"c:auto:{tid}", user_id=31337), db, cfg)
    assert db.tenant(tid)["auto_renew"] == 0


async def test_owner_changes_price(db, state):
    await state.set_state(Admin.waiting_sub_price)
    await con_h.got_sub_price(FakeMessage("75", user_id=ADMIN_ID), state, db)
    assert billing.price(db) == 7500
    await state.set_state(Admin.waiting_sub_price)
    await con_h.got_sub_price(FakeMessage("0", user_id=ADMIN_ID), state, db)
    assert billing.price(db) == 0


async def test_owner_gifts_month_without_charge(db):
    tid = _partner_bot(db, balance=0, paid_days=-1)
    db.set_tenant(tid, status="expired")
    manager, bot = _Manager(), FakeBot()
    await con_h.cb_o_gift(FakeCallback(f"o:gift:{tid}", user_id=ADMIN_ID), db, bot, manager)
    assert db.tenant(tid)["status"] == "active" and billing.days_left(db.tenant(tid)) > 29
    assert manager.started == [tid] and "тӯҳфа" in bot.to(PARTNER_ID)
    assert db.subscription_income("2000-01-01") == (0, 0)  # тӯҳфа даромад нест


def test_income_counts_paid_subscriptions(db):
    tid = _partner_bot(db, balance=20000)
    billing.charge(db, db.tenant(tid))
    billing.charge(db, db.tenant(tid))
    assert db.subscription_income("2000-01-01") == (2, 10000)
