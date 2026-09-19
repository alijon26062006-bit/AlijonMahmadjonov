"""Тестҳои сенария: аз пахши тугма то фармоиши тайёр."""

from types import SimpleNamespace

import asyncio

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from shop import catalog, keyboards, texts
from shop.config import Config
from shop.db import (
    Database,
    ORDER_DONE,
    ORDER_NEW,
    ORDER_REJECTED,
    ORDER_SENT,
    TOPUP_WAITING,
)
from shop.handlers import admin as admin_h
from shop.handlers import menu as menu_h
from shop.handlers import purchase as buy_h
from shop.handlers import topup as top_h
from shop.fulfillment import deliver_order
from shop.middlewares import GuardMiddleware
from shop.states import Buy, Topup
from shop.supplier import CheckResult, ManualSupplier, OrderResult

USER_ID = 555
ADMIN_ID = 1


# ── дастгоҳҳои сохта ──────────────────────────────────────────────────
class FakeMessage:
    def __init__(self, text=None, user_id=USER_ID, username="ali", first_name="Alijon"):
        self.text = text
        self.html_text = text
        self.message_id = 10
        self.from_user = SimpleNamespace(
            id=user_id, username=username, first_name=first_name, is_bot=False
        )
        self.chat = SimpleNamespace(id=user_id)
        self.sent: list[tuple[str, object]] = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))
        return self

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.sent.append((text, reply_markup))
        return self

    async def delete(self):
        return True

    @property
    def last(self) -> str:
        return self.sent[-1][0] if self.sent else ""

    @property
    def last_markup(self):
        return self.sent[-1][1] if self.sent else None

    def all_text(self) -> str:
        return "\n".join(t for t, _ in self.sent)


class FakeCallback:
    def __init__(self, data, user_id=USER_ID, message=None):
        self.data = data
        self.from_user = SimpleNamespace(
            id=user_id, username="ali", first_name="Alijon", is_bot=False
        )
        self.message = message or FakeMessage(user_id=user_id)
        self.answers: list[str | None] = []

    async def answer(self, text=None, show_alert=False, **kwargs):
        self.answers.append(text)


class FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.messages.append((chat_id, text))

    async def copy_message(self, chat_id, **kwargs):
        self.messages.append((chat_id, kwargs.get("caption", "")))

    def to(self, chat_id) -> str:
        return "\n".join(t for cid, t in self.messages if cid == chat_id)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "shop.sqlite3")
    yield database
    database.close()


@pytest.fixture
def cfg(tmp_path):
    return Config(
        token="1:x",
        admin_ids=(ADMIN_ID,),
        db_path=tmp_path / "shop.sqlite3",
        currency="с.",
        support="support",
        reviews_url="https://t.me/reviews",
        channel_url="",
        card_number="8888 1234 1234 1234",
        card_holder="ALIJON M.",
        pay_link="http://pay.dc.tj/?A={card}&s={amount}&c={comment}&f1=133&FIELD2=&FIELD3=",
        alif_link="https://alifmobi.page.link/providers?id=124&amount={amount}&account={account}",
        alif_account="939880805",
        min_topup=1000,
        max_topup=500000,
        supplier="manual",
        supplier_url="",
        supplier_key="",
        log_level="INFO",
    )


@pytest.fixture
def cfg_api(cfg):
    """Ҳамон танзимот, вале бо таъминкунандаи фаъол."""
    from dataclasses import replace

    return replace(
        cfg, supplier="fireloot", supplier_url="https://api.test", supplier_key="k"
    )


@pytest.fixture
def state():
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=USER_ID, user_id=USER_ID),
    )


@pytest.fixture
def bot():
    return FakeBot()


def _labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


def _has(markup, title: str) -> bool:
    return title in _labels(markup)


# ── оғоз ──────────────────────────────────────────────────────────────
async def test_start_shows_welcome_and_menu(db, cfg, state):
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    assert "Хуш омадед" in message.all_text()
    assert "0.00 с." in message.all_text()
    assert _has(message.last_markup, texts.BTN_TELEGRAM)


async def test_start_registers_user(db, cfg, state):
    await menu_h.cmd_start(FakeMessage("/start"), state, db, cfg)
    user = db.user(USER_ID)
    assert user is not None and user.username == "ali"


async def test_welcome_shows_real_balance(db, cfg, state):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 12345, "test")
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    assert "123.45 с." in message.all_text()


# ── ду қадами Telegram ────────────────────────────────────────────────
async def test_telegram_button_opens_second_step(db, cfg, state):
    cb = FakeCallback(keyboards.CB_TG_MENU)
    await menu_h.cb_telegram(cb, state)
    assert _has(cb.message.last_markup, texts.BTN_STARS)
    assert _has(cb.message.last_markup, texts.BTN_PREMIUM)


async def test_premium_has_three_periods(db, cfg, state):
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_PREMIUM)
    await menu_h.cb_category(cb, state, db, cfg)
    labels = " ".join(_labels(cb.message.last_markup))
    assert "3 моҳ" in labels and "6 моҳ" in labels and "12 моҳ" in labels


@pytest.mark.parametrize(
    "category", [catalog.CAT_FF_CIS, catalog.CAT_FF_ID, catalog.CAT_PUBG]
)
async def test_each_game_has_its_own_price_list(db, cfg, state, category):
    cb = FakeCallback(keyboards.CB_CAT + category)
    await menu_h.cb_category(cb, state, db, cfg)
    assert len(_labels(cb.message.last_markup)) > 3


# ── харид: Telegram Stars ─────────────────────────────────────────────
async def test_stars_asks_for_username(db, cfg, state):
    cb = FakeCallback(keyboards.CB_PRODUCT + "stars_100")
    await buy_h.cb_product(cb, state, db, cfg)
    assert "username" in cb.message.last.lower()
    assert await state.get_state() == Buy.waiting_target.state


async def test_bad_username_is_refused(db, cfg, state):
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "stars_100"), state, db, cfg)
    message = FakeMessage("ab")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "нодуруст" in message.last
    assert await state.get_state() == Buy.waiting_target.state


async def test_stars_username_is_verified_first(db, cfg, state):
    """Stars низ панели тафтишро мебинад — ҳамон тавре ки ID-и бозӣ."""
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "stars_100"), state, db, cfg)
    message = FakeMessage("@Alijon_26")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "Тафтиши аккаунт" in message.all_text()
    assert "@Alijon_26" in message.all_text()


async def test_premium_skips_verification(db, cfg, state):
    """Premium API надорад — рост ба тасдиқи фармоиш."""
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "prem_3"), state, db, cfg)
    message = FakeMessage("@Alijon_26")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "Тасдиқи фармоиш" in message.last
    assert await state.get_state() == Buy.confirming.state


