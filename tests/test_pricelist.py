"""«💰 Нархҳо»: соҳиби калиди API ва шарики конструктор нархҳои худро мебинанд."""

from __future__ import annotations

from shop import costs, devapi, pricelist, wholesale
from shop.handlers import common as common_h
from shop.handlers import pricelist as pl_h

from test_constructor import PARTNER_ID, _tenant, cfg_api, platform  # noqa: F401
from test_shop_flow import (  # noqa: F401 — fixtures
    ADMIN_ID,
    USER_ID,
    FakeCallback,
    FakeMessage,
    cfg,
    db,
)


def _prices(db):
    db.set_setting(costs.RATE_KEY, "10")
    db.set_setting(costs.API_MARKUP_KEY, "5")
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, "10")
    db.set_cost("pubg_60", 1000)
    db.set_cost("stars_100", 1500)


def _buttons(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_viewer_rules(db):
    db.touch_user(USER_ID)
    assert not pricelist.viewer_of(db, USER_ID).any
    devapi.issue_key(db, USER_ID)
    assert pricelist.viewer_of(db, USER_ID) == pricelist.Viewer(api=True)
    db.grant_constructor(USER_ID, 1, ADMIN_ID)
    assert pricelist.viewer_of(db, USER_ID) == pricelist.Viewer(api=True, wholesale=True)
    assert pricelist.viewer_of(db, 42, is_admin=True).any


async def test_menu_button_only_for_api_and_constructor(db, cfg):
    db.touch_user(USER_ID)
    msg = FakeMessage("/start")
    await common_h.show_main_menu(msg, db, cfg, edit=False)
    assert "pl:home" not in _buttons(msg.last_markup)

    devapi.issue_key(db, USER_ID)
    await common_h.show_main_menu(msg, db, cfg, edit=False)
    assert _buttons(msg.last_markup)[0] == "pl:home"          # дар ҷои аввал, намоён


async def test_api_holder_sees_api_prices_and_codes(db, cfg):
    _prices(db)
    db.touch_user(USER_ID)
    devapi.issue_key(db, USER_ID)
    cb = FakeCallback("pl:home")
    await pl_h.cb_prices(cb, db, cfg)
    assert "pl:cat:pubg" in _buttons(cb.message.last_markup)

    cb = FakeCallback("pl:cat:pubg")
    await pl_h.cb_prices_category(cb, db, cfg)
    text = cb.message.all_text()
    api = costs.api_price(1000, 10, 5)                           # 10.50
    assert f"{api // 100}.{api % 100:02d}" in text and "<code>pubg_60</code>" in text
    assert "pubg_660" not in text                                 # бе нархи харид — нест


async def test_partner_sees_wholesale_price(db, cfg):
    _prices(db)
    db.touch_user(PARTNER_ID)
    db.grant_constructor(PARTNER_ID, 1, ADMIN_ID)
    cb = FakeCallback("pl:cat:pubg", user_id=PARTNER_ID)
    await pl_h.cb_prices_category(cb, db, cfg)
    assert "11.00" in cb.message.all_text()                       # 1 $ × 10 + 10%
    assert "<code>" not in cb.message.all_text()                  # коди API лозим нест


async def test_plain_buyer_gets_no_prices(db, cfg):
    db.touch_user(USER_ID)
    cb = FakeCallback("pl:cat:pubg")
    await pl_h.cb_prices_category(cb, db, cfg)
    assert cb.message.sent == [] and cb.answers


def test_long_lists_are_split():
    lines = [f"• мол {i} — 10.00 с." for i in range(500)]
    parts = pricelist.chunks(lines)
    assert len(parts) > 1 and all(len(p) <= pricelist.CHUNK for p in parts)
    assert sum(p.count("•") for p in parts) == 500


async def test_tenant_wholesale_table_shows_profit(platform):
    from shop import texts

    ctx = await _tenant(platform)
    lines = texts.wholesale_lines("pubg", ctx.db.products("pubg", only_active=False))
    joined = "\n".join(lines)
    assert "11.00 с. → <b>13.00 с.</b> (+2.00 с.)" in joined      # яклухт → нарх (фоида)
    assert "платформа намефурӯшад" in joined
