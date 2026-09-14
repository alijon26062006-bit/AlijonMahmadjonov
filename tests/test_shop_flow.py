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
    """Аломати ранга ба матн илова мешавад, пас муқоисаи қисмӣ мекунем."""
    return any(title in label for label in _labels(markup))


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
        async def check(self, *, kind, sku, target, amount):
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

    async def check(self, *, kind, sku, target, amount):
        return CheckResult(target=target, nickname="Tester")

    async def place_order(self, *, kind, sku, target, amount, order_id):
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