# ── харид: бозӣ бо тафтиши ID ─────────────────────────────────────────
async def test_game_asks_for_player_id(db, cfg, state):
    cb = FakeCallback(keyboards.CB_PRODUCT + "pubg_660")
    await buy_h.cb_product(cb, state, db, cfg)
    assert "ID" in cb.message.last


async def test_short_player_id_is_refused(db, cfg, state):
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "pubg_660"), state, db, cfg)
    message = FakeMessage("123")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "нодуруст" in message.last


async def test_player_id_shows_verification_panel(db, cfg, state):
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "pubg_660"), state, db, cfg)
    message = FakeMessage("123456789")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "Тафтиши аккаунт" in message.last
    assert "123456789" in message.last
    assert _has(message.last_markup, texts.BTN_YES_MINE)


async def test_verification_shows_nickname_from_supplier(db, cfg, state):
    class WithNick(ManualSupplier):
        async def check(self, *, kind, sku, target, amount, server=""):
            return CheckResult(target=target, nickname="ProGamer")

    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "ffcis_341"), state, db, cfg)
    message = FakeMessage("123456789")
    await buy_h.got_target(message, state, db, cfg, WithNick())
    assert "ProGamer" in message.last


async def test_wrong_id_lets_user_retype(db, cfg, state):
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "pubg_660"), state, db, cfg)
    await buy_h.got_target(FakeMessage("123456789"), state, db, cfg, ManualSupplier())
    cb = FakeCallback(keyboards.CB_ID_NO)
    await buy_h.cb_id_no(cb, state, db, cfg)
    assert await state.get_state() == Buy.waiting_target.state


async def test_confirmed_id_goes_to_order_confirmation(db, cfg, state):
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "pubg_660"), state, db, cfg)
    await buy_h.got_target(FakeMessage("123456789"), state, db, cfg, ManualSupplier())
    cb = FakeCallback(keyboards.CB_ID_OK)
    await buy_h.cb_id_ok(cb, state, db, cfg)
    assert "Тасдиқи фармоиш" in cb.message.all_text()


# ── пардохт аз ҳисоб ──────────────────────────────────────────────────
async def _reach_confirm(db, cfg, state, code="prem_3", target="@Alijon_26"):
    """То экрани тасдиқи фармоиш мерасад."""
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + code), state, db, cfg)
    await buy_h.got_target(FakeMessage(target), state, db, cfg, ManualSupplier())
    if await state.get_state() != Buy.confirming.state:
        await buy_h.cb_id_ok(FakeCallback(keyboards.CB_ID_OK), state, db, cfg)


async def test_buying_without_money_offers_topup(db, cfg, state, bot):
    await _reach_confirm(db, cfg, state)
    cb = FakeCallback(keyboards.CB_BUY_OK)
    await buy_h.cb_buy(cb, state, db, cfg, bot, ManualSupplier())
    assert "кифоя нест" in cb.message.last
    assert _has(cb.message.last_markup, texts.BTN_TOPUP)
    assert db.user_orders(USER_ID) == []


async def test_successful_purchase_creates_order_and_takes_money(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    await _reach_confirm(db, cfg, state)
    cb = FakeCallback(keyboards.CB_BUY_OK)
    await buy_h.cb_buy(cb, state, db, cfg, bot, ManualSupplier())

    assert "Фармоиш қабул шуд" in cb.message.last
    orders = db.user_orders(USER_ID)
    assert len(orders) == 1
    assert orders[0]["target"] == "@Alijon_26"
    assert db.user(USER_ID).balance == 50000 - orders[0]["price"]
    assert await state.get_state() is None


async def test_purchase_notifies_admin(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    await _reach_confirm(db, cfg, state)
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())
    await asyncio.sleep(0.05)  # иҷро дар паси парда
    assert "ФАРМОИШИ НАВ" in bot.to(ADMIN_ID)
    assert "@Alijon_26" in bot.to(ADMIN_ID)


async def test_order_keeps_sku_and_kind(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 100000, "topup")
    await _reach_confirm(db, cfg, state, code="pubg_660", target="123456789")
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())
    order = db.user_orders(USER_ID)[0]
    assert order["sku"] == "pubg_uc_660"
    assert order["kind"] == "game"


async def test_price_change_applies_to_next_purchase(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 100000, "topup")
    db.set_price("prem_3", 5000)
    await _reach_confirm(db, cfg, state)
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())
    assert db.user_orders(USER_ID)[0]["price"] == 5000


# ── пур кардани ҳисоб ─────────────────────────────────────────────────
async def test_topup_menu_lists_amounts(db, cfg, state):
    cb = FakeCallback(keyboards.CB_TOPUP)
    await top_h.cb_topup(cb, state, db, cfg)
    assert _has(cb.message.last_markup, texts.BTN_OTHER_SUM)


async def test_preset_amount_shows_card_and_code(db, cfg, state):
    cb = FakeCallback(keyboards.CB_TOPUP_SUM + "10000")
    await top_h.cb_preset_sum(cb, state, db, cfg)
    text = cb.message.all_text()
    assert "8888 1234 1234 1234" in text
    assert "Душанбе Сити" in text
    assert "100.00 с." in text

    row = db.user_topups(USER_ID)[0]
    assert row["status"] == TOPUP_WAITING
    assert len(row["code"]) == 4
    assert row["code"] in text  # коди тасдиқ ба харидор нишон дода мешавад


async def test_payment_link_is_prefilled(db, cfg, state):
    cb = FakeCallback(keyboards.CB_TOPUP_SUM + "15000")
    await top_h.cb_preset_sum(cb, state, db, cfg)
    urls = [b.url for row in cb.message.last_markup.inline_keyboard for b in row if b.url]
    assert urls, "тугмаи ҳавола набояд гум шавад"
    code = db.user_topups(USER_ID)[0]["code"]
    assert "A=8888123412341234" in urls[0]      # корт
    assert "s=150.00" in urls[0]                 # маблағ
    assert f"c={code}" in urls[0]                # коди тасдиқ дар шарҳ
    assert any("alifmobi" in u for u in urls)    # тугмаи дуюм — Alif


async def test_custom_amount_below_minimum_refused(db, cfg, state):
    await top_h.cb_other_sum(FakeCallback(keyboards.CB_TOPUP_OTHER), state, cfg)
    message = FakeMessage("1")
    await top_h.got_amount(message, state, db, cfg)
    assert "нодуруст" in message.last
    assert db.user_topups(USER_ID) == []


async def test_custom_amount_accepted(db, cfg, state):
    await top_h.cb_other_sum(FakeCallback(keyboards.CB_TOPUP_OTHER), state, cfg)
    message = FakeMessage("250")
    await top_h.got_amount(message, state, db, cfg)
    assert db.user_topups(USER_ID)[0]["amount"] == 25000


async def test_i_paid_button_notifies_admin(db, cfg, state, bot):
    await top_h.cb_preset_sum(FakeCallback(keyboards.CB_TOPUP_SUM + "10000"), state, db, cfg)
    topup_id = db.user_topups(USER_ID)[0]["id"]
    cb = FakeCallback(f"{keyboards.CB_TOPUP_PAID}{topup_id}")
    await top_h.cb_paid(cb, state, db, cfg, bot)
    assert "ПАРДОХТИ НАВ" in bot.to(ADMIN_ID)
    assert await state.get_state() == Topup.waiting_receipt.state


async def test_cannot_confirm_someone_elses_payment(db, cfg, state, bot):
    await top_h.cb_preset_sum(FakeCallback(keyboards.CB_TOPUP_SUM + "10000"), state, db, cfg)
    topup_id = db.user_topups(USER_ID)[0]["id"]
    stranger = FakeCallback(f"{keyboards.CB_TOPUP_PAID}{topup_id}", user_id=999)
    await top_h.cb_paid(stranger, state, db, cfg, bot)
    assert bot.to(ADMIN_ID) == ""


# ── панели админ ──────────────────────────────────────────────────────
async def test_admin_finds_user_by_username(db, cfg, state):
    db.touch_user(USER_ID, "ali", "Alijon")
    message = FakeMessage("@ali", user_id=ADMIN_ID)
    await admin_h.got_user_query(message, state, db, cfg)
    assert str(USER_ID) in message.all_text()
    assert "Корти корбар" in message.all_text()


async def test_admin_search_reports_missing_user(db, cfg, state):
    message = FakeMessage("@kase_nest", user_id=ADMIN_ID)
    await admin_h.got_user_query(message, state, db, cfg)
    assert "ёфт нашуд" in message.last


async def test_admin_adds_money_and_user_is_told(db, cfg, state, bot):
    db.touch_user(USER_ID)
    await state.set_data({"target_id": USER_ID})
    message = FakeMessage("50", user_id=ADMIN_ID)
    await admin_h.got_plus(message, state, db, cfg, bot)
    assert db.user(USER_ID).balance == 5000
    assert "пур шуд" in bot.to(USER_ID)


async def test_admin_subtracts_money(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 10000, "topup")
    await state.set_data({"target_id": USER_ID})
    await admin_h.got_minus(FakeMessage("30", user_id=ADMIN_ID), state, db, cfg, bot)
    assert db.user(USER_ID).balance == 7000
    assert "кам карда шуд" in bot.to(USER_ID)


async def test_admin_cannot_subtract_more_than_balance(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 1000, "topup")
    await state.set_data({"target_id": USER_ID})
    message = FakeMessage("500", user_id=ADMIN_ID)
    await admin_h.got_minus(message, state, db, cfg, bot)
    assert db.user(USER_ID).balance == 1000
    assert "нест" in message.last


async def test_admin_marks_order_done_and_user_is_told(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 10000, "topup")
    order_id = db.create_order(
        user_id=USER_ID, product_code="stars_100", category=catalog.CAT_STARS,
        title="100 ⭐️", price=2100, target="@ali", nickname=None,
    )
    cb = FakeCallback(f"a:odone:{order_id}", user_id=ADMIN_ID)
    await admin_h.cb_order_action(cb, db, cfg, bot)
    assert db.order(order_id)["status"] == ORDER_DONE
    assert "иҷро шуд" in bot.to(USER_ID)


async def test_admin_rejects_order_and_money_comes_back(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 10000, "topup")
    order_id = db.create_order(
        user_id=USER_ID, product_code="stars_100", category=catalog.CAT_STARS,
        title="100 ⭐️", price=2100, target="@ali", nickname=None,
    )
    cb = FakeCallback(f"a:orej:{order_id}", user_id=ADMIN_ID)
    await admin_h.cb_order_action(cb, db, cfg, bot)
    assert db.user(USER_ID).balance == 10000
    assert "баргардонида шуд" in bot.to(USER_ID)


async def test_admin_confirms_payment(db, cfg, state, bot):
    db.touch_user(USER_ID)
    topup_id = db.create_topup(USER_ID, 20000, "1234")
    cb = FakeCallback(f"a:tok:{topup_id}", user_id=ADMIN_ID)
    await admin_h.cb_topup_action(cb, db, cfg, bot)
    assert db.user(USER_ID).balance == 20000
    assert "Ҳисоб пур шуд" in bot.to(USER_ID)


async def test_admin_changes_price(db, cfg, state):
    await state.set_data({"price_code": "stars_100"})
    message = FakeMessage("25.50", user_id=ADMIN_ID)
    await admin_h.got_price(message, state, db, cfg)
    assert db.product("stars_100")["price"] == 2550


async def test_admin_filter_lets_admin_in_only(cfg):
    check = admin_h.IsAdmin()
    assert await check(FakeMessage(user_id=ADMIN_ID), cfg=cfg) is True
    assert await check(FakeMessage(user_id=USER_ID), cfg=cfg) is False


# ── маҳдудкунӣ ────────────────────────────────────────────────────────
async def test_blocked_user_is_stopped(db, cfg):
    db.touch_user(USER_ID)
    db.set_blocked(USER_ID, True)
    guard = GuardMiddleware(db, cfg)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    bot = FakeBot()
    await guard(handler, FakeMessage("/start"), {"bot": bot})
    assert called is False
    assert "маҳдуд" in bot.to(USER_ID)


async def test_admin_is_never_blocked(db, cfg):
    db.touch_user(ADMIN_ID)
    db.set_blocked(ADMIN_ID, True)
    guard = GuardMiddleware(db, cfg)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    await guard(handler, FakeMessage("/start", user_id=ADMIN_ID), {"bot": FakeBot()})
    assert called is True


# ── иҷрои худкор тавассути таъминкунанда ─────────────────────────────
class FakeSupplier(ManualSupplier):
    """Таъминкунандаи сохта бо ҷавобҳои идорашаванда."""

    name = "fake"

    def __init__(self, place=None, statuses=None):
        self._place = place or OrderResult(ok=True, external_id="FL-1")
        self._statuses = list(statuses or ["completed"])
        self.calls = []

    async def check(self, *, kind, sku, target, amount, server=""):
        return CheckResult(target=target, nickname="Tester")

    async def place_order(self, *, kind, sku, target, amount, order_id, server=""):
        self.calls.append((kind, sku, target, amount, order_id))
        return self._place

    async def order_status(self, external_id, *, by_external=False):
        status = self._statuses[0] if len(self._statuses) == 1 else self._statuses.pop(0)
        return OrderResult(ok=True, external_id=external_id, status=status)

    async def wait_until_done(self, external_id, **kwargs):
        return await self.order_status(external_id)


def _make_order(db, code="pubg_660", price=9370, target="123456789"):
    row = db.product(code)
    return db.create_order(
        user_id=USER_ID, product_code=code, category=row["category"],
        title=row["title"], price=price, target=target, nickname="Tester",
        sku=row["sku"], kind=row["kind"],
    )


async def test_successful_delivery_sends_receipt(db, cfg_api, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier()

    await deliver_order(bot, db, cfg_api, supplier, order_id)

    assert db.order(order_id)["status"] == ORDER_DONE
    assert db.order(order_id)["external_id"] == "FL-1"
    assert "ЧЕКИ ХАРИД" in bot.to(USER_ID)
    assert "123456789" in bot.to(USER_ID)
    assert db.user(USER_ID).spent == 9370


async def test_supplier_gets_right_sku_and_amount(db, cfg_api, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier()
    await deliver_order(bot, db, cfg_api, supplier, order_id)
    kind, sku, target, amount, ext = supplier.calls[0]
    assert (kind, sku, target, amount) == ("game", "pubg_uc_660", "123456789", 660)
    assert ext == str(order_id)


async def test_rejected_order_is_refunded_at_once(db, cfg_api, bot):
    """Таъминкунанда қабул накард — пул фавран бармегардад."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier(place=OrderResult(ok=False, error="insufficient_balance"))

    await deliver_order(bot, db, cfg_api, supplier, order_id)

    assert db.order(order_id)["status"] == ORDER_REJECTED
    assert db.user(USER_ID).balance == 20000       # пул сари ҷояш
    assert "баргардонида шуд" in bot.to(USER_ID)
    assert "insufficient_balance" in bot.to(ADMIN_ID)


async def test_failed_status_is_refunded(db, cfg_api, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier(statuses=["failed"])

    await deliver_order(bot, db, cfg_api, supplier, order_id)

    assert db.order(order_id)["status"] == ORDER_REJECTED
    assert db.user(USER_ID).balance == 20000
    assert "баргардонида шуд" in bot.to(USER_ID)


async def test_stuck_order_is_not_refunded_but_flagged(db, cfg_api, bot):
    """Ҳанӯз дар коркард — пул намемонад, аммо админ хабар дорад."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier(statuses=["processing"])

    await deliver_order(bot, db, cfg_api, supplier, order_id)

    assert db.order(order_id)["status"] == ORDER_SENT
    assert db.user(USER_ID).balance == 20000 - 9370
    assert "дар коркард" in bot.to(ADMIN_ID)


async def test_manual_product_waits_for_admin(db, cfg_api, bot):
    """Premium API надорад — фармоиш ба админ меравад, на ба таъминкунанда."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    order_id = _make_order(db, code="prem_3", price=16500, target="@ali")
    supplier = FakeSupplier()

    await deliver_order(bot, db, cfg_api, supplier, order_id)

    assert db.order(order_id)["status"] == ORDER_NEW
    assert supplier.calls == []                   # ба API нарафт
    assert "Дастӣ иҷро кунед" in bot.to(ADMIN_ID)


async def test_without_api_key_everything_goes_to_admin(db, cfg, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)
    supplier = FakeSupplier()

    await deliver_order(bot, db, cfg, supplier, order_id)   # cfg бе калиди API

    assert db.order(order_id)["status"] == ORDER_NEW
    assert supplier.calls == []
    assert "ФАРМОИШИ НАВ" in bot.to(ADMIN_ID)


async def test_broken_supplier_never_loses_the_order(db, cfg_api, bot):
    class Exploding(FakeSupplier):
        async def place_order(self, **kwargs):
            raise RuntimeError("шабака канда шуд")

    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 20000, "topup")
    order_id = _make_order(db)

    await deliver_order(bot, db, cfg_api, Exploding(), order_id)

    assert db.order(order_id)["status"] == ORDER_NEW
    assert "дастӣ санҷед" in bot.to(ADMIN_ID)


# ── клавиатураи поёнӣ ─────────────────────────────────────────────────
async def test_bottom_keyboard_removed_once(db, cfg, state):
    """Паёми хидматӣ барои ҳар корбар танҳо як бор меояд."""
    from aiogram.types import ReplyKeyboardRemove

    first = FakeMessage("/start")
    await menu_h.cmd_start(first, state, db, cfg)
    removals = [m for m in first.sent if isinstance(m[1], ReplyKeyboardRemove)]
    assert len(removals) == 1

    second = FakeMessage("/start")
    await menu_h.cmd_start(second, state, db, cfg)
    assert not [m for m in second.sent if isinstance(m[1], ReplyKeyboardRemove)]


async def test_main_menu_has_no_reply_keyboard(db, cfg, state):
    """Дар менюи асосӣ танҳо тугмаҳои inline мемонанд."""
    from aiogram.types import InlineKeyboardMarkup

    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    welcome = [m for m in message.sent if "Хуш омадед" in (m[0] or "")]
    assert welcome and isinstance(welcome[0][1], InlineKeyboardMarkup)


# ── шарикон: нархи махсус ─────────────────────────────────────────────
async def test_partner_sees_cheaper_price_in_list(db, cfg, state):
    db.touch_user(USER_ID)
    db.set_price("pubg_660", 9370)
    db.set_partner_price("pubg_660", 9200)

    normal = FakeCallback(keyboards.CB_CAT + catalog.CAT_PUBG)
    await menu_h.cb_category(normal, state, db, cfg)
    assert "93.70" in " ".join(_labels(normal.message.last_markup))

    db.add_partner(USER_ID)
    partner = FakeCallback(keyboards.CB_CAT + catalog.CAT_PUBG)
    await menu_h.cb_category(partner, state, db, cfg)
    labels = " ".join(_labels(partner.message.last_markup))
    assert "92.00" in labels and "93.70" not in labels


async def test_partner_pays_partner_price(db, cfg, state, bot):
    """Асосӣ: аз ҳисоб маҳз нархи шарикӣ бардошта мешавад."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    db.set_partner_price("pubg_660", 9200)
    db.add_partner(USER_ID)

    await _reach_confirm(db, cfg, state, code="pubg_660", target="123456789")
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())

    order = db.user_orders(USER_ID)[0]
    assert order["price"] == 9200
    assert db.user(USER_ID).balance == 50000 - 9200


async def test_ordinary_user_pays_full_price(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    db.set_price("pubg_660", 9370)
    db.set_partner_price("pubg_660", 9200)

    await _reach_confirm(db, cfg, state, code="pubg_660", target="123456789")
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())
    assert db.user_orders(USER_ID)[0]["price"] == 9370


async def test_partner_without_special_price_pays_normal(db, cfg, state, bot):
    """Агар барои мол нархи шарикӣ гузошта нашуда бошад — нархи оддӣ."""
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    db.add_partner(USER_ID)
    db.set_partner_price("prem_3", None)

    await _reach_confirm(db, cfg, state, code="prem_3", target="@Alijon_26")
    await buy_h.cb_buy(FakeCallback(keyboards.CB_BUY_OK), state, db, cfg, bot, ManualSupplier())
    assert db.user_orders(USER_ID)[0]["price"] == db.product("prem_3")["price"]


async def test_partner_badge_on_start(db, cfg, state):
    db.add_partner(USER_ID)
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    assert "шарикӣ" in message.all_text()


async def test_no_badge_for_ordinary_user(db, cfg, state):
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    assert "шарикӣ" not in message.all_text()


async def test_admin_adds_partner_and_person_is_told(db, cfg, state, bot):
    db.touch_user(USER_ID, "ali", "Alijon")
    message = FakeMessage("@ali", user_id=ADMIN_ID)
    await admin_h.got_partner(message, state, db, cfg, bot)
    assert db.is_partner(USER_ID)
    assert "шарики мо шудед" in bot.to(USER_ID)


async def test_admin_cannot_add_unknown_person(db, cfg, state, bot):
    message = FakeMessage("@kase_nest", user_id=ADMIN_ID)
    await admin_h.got_partner(message, state, db, cfg, bot)
    assert db.partners() == []
    assert "ёфт нашуд" in message.last


async def test_admin_removes_partner(db, cfg, state, bot):
    db.touch_user(USER_ID)
    db.add_partner(USER_ID)
    cb = FakeCallback(f"a:pdel:{USER_ID}", user_id=ADMIN_ID)
    await admin_h.cb_partner_remove(cb, db, cfg, bot)
    assert not db.is_partner(USER_ID)
    assert "бекор карда шуд" in bot.to(USER_ID)


async def test_partner_price_must_be_lower(db, cfg, state):
    """Нархи шарикӣ бояд аз нархи оддӣ кам бошад — вагарна маънӣ надорад."""
    db.set_price("pubg_660", 9370)
    await state.set_data({"price_code": "pubg_660"})
    message = FakeMessage("100", user_id=ADMIN_ID)      # 100.00 > 93.70
    await admin_h.got_partner_price(message, state, db, cfg)
    assert db.product("pubg_660")["partner_price"] != 10000
    assert "кам бошад" in message.last


async def test_admin_sets_and_clears_partner_price(db, cfg, state):
    db.set_price("pubg_660", 9370)
    await state.set_data({"price_code": "pubg_660"})
    await admin_h.got_partner_price(FakeMessage("92", user_id=ADMIN_ID), state, db, cfg)
    assert db.product("pubg_660")["partner_price"] == 9200

    await state.set_data({"price_code": "pubg_660"})
    await admin_h.got_partner_price(FakeMessage("0", user_id=ADMIN_ID), state, db, cfg)
    assert db.product("pubg_660")["partner_price"] is None


# ── зербахшҳо ─────────────────────────────────────────────────────────
async def test_free_fire_shows_two_groups(db, cfg, state):
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_FF_CIS)
    await menu_h.cb_category(cb, state, db, cfg)
    labels = _labels(cb.message.last_markup)
    assert any("Алмос" in x for x in labels)
    assert any("Ваучер" in x for x in labels)


async def test_pubg_goes_straight_to_prices(db, cfg, state):
    """Як зербахш — экрани иловагӣ лозим нест."""
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_PUBG)
    await menu_h.cb_category(cb, state, db, cfg)
    assert any("UC —" in x for x in _labels(cb.message.last_markup))


async def test_group_opens_long_buttons(db, cfg, state):
    cb = FakeCallback(keyboards.CB_GROUP + "ffcis_diamonds")
    await menu_h.cb_group(cb, state, db, cfg)
    rows = cb.message.last_markup.inline_keyboard
    products = [r for r in rows if len(r) == 1 and "—" in r[0].text]
    assert len(products) == 6                       # ҳамаи алмосҳо
    assert all(len(r) == 1 for r in rows[:-1])      # ҳар кадом дар сатри худ
    assert "9.00" in products[0][0].text            # нарх дида мешавад


async def test_group_back_returns_to_category(db, cfg, state):
    cb = FakeCallback(keyboards.CB_GROUP + "ffcis_vouchers")
    await menu_h.cb_group(cb, state, db, cfg)
    back = cb.message.last_markup.inline_keyboard[-1]
    assert back[0].callback_data == keyboards.CB_CAT + catalog.CAT_FF_CIS


async def test_admin_renames_group(db, cfg, state):
    from shop.handlers import settings as st

    await state.set_data({"group_code": "ffcis_diamonds"})
    message = FakeMessage("💎 Алмосҳои арзон", user_id=ADMIN_ID)
    await st.got_group_title(message, state, db)
    assert db.group("ffcis_diamonds")["title"] == "💎 Алмосҳои арзон"

    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_FF_CIS)
    await menu_h.cb_category(cb, state, db, cfg)
    assert any("арзон" in x for x in _labels(cb.message.last_markup))


# ── обунаи ҳатмӣ ──────────────────────────────────────────────────────
class SubBot(FakeBot):
    """Бот бо аъзогии идорашаванда."""

    def __init__(self, member=True, raise_error=False):
        super().__init__()
        self.member = member
        self.raise_error = raise_error

    async def get_chat_member(self, chat_id, user_id):
        from types import SimpleNamespace

        if self.raise_error:
            raise RuntimeError("бот админ нест")
        return SimpleNamespace(status="member" if self.member else "left")


async def test_no_channels_means_no_gate(db, cfg):
    from shop.subscription import missing_channels

    assert await missing_channels(SubBot(), db, USER_ID) == []


async def test_unsubscribed_user_is_stopped(db, cfg):
    db.add_channel("@test_channel", "Тест", "https://t.me/test_channel")
    guard = GuardMiddleware(db, cfg)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    bot = SubBot(member=False)
    await guard(handler, FakeMessage("/start"), {"bot": bot})
    assert called is False
    assert "обуна" in bot.to(USER_ID)


async def test_subscribed_user_passes(db, cfg):
    db.add_channel("@test_channel", "Тест")
    guard = GuardMiddleware(db, cfg)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    await guard(handler, FakeMessage("/start"), {"bot": SubBot(member=True)})
    assert called is True


async def test_admin_skips_subscription(db, cfg):
    db.add_channel("@test_channel", "Тест")
    guard = GuardMiddleware(db, cfg)
    called = False

    async def handler(event, data):
        nonlocal called
        called = True

    await guard(handler, FakeMessage("/start", user_id=ADMIN_ID), {"bot": SubBot(member=False)})
    assert called is True


async def test_unreachable_channel_does_not_lock_everyone_out(db, cfg):
    """Агар ботро аз канал хориҷ кунанд — харидорон набояд маҳрум шаванд."""
    from shop.subscription import missing_channels

    db.add_channel("@gone", "Нест шуд")
    assert await missing_channels(SubBot(raise_error=True), db, USER_ID) == []


async def test_many_channels_all_required(db, cfg):
    from shop.subscription import missing_channels

    for i in range(5):
        db.add_channel(f"@ch{i}", f"Канал {i}")
    assert len(await missing_channels(SubBot(member=False), db, USER_ID)) == 5


# ── шарҳҳо ────────────────────────────────────────────────────────────
async def test_review_goes_to_admin(db, cfg, state, bot):
    from shop.handlers import reviews as rv

    db.touch_user(USER_ID, "ali", "Alijon")
    await state.set_state(rv.Review.waiting_text)
    message = FakeMessage("Хеле зуд расид, ташаккур!")
    await rv.got_review(message, state, db, cfg, bot)

    rows = db.pending_reviews()
    assert len(rows) == 1 and rows[0]["text"].startswith("Хеле зуд")
    assert "ШАРҲИ НАВ" in bot.to(ADMIN_ID)


async def test_short_review_refused(db, cfg, state, bot):
    from shop.handlers import reviews as rv

    await state.set_state(rv.Review.waiting_text)
    message = FakeMessage("зур")
    await rv.got_review(message, state, db, cfg, bot)
    assert db.pending_reviews() == []
    assert "кӯтоҳ" in message.last


async def test_approved_review_is_published(db, cfg, state, bot):
    from shop.db import REVIEW_PUBLISHED

    db.touch_user(USER_ID, "ali", "Alijon")
    db.set_setting("review_channel", "@reviews")
    review_id = db.create_review(USER_ID, "Ҳамааш аъло буд!")

    cb = FakeCallback(f"a:revok:{review_id}", user_id=ADMIN_ID)
    await admin_h.cb_review_action(cb, db, cfg, bot)

    assert db.review(review_id)["status"] == REVIEW_PUBLISHED
    assert "Шарҳи харидор" in bot.to("@reviews")
    assert "нашр шуд" in bot.to(USER_ID)


async def test_review_not_published_without_channel(db, cfg, state, bot):
    from shop.db import REVIEW_PENDING

    db.touch_user(USER_ID)
    review_id = db.create_review(USER_ID, "Матни шарҳи хуб")
    cb = FakeCallback(f"a:revok:{review_id}", user_id=ADMIN_ID)
    await admin_h.cb_review_action(cb, db, cfg, bot)

    assert db.review(review_id)["status"] == REVIEW_PENDING   # дар навбат мемонад
    assert "гузошта нашудааст" in cb.message.all_text()


async def test_rejected_review_is_not_published(db, cfg, state, bot):
    from shop.db import REVIEW_REJECTED

    db.touch_user(USER_ID)
    db.set_setting("review_channel", "@reviews")
    review_id = db.create_review(USER_ID, "Матни шарҳи хуб")
    cb = FakeCallback(f"a:revno:{review_id}", user_id=ADMIN_ID)
    await admin_h.cb_review_action(cb, db, cfg, bot)

    assert db.review(review_id)["status"] == REVIEW_REJECTED
    assert bot.to("@reviews") == ""


# ── эълон ─────────────────────────────────────────────────────────────
def test_broadcast_buttons_parsed():
    from shop.handlers.settings import parse_buttons

    rows = parse_buttons("Канали мо | https://t.me/almaz\nСайт | https://almaz.tj")
    assert [b.text for row in rows for b in row] == ["Канали мо", "Сайт"]
    assert rows[0][0].url == "https://t.me/almaz"


@pytest.mark.parametrize("raw", ["бе ҳавола", "Ном | not-a-url", "| https://x", ""])
def test_broadcast_bad_buttons_refused(raw):
    from shop.handlers.settings import parse_buttons

    assert parse_buttons(raw) is None


# ── дастгирӣ ва ҳисоб ─────────────────────────────────────────────────
async def test_support_shows_whatsapp(db, cfg, state):
    db.set_setting("whatsapp", "992939880805")
    cb = FakeCallback(keyboards.CB_SUPPORT)
    await menu_h.cb_support(cb, db, cfg)
    assert "992939880805" in cb.message.last
    urls = [b.url for row in cb.message.last_markup.inline_keyboard for b in row if b.url]
    assert any("wa.me/992939880805" in u for u in urls)


async def test_balance_button_shows_history(db, cfg, state):
    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 15000, "topup")
    cb = FakeCallback(keyboards.CB_BALANCE)
    await menu_h.cb_balance(cb, db, cfg)
    assert "150.00" in cb.message.last


async def test_users_screen_counts_money(db, cfg, state):
    from shop.handlers import settings as st

    for uid, amount in ((1, 10000), (2, 5000), (3, 0)):
        db.touch_user(uid)
        if amount:
            db.change_balance(uid, amount, "topup")
    cb = FakeCallback("a:users", user_id=ADMIN_ID)
    await st.cb_users(cb, db, cfg)
    assert "150.00" in cb.message.last     # 100 + 50


# ── реквизитҳо ────────────────────────────────────────────────────────
def _req(db, cfg):
    from shop import requisites

    return requisites.get(db, cfg)


async def test_requisites_start_from_env(db, cfg):
    from shop import requisites

    requisites.seed(db, cfg)
    req = _req(db, cfg)
    assert req.card == cfg.card_number
    assert req.alif_account == cfg.alif_account
    assert req.dc_enabled and req.alif_enabled


async def test_admin_changes_card_and_buyer_sees_it(db, cfg, state):
    from shop.handlers import settings as st

    await st.got_card(FakeMessage("8888 9999 0000 1111", user_id=ADMIN_ID), state, db, cfg)
    await st.got_holder(FakeMessage("ФИРУЗ Н.", user_id=ADMIN_ID), state, db, cfg)

    cb = FakeCallback(keyboards.CB_TOPUP_SUM + "10000")
    await top_h.cb_preset_sum(cb, state, db, cfg)
    text = cb.message.all_text()
    assert "8888 9999 0000 1111" in text
    assert "ФИРУЗ Н." in text
    assert cfg.card_number not in text          # корти кӯҳна дигар нест


async def test_new_card_goes_into_payment_link(db, cfg, state):
    from shop.handlers import settings as st

    await st.got_card(FakeMessage("8888999900001111", user_id=ADMIN_ID), state, db, cfg)
    cb = FakeCallback(keyboards.CB_TOPUP_SUM + "15000")
    await top_h.cb_preset_sum(cb, state, db, cfg)
    urls = [b.url for row in cb.message.last_markup.inline_keyboard for b in row if b.url]
    assert any("A=8888999900001111" in u for u in urls)


async def test_admin_changes_alif_account(db, cfg, state):
    from shop.handlers import settings as st

    await st.got_alif(FakeMessage("900112233", user_id=ADMIN_ID), state, db, cfg)
    cb = FakeCallback(keyboards.CB_TOPUP_SUM + "10000")
    await top_h.cb_preset_sum(cb, state, db, cfg)
    urls = [b.url for row in cb.message.last_markup.inline_keyboard for b in row if b.url]
    assert any("account=900112233" in u for u in urls)


@pytest.mark.parametrize("bad", ["12345", "abcdefghijkl", "1234567890123456789012"])
async def test_bad_card_refused(db, cfg, state, bad):
    from shop import requisites
    from shop.handlers import settings as st

    requisites.seed(db, cfg)
    before = _req(db, cfg).card
    message = FakeMessage(bad, user_id=ADMIN_ID)
    await st.got_card(message, state, db, cfg)
    assert _req(db, cfg).card == before
    assert "нодуруст" in message.last


async def test_disabled_alif_disappears_for_buyer(db, cfg, state):
    from shop import requisites
    from shop.handlers import settings as st

    requisites.seed(db, cfg)
    cb = FakeCallback("a:aliftoggle", user_id=ADMIN_ID)
    await st.cb_toggle_method(cb, db, cfg)
    assert _req(db, cfg).alif_enabled is False

    pay = FakeCallback(keyboards.CB_TOPUP_SUM + "10000")
    await top_h.cb_preset_sum(pay, state, db, cfg)
    urls = [b.url for row in pay.message.last_markup.inline_keyboard for b in row if b.url]
    assert not any("alifmobi" in u for u in urls)
    assert "Alif" not in pay.message.all_text()


async def test_last_method_cannot_be_switched_off(db, cfg, state):
    """Агар ҳарду хомӯш шаванд, харидор пул гузаронида наметавонад."""
    from shop import requisites
    from shop.handlers import settings as st

    requisites.seed(db, cfg)
    await st.cb_toggle_method(FakeCallback("a:aliftoggle", user_id=ADMIN_ID), db, cfg)

    cb = FakeCallback("a:dctoggle", user_id=ADMIN_ID)
    await st.cb_toggle_method(cb, db, cfg)
    assert _req(db, cfg).dc_enabled is True          # хомӯш нашуд
    assert any("ягона" in (a or "") for a in cb.answers)


async def test_requisites_survive_restart(db, cfg, state, tmp_path):
    """Реквизитҳо дар база мемонанд, на дар .env."""
    from shop import requisites
    from shop.db import Database
    from shop.handlers import settings as st

    await st.got_card(FakeMessage("7777888899990000", user_id=ADMIN_ID), state, db, cfg)
    path = db.path
    db.close()

    again = Database(path)
    requisites.seed(again, cfg)                      # оғози нави бот
    assert requisites.get(again, cfg).card == "7777888899990000"
    again.close()


# ── «Дигар бозиҳо» ────────────────────────────────────────────────────
async def test_other_games_hidden_until_enabled(db, cfg, state):
    """Раздел не показывается, пока админ не включил ни одной игры."""
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    assert not _has(message.last_markup, texts.BTN_OTHER)


async def test_other_games_appears_after_enabling(db, cfg, state):
    db.set_group_products_active("mlbb_all", True)
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg)
    labels = _labels(message.last_markup)
    assert texts.BTN_OTHER in labels
    # Строго после PUBG
    assert labels.index(texts.BTN_OTHER) == labels.index(texts.BTN_PUBG) + 1


async def test_one_enabled_game_opens_prices_directly(db, cfg, state):
    """Включена одна игра — лишний экран выбора не нужен."""
    db.set_group_products_active("hok_all", True)
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_OTHER)
    await menu_h.cb_category(cb, state, db, cfg)
    labels = " ".join(_labels(cb.message.last_markup))
    assert "токен" in labels                     # сразу прайс Honor of Kings
    assert "Lattice" not in labels               # чужие игры не попали


async def test_two_enabled_games_show_choice(db, cfg, state):
    db.set_group_products_active("hok_all", True)
    db.set_group_products_active("mr_all", True)
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_OTHER)
    await menu_h.cb_category(cb, state, db, cfg)
    labels = " ".join(_labels(cb.message.last_markup))
    assert "Honor of Kings" in labels and "Marvel Rivals" in labels
    assert "Mobile Legends" not in labels        # выключенная игра не показана


async def test_pubg_still_opens_prices_directly(db, cfg, state):
    """Prime выключен, значит лишнего экрана у PUBG быть не должно."""
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_PUBG)
    await menu_h.cb_category(cb, state, db, cfg)
    assert any("UC —" in x for x in _labels(cb.message.last_markup))


async def test_pubg_shows_groups_when_prime_enabled(db, cfg, state):
    db.set_group_products_active("pubg_extra", True)
    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_PUBG)
    await menu_h.cb_category(cb, state, db, cfg)
    labels = " ".join(_labels(cb.message.last_markup))
    assert "UC" in labels and "Prime" in labels


# ── Mobile Legends: ID + сервер ───────────────────────────────────────
async def test_mlbb_asks_for_id_and_server(db, cfg, state):
    db.set_group_products_active("mlbb_all", True)
    cb = FakeCallback(keyboards.CB_PRODUCT + "mlbb_diamonds_50")
    await buy_h.cb_product(cb, state, db, cfg)
    assert "сервер" in cb.message.last.lower()


async def test_mlbb_refuses_id_without_server(db, cfg, state):
    db.set_group_products_active("mlbb_all", True)
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "mlbb_diamonds_50"), state, db, cfg)
    message = FakeMessage("123456789")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    assert "сервер" in message.last.lower()


async def test_mlbb_accepts_id_and_server(db, cfg, state):
    db.set_group_products_active("mlbb_all", True)
    await buy_h.cb_product(FakeCallback(keyboards.CB_PRODUCT + "mlbb_diamonds_50"), state, db, cfg)
    message = FakeMessage("123456789 1234")
    await buy_h.got_target(message, state, db, cfg, ManualSupplier())
    data = await state.get_data()
    assert data["target"] == "123456789" and data["server"] == "1234"


async def test_server_reaches_supplier(db, cfg_api, state, bot):
    """Сервер обязан дойти до поставщика — иначе заказ уйдёт не туда."""
    seen = {}

    class Watcher(FakeSupplier):
        async def place_order(self, *, kind, sku, target, amount, order_id, server=""):
            seen["target"] = target
            seen["server"] = server
            return OrderResult(ok=True, external_id="FL-9")

    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    row = db.product("mlbb_diamonds_50")
    order_id = db.create_order(
        user_id=USER_ID, product_code="mlbb_diamonds_50", category=row["category"],
        title=row["title"], price=row["price"], target="123456789 (1234)",
        nickname="Tester", sku=row["sku"], kind=row["kind"],
    )
    await deliver_order(bot, db, cfg_api, Watcher(), order_id)
    assert seen == {"target": "123456789", "server": "1234"}


async def test_plain_game_sends_no_server(db, cfg_api, state, bot):
    seen = {}

    class Watcher(FakeSupplier):
        async def place_order(self, *, kind, sku, target, amount, order_id, server=""):
            seen["target"], seen["server"] = target, server
            return OrderResult(ok=True, external_id="FL-9")

    db.touch_user(USER_ID)
    db.change_balance(USER_ID, 50000, "topup")
    order_id = _make_order(db)
    await deliver_order(bot, db, cfg_api, Watcher(), order_id)
    assert seen == {"target": "123456789", "server": ""}


# ── включение раздела админом ─────────────────────────────────────────
async def test_admin_enables_whole_group(db, cfg, state):
    cb = FakeCallback("a:gon:hok_all", user_id=ADMIN_ID)
    await admin_h.cb_group_toggle(cb, db, cfg)
    items = db.group_products("hok_all", only_active=False)
    assert all(i["active"] for i in items)


async def test_admin_disables_whole_group(db, cfg, state):
    db.set_group_products_active("hok_all", True)
    cb = FakeCallback("a:goff:hok_all", user_id=ADMIN_ID)
    await admin_h.cb_group_toggle(cb, db, cfg)
    assert db.group_products("hok_all") == []


async def test_new_games_start_disabled(db):
    """Новые игры не должны продаваться, пока цены не проверены."""
    for code in ("mlbb_diamonds_50", "hok_tokens_80", "bs_gold_100", "mr_lattice_100"):
        assert db.product(code)["active"] == 0, code


async def test_new_games_have_cost_and_margin(db):
    """У каждой новой игры есть закупка, и цена выше неё."""
    from shop.db import price_of

    for code in ("mlbb_diamonds_50", "hok_tokens_80", "bs_gold_100", "mr_lattice_100"):
        row = db.product(code)
        assert row["cost"], code
        in_somoni = round(row["cost"] / 1000 * 11.0 * 100)
        assert row["price"] > in_somoni, f"{code}: цена ниже закупки"


# ── добавление игры из панели ─────────────────────────────────────────
class CatalogSupplier(FakeSupplier):
    """Поставщик с заданным каталогом."""

    def __init__(self, live):
        super().__init__()
        self._live = live

    async def products(self):
        return self._live


FAKE_LIVE = {
    "codm_cp_80": {"name": "Call of Duty 80 CP", "price": 0.99},
    "codm_cp_400": {"name": "Call of Duty 400 CP", "price": 4.50},
    "codm_cp_800": {"name": "Call of Duty 800 CP", "price": 8.90},
    "pubg_uc_60": {"name": "60 UC", "price": 0.886},      # уже есть
    "broken_item": {"name": "Без цены", "price": 0},      # пропустить
}


async def test_panel_lists_only_new_games(db, cfg_api, state):
    from shop.handlers import settings as st

    cb = FakeCallback("a:addgame", user_id=ADMIN_ID)
    await st.cb_add_game(cb, db, cfg_api, CatalogSupplier(FAKE_LIVE))
    labels = " ".join(_labels(cb.message.last_markup))
    assert "codm" in labels
    assert "PUBG" not in labels            # уже продаётся


async def test_panel_adds_whole_game(db, cfg_api, state):
    from shop.handlers import settings as st

    cb = FakeCallback("a:addfam:codm", user_id=ADMIN_ID)
    await st.cb_add_family(cb, db, cfg_api, CatalogSupplier(FAKE_LIVE))

    items = db.group_products("codm_all", only_active=False)
    assert len(items) == 3                                   # три товара CoD
    assert all(i["custom"] for i in items)
    assert all(not i["active"] for i in items)               # выключены
    assert db.group("codm_all") is not None


async def test_added_prices_include_markup(db, cfg_api, state):
    from shop.handlers import settings as st

    db.set_setting("usd_rate", "11")
    db.set_setting("markup_percent", "20")
    cb = FakeCallback("a:addfam:codm", user_id=ADMIN_ID)
    await st.cb_add_family(cb, db, cfg_api, CatalogSupplier(FAKE_LIVE))

    row = db.product("codm_cp_80")          # 0.99 $ × 11 × 1.2 = 13.07 → 13.50
    assert row["cost"] == 990
    assert row["price"] == 1350
    assert row["price"] > round(row["cost"] / 1000 * 11 * 100)   # прибыль есть


async def test_markup_setting_changes_result(db, cfg_api, state):
    from shop.handlers import settings as st

    db.set_setting("usd_rate", "11")
    db.set_setting("markup_percent", "50")
    cb = FakeCallback("a:addfam:codm", user_id=ADMIN_ID)
    await st.cb_add_family(cb, db, cfg_api, CatalogSupplier(FAKE_LIVE))
    assert db.product("codm_cp_80")["price"] == 1650     # 0.99×11×1.5 = 16.34 → 16.50


async def test_adding_twice_does_not_duplicate(db, cfg_api, state):
    from shop.handlers import settings as st

    supplier = CatalogSupplier(FAKE_LIVE)
    cb = FakeCallback("a:addfam:codm", user_id=ADMIN_ID)
    await st.cb_add_family(cb, db, cfg_api, supplier)
    await st.cb_add_family(FakeCallback("a:addfam:codm", user_id=ADMIN_ID), db, cfg_api, supplier)
    assert len(db.group_products("codm_all", only_active=False)) == 3


async def test_added_game_reaches_customer(db, cfg_api, state):
    """Полный путь: добавили из панели → включили → покупатель видит."""
    from shop.handlers import settings as st

    await st.cb_add_family(FakeCallback("a:addfam:codm", user_id=ADMIN_ID),
                           db, cfg_api, CatalogSupplier(FAKE_LIVE))
    message = FakeMessage("/start")
    await menu_h.cmd_start(message, state, db, cfg_api)
    assert not _has(message.last_markup, texts.BTN_OTHER)     # ещё выключено

    db.set_group_products_active("codm_all", True)
    message2 = FakeMessage("/start")
    await menu_h.cmd_start(message2, state, db, cfg_api)
    assert _has(message2.last_markup, texts.BTN_OTHER)

    cb = FakeCallback(keyboards.CB_CAT + catalog.CAT_OTHER)
    await menu_h.cb_category(cb, state, db, cfg_api)
    assert any("CP" in x for x in _labels(cb.message.last_markup))


async def test_added_game_survives_restart(db, cfg_api, state, tmp_path):
    from shop.db import Database
    from shop.handlers import settings as st

    await st.cb_add_family(FakeCallback("a:addfam:codm", user_id=ADMIN_ID),
                           db, cfg_api, CatalogSupplier(FAKE_LIVE))
    db.set_group_products_active("codm_all", True)
    path = db.path
    db.close()

    again = Database(path)                       # перезапуск бота
    assert again.active_count(catalog.CAT_OTHER) == 3
    assert again.product("codm_cp_80") is not None
    again.close()


async def test_bad_markup_refused(db, cfg, state):
    from shop.handlers import settings as st

    message = FakeMessage("абв", user_id=ADMIN_ID)
    await st.got_markup(message, state, db)
    assert "нодуруст" in message.last
