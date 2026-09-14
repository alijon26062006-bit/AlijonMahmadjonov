"""Тестҳои мантиқи дӯкон: база, пардохт, матнҳо, санҷиши вуруд."""

import pytest

from shop import catalog, keyboards, payments, texts
from shop.db import (
    Database,
    NotEnoughMoney,
    ORDER_DONE,
    ORDER_NEW,
    ORDER_REJECTED,
    TOPUP_PAID,
    TOPUP_REJECTED,
)
from shop.handlers.common import clean_player_id, clean_username


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "shop.sqlite3")
    yield database
    database.close()


# ── пул ───────────────────────────────────────────────────────────────
def test_money_format():
    assert texts.money(0) == "0.00 с."
    assert texts.money(1250) == "12.50 с."
    assert texts.money(-500) == "-5.00 с."
    assert texts.money(100000) == "1000.00 с."


@pytest.mark.parametrize(
    "raw,expected",
    [("150", 15000), ("99.50", 9950), ("99,5", 9950), ("1 000", 100000)],
)
def test_to_diram_ok(raw, expected):
    assert texts.to_diram(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "-5", "0", "  "])
def test_to_diram_bad(raw):
    assert texts.to_diram(raw) is None


# ── санҷиши вуруди корбар ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("@Alijon_26", "@Alijon_26"),
        ("Alijon_26", "@Alijon_26"),
        ("t.me/Alijon_26", "@Alijon_26"),
        ("https://t.me/Alijon_26", "@Alijon_26"),
    ],
)
def test_clean_username_ok(raw, expected):
    assert clean_username(raw) == expected


@pytest.mark.parametrize("raw", ["", "@ab", "@1abcdef", "@има_рус", "@" + "a" * 40])
def test_clean_username_bad(raw):
    assert clean_username(raw) is None


@pytest.mark.parametrize("raw,expected", [("123456789", "123456789"), (" 1234 5678 ", "12345678")])
def test_clean_player_id_ok(raw, expected):
    assert clean_player_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "abcdefgh", "1234567890123"])
def test_clean_player_id_bad(raw):
    assert clean_player_id(raw) is None


# ── каталог ───────────────────────────────────────────────────────────
def test_every_product_has_known_category():
    for product in catalog.DEFAULT_PRODUCTS:
        assert product.category in catalog.CATEGORY_INFO
        assert product.price > 0


def test_seed_is_idempotent(db):
    before = len(db.products(catalog.CAT_STARS))
    db.seed_products()
    assert len(db.products(catalog.CAT_STARS)) == before


def test_seed_does_not_touch_edited_price(db):
    code = catalog.DEFAULT_PRODUCTS[0].code
    db.set_price(code, 999)
    db.seed_products()
    assert db.product(code)["price"] == 999


def test_inactive_product_hidden(db):
    code = catalog.DEFAULT_PRODUCTS[0].code
    db.set_active(code, False)
    codes = [r["code"] for r in db.products(catalog.CAT_STARS)]
    assert code not in codes
    assert code in [r["code"] for r in db.products(catalog.CAT_STARS, only_active=False)]


# ── ҳисоб ─────────────────────────────────────────────────────────────
def test_balance_up_and_down(db):
    db.touch_user(1, "ali", "Alijon")
    assert db.change_balance(1, 10000, "test") == 10000
    assert db.change_balance(1, -4000, "test") == 6000
    assert db.user(1).balance == 6000


def test_balance_cannot_go_negative(db):
    db.touch_user(1)
    with pytest.raises(NotEnoughMoney):
        db.change_balance(1, -1, "test")
    assert db.user(1).balance == 0


def test_balance_log_records_every_change(db):
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    db.change_balance(1, -1000, "order")
    rows = db.balance_log(1)
    assert [r["delta"] for r in rows] == [-1000, 5000]
    assert rows[0]["balance_after"] == 4000


# ── фармоишҳо ─────────────────────────────────────────────────────────
def _order(db, user_id=1, price=1100):
    return db.create_order(
        user_id=user_id,
        product_code="stars_50",
        category=catalog.CAT_STARS,
        title="50 ⭐️",
        price=price,
        target="@ali",
        nickname=None,
    )


def test_order_takes_money_at_once(db):
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    order_id = _order(db)
    assert db.user(1).balance == 3900
    assert db.order(order_id)["status"] == ORDER_NEW


def test_order_without_money_changes_nothing(db):
    db.touch_user(1)
    db.change_balance(1, 500, "topup")
    with pytest.raises(NotEnoughMoney):
        _order(db)
    assert db.user(1).balance == 500
    assert db.user_orders(1) == []


def test_done_order_counts_as_spent(db):
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    order_id = _order(db)
    db.set_order_status(order_id, ORDER_DONE)
    user = db.user(1)
    assert user.spent == 1100 and user.orders_done == 1
    assert user.balance == 3900


def test_rejected_order_returns_money(db):
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    order_id = _order(db)
    db.set_order_status(order_id, ORDER_REJECTED)
    user = db.user(1)
    assert user.balance == 5000
    assert user.spent == 0


def test_status_change_is_not_repeated(db):
    """Ду маротиба «рад» — пул танҳо як бор бармегардад."""
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    order_id = _order(db)
    db.set_order_status(order_id, ORDER_REJECTED)
    db.set_order_status(order_id, ORDER_REJECTED)
    assert db.user(1).balance == 5000


def test_done_then_rejected_does_not_double_refund(db):
    db.touch_user(1)
    db.change_balance(1, 5000, "topup")
    order_id = _order(db)
    db.set_order_status(order_id, ORDER_DONE)
    db.set_order_status(order_id, ORDER_REJECTED)
    assert db.user(1).balance == 3900  # фармоиши иҷрошуда баргардонида намешавад


def test_open_orders_list(db):
    db.touch_user(1)
    db.change_balance(1, 50000, "topup")
    first, second = _order(db), _order(db)
    db.set_order_status(first, ORDER_DONE)
    assert [r["id"] for r in db.open_orders()] == [second]


# ── пур кардани ҳисоб ─────────────────────────────────────────────────
def test_topup_confirm_adds_money_once(db):
    db.touch_user(1)
    topup_id = db.create_topup(1, 10000, "1234")
    db.confirm_topup(topup_id, admin_id=99)
    db.confirm_topup(topup_id, admin_id=99)
    assert db.user(1).balance == 10000
    assert db.topup(topup_id)["status"] == TOPUP_PAID


def test_rejected_topup_gives_nothing(db):
    db.touch_user(1)
    topup_id = db.create_topup(1, 10000, "1234")
    db.reject_topup(topup_id, admin_id=99)
    assert db.user(1).balance == 0
    assert db.topup(topup_id)["status"] == TOPUP_REJECTED


def test_rejected_topup_cannot_be_confirmed_later(db):
    db.touch_user(1)
    topup_id = db.create_topup(1, 10000, "1234")
    db.reject_topup(topup_id, 99)
    db.confirm_topup(topup_id, 99)
    assert db.user(1).balance == 0


# ── корбарон ──────────────────────────────────────────────────────────
def test_find_user_by_id_and_username(db):
    db.touch_user(777, "Alijon", "Ali")
    assert db.find_user("777").id == 777
    assert db.find_user("@alijon").id == 777
    assert db.find_user("ALIJON").id == 777
    assert db.find_user("нест") is None


def test_touch_keeps_old_name_when_absent(db):
    db.touch_user(1, "ali", "Alijon")
    db.touch_user(1)
    user = db.user(1)
    assert user.username == "ali" and user.first_name == "Alijon"


def test_blocked_user_excluded_from_broadcast(db):
    db.touch_user(1)
    db.touch_user(2)
    db.set_blocked(2, True)
    assert db.all_user_ids() == [1]


def test_top_users_sorted_by_spending(db):
    for uid, spent in ((1, 5000), (2, 20000), (3, 1000)):
        db.touch_user(uid)
        db.change_balance(uid, spent, "topup")
        order_id = _order(db, uid, spent)
        db.set_order_status(order_id, ORDER_DONE)
    assert [u.id for u in db.top_users()] == [2, 1, 3]


def test_stats(db):
    db.touch_user(1)
    db.change_balance(1, 50000, "topup")
    order_id = _order(db)
    db.set_order_status(order_id, ORDER_DONE)
    data = db.stats()
    assert data["users"] == 1
    assert data["orders_done"] == 1
    assert data["revenue"] == 1100


# ── пардохт ───────────────────────────────────────────────────────────
def test_pay_code_is_four_digits():
    for _ in range(50):
        code = payments.make_code()
        assert len(code) == 4 and code.isdigit()


def test_pay_link_fills_placeholders():
    link = payments.build_pay_link(
        "https://dc.tj/pay?card={card}&amount={amount}&comment={comment}",
        card="8888 1234 1234 1234",
        amount=15050,
        comment="4321",
    )
    assert link == "https://dc.tj/pay?card=8888123412341234&amount=150.50&comment=4321"


def test_pay_link_without_template():
    assert payments.build_pay_link("", card="1", amount=1, comment="1") is None


def test_pay_link_with_bad_template():
    assert payments.build_pay_link("{nest}", card="1", amount=1, comment="1") is None


def test_card_format():
    assert payments.format_card("8888123412341234") == "8888 1234 1234 1234"


# ── тугмаҳо ───────────────────────────────────────────────────────────
def test_main_menu_has_all_sections():
    kb = keyboards.main_menu(reviews_url="https://t.me/x")
    labels = " ".join(b.text for row in kb.inline_keyboard for b in row)
    for title in (
        texts.BTN_TELEGRAM, texts.BTN_FF_CIS, texts.BTN_FF_ID,
        texts.BTN_PUBG, texts.BTN_TOPUP,
    ):
        assert title in labels
    assert texts.BTN_ADMIN not in labels


def test_admin_button_only_for_admin():
    kb = keyboards.main_menu(is_admin=True)
    labels = " ".join(b.text for row in kb.inline_keyboard for b in row)
    assert texts.BTN_ADMIN in labels


def test_telegram_submenu_has_stars_and_premium():
    labels = " ".join(b.text for row in keyboards.telegram_menu().inline_keyboard for b in row)
    assert texts.BTN_STARS in labels and texts.BTN_PREMIUM in labels


def test_product_buttons_carry_price(db):
    rows = db.products(catalog.CAT_PREMIUM)
    kb = keyboards.products(rows, catalog.CAT_PREMIUM)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("3 моҳ" in label and "165.00" in label for label in labels)


def test_payment_keyboard_hides_link_when_missing():
    labels = " ".join(b.text for row in keyboards.payment(1, None).inline_keyboard for b in row)
    assert texts.BTN_OPEN_LINK not in labels
    labels = " ".join(b.text for row in keyboards.payment(1, "https://x").inline_keyboard for b in row)
    assert texts.BTN_OPEN_LINK in labels


def test_all_texts_are_tajik_not_russian():
    """Назорат: дар менюи асосӣ калимаҳои русӣ набошанд."""
    russian_words = ("Купить", "Пополнить", "Поддержка", "Отзывы", "Назад", "Баланс")
    all_labels = " ".join(
        b.text for row in keyboards.main_menu().inline_keyboard for b in row
    )
    for word in russian_words:
        assert word not in all_labels


# ── ранги тугмаҳо (майдони style-и Telegram) ──────────────────────────
def _find(markup, text_part: str):
    for row in markup.inline_keyboard:
        for button in row:
            if text_part in button.text:
                return button
    raise AssertionError(f"тугмаи «{text_part}» ёфт нашуд")


def test_topup_button_is_green():
    """Пур кардани ҳисоб — пул ба ҳисоб меояд, пас сабз."""
    from shop import style

    button = _find(keyboards.main_menu(), texts.BTN_TOPUP)
    assert button.style == style.SUCCESS


def test_sections_are_blue():
    from shop import style

    menu = keyboards.main_menu()
    for title in (texts.BTN_TELEGRAM, texts.BTN_FF_CIS, texts.BTN_FF_ID, texts.BTN_PUBG):
        assert _find(menu, title).style == style.PRIMARY


def test_cancel_is_red_everywhere():
    from shop import style

    for markup in (keyboards.cancel_only(), keyboards.confirm_order(), keyboards.confirm_target()):
        assert _find(markup, texts.BTN_CANCEL).style == style.DANGER


def test_pay_and_confirm_are_green():
    from shop import style

    assert _find(keyboards.confirm_order(), texts.BTN_PAY).style == style.SUCCESS
    assert _find(keyboards.confirm_target(), texts.BTN_YES_MINE).style == style.SUCCESS
    assert _find(keyboards.payment(1, None), texts.BTN_PAID).style == style.SUCCESS


def test_admin_approve_green_reject_red():
    from shop import style

    order = keyboards.admin_order(1)
    assert _find(order, texts.ADM_BTN_DONE).style == style.SUCCESS
    assert _find(order, texts.ADM_BTN_REJECT).style == style.DANGER
    topup = keyboards.admin_topup(1)
    assert _find(topup, texts.ADM_BTN_CONFIRM_PAY).style == style.SUCCESS


def test_admin_money_buttons(db):
    from types import SimpleNamespace
    from shop import style

    card = keyboards.admin_user(SimpleNamespace(id=1, is_blocked=False))
    assert _find(card, texts.ADM_BTN_PLUS).style == style.SUCCESS
    assert _find(card, texts.ADM_BTN_MINUS).style == style.DANGER
    assert _find(card, texts.ADM_BTN_BLOCK).style == style.DANGER
    unlocked = keyboards.admin_user(SimpleNamespace(id=1, is_blocked=True))
    assert _find(unlocked, texts.ADM_BTN_UNBLOCK).style == style.SUCCESS


def test_payment_links_are_blue():
    from shop import style

    pay = keyboards.payment(1, "https://dc.tj/x", "https://alif/x")
    assert _find(pay, texts.BTN_OPEN_LINK).style == style.PRIMARY
    assert _find(pay, texts.BTN_OPEN_ALIF).style == style.PRIMARY


def _every_button(*markups):
    for markup in markups:
        for row in markup.inline_keyboard:
            yield from row


def test_no_keyboard_button_uses_link_style():
    """Telegram дар клавиатура танҳо danger/success/primary-ро қабул мекунад.

    Агар «link» ба он ҷо афтад, тамоми паём рад мешавад — ин тест
    чунин хаторо дар реша мегирад.
    """
    from types import SimpleNamespace
    from shop import style

    user = SimpleNamespace(id=1, is_blocked=False)
    everything = (
        keyboards.main_menu(is_admin=True, reviews_url="https://t.me/x"),
        keyboards.telegram_menu(),
        keyboards.cancel_only(),
        keyboards.confirm_target(),
        keyboards.confirm_order(),
        keyboards.need_money(),
        keyboards.topup_menu((1000, 2000)),
        keyboards.payment(1, "https://a", "https://b"),
        keyboards.back_home(),
        keyboards.support("user"),
        keyboards.admin_home(),
        keyboards.admin_back(),
        keyboards.admin_user(user),
        keyboards.admin_order(1),
        keyboards.admin_topup(1),
        keyboards.admin_price_categories(),
        keyboards.admin_price_item("stars_50", True),
        keyboards.admin_price_item("stars_50", False),
    )
    for button in _every_button(*everything):
        assert button.style in (None, style.SUCCESS, style.DANGER, style.PRIMARY), (
            f"тугмаи «{button.text}» ранги мамнӯъ дорад: {button.style}"
        )


def test_pick_drops_forbidden_style():
    from shop import style

    assert style.pick(style.LINK) is None          # барои клавиатура мамнӯъ
    assert style.pick(style.SUCCESS) == style.SUCCESS


def test_strip_removes_all_colors():
    from shop import style

    menu = keyboards.main_menu()
    assert any(b.style for b in _every_button(menu))
    assert style.strip(menu) is True
    assert all(b.style is None for b in _every_button(menu))
    assert style.strip(menu) is False              # дуюм бор чизе намемонад


def test_colors_can_be_switched_off():
    """SHOP_BUTTON_COLORS=0 — ҳамаи рангҳо хомӯш мешаванд."""
    from shop import style

    style.set_enabled(False)
    try:
        assert _find(keyboards.main_menu(), texts.BTN_TOPUP).style is None
        assert _find(keyboards.confirm_order(), texts.BTN_CANCEL).style is None
    finally:
        style.set_enabled(True)


def test_style_values_are_what_telegram_accepts():
    from shop import style

    assert {style.SUCCESS, style.DANGER, style.PRIMARY, style.LINK} == {
        "success", "danger", "primary", "link"
    }


def test_no_bottom_keyboard_left():
    """Клавиатураи поёнӣ тамоман хориҷ шуд."""
    assert not hasattr(keyboards, "persistent_menu")


# ── фарогирии ранг ───────────────────────────────────────────────────
NEUTRAL = ("◀️", "🏠")  # танҳо тугмаҳои роҳнамоӣ бе ранг мемонанд


def test_every_action_button_has_a_color():
    """Ҳар тугмаи амал бояд ранг дошта бошад — ба ғайр аз роҳнамоӣ."""
    from types import SimpleNamespace

    user = SimpleNamespace(id=1, is_blocked=False)
    everything = (
        keyboards.main_menu(is_admin=True, reviews_url="https://t.me/x"),
        keyboards.telegram_menu(),
        keyboards.cancel_only(),
        keyboards.confirm_target(),
        keyboards.confirm_order(),
        keyboards.need_money(),
        keyboards.topup_menu((1000, 2000)),
        keyboards.payment(1, "https://a", "https://b"),
        keyboards.support("user"),
        keyboards.admin_home(),
        keyboards.admin_user(user),
        keyboards.admin_order(1),
        keyboards.admin_topup(1),
        keyboards.admin_price_categories(),
        keyboards.admin_price_item("stars_50", True),
    )
    colorless = [
        b.text
        for b in _every_button(*everything)
        if b.style is None and not b.text.startswith(NEUTRAL)
    ]
    assert not colorless, f"бе ранг мондаанд: {colorless}"


def test_navigation_stays_neutral():
    """Роҳнамоӣ бе ранг — то тугмаҳои амал фарқ кунанд."""
    home = _find(keyboards.back_home(), texts.BTN_HOME)
    assert home.style is None


def test_product_list_is_blue(db):
    from shop import style

    rows = db.products(catalog.CAT_PUBG)
    for button in _every_button(keyboards.products(rows, catalog.CAT_PUBG)):
        if not button.text.startswith(NEUTRAL):
            assert button.style == style.PRIMARY, button.text


def test_topup_amounts_are_green():
    from shop import style

    kb = keyboards.topup_menu((2000, 5000, 10000))
    greens = [b for b in _every_button(kb) if b.style == style.SUCCESS]
    assert len(greens) == 3


def test_disabled_product_is_red_for_admin(db):
    from shop import style

    db.set_active("stars_50", False)
    rows = db.products(catalog.CAT_STARS, only_active=False)
    kb = keyboards.admin_price_list(rows)
    off = _find(kb, "50 Stars")
    assert off.style == style.DANGER


def test_no_emoji_markers_left():
    """Доираҳои 🟢🔴 аз матни тугмаҳо тамоман бардошта шуданд."""
    kb = keyboards.main_menu(is_admin=True)
    for button in _every_button(kb, keyboards.confirm_order(), keyboards.cancel_only()):
        assert "🟢" not in button.text and "🔴" not in button.text


# ── нархҳои шарикӣ: рӯйхати тасдиқшудаи соҳиби дӯкон ──────────────────
PARTNER_PRICE_LIST = [
    ("ffcis_110", 840), ("ffcis_341", 2500), ("ffcis_572", 4250),
    ("ffcis_1166", 8600), ("ffcis_2398", 17000), ("ffcis_6160", 41400),
    ("ffcis_week", 1620), ("ffcis_month", 5900), ("ffcis_week_lite", 450),
    ("pubg_60", 960), ("pubg_325", 4780), ("pubg_660", 9200),
    ("pubg_1800", 23500), ("pubg_3850", 44000), ("pubg_8100", 86500),
    ("pubg_16200", 167000), ("pubg_24300", 265000),
    ("pubg_32400", 365000), ("pubg_40500", 445000),
]


@pytest.mark.parametrize("code,expected", PARTNER_PRICE_LIST)
def test_partner_price_matches_owner_list(db, code, expected):
    """Ҳар нарх маҳз ҳамон аст, ки соҳиби дӯкон тасдиқ кардааст."""
    from shop.db import price_of

    row = db.product(code)
    assert row is not None, f"моли {code} дар каталог нест"
    assert row["partner_price"] == expected
    assert price_of(row, True) == expected      # шарик маҳз инро мепардозад
    assert price_of(row, False) == row["price"]  # оддӣ — нархи пурра


def test_partner_price_is_always_cheaper(db):
    for code, _ in PARTNER_PRICE_LIST:
        row = db.product(code)
        assert row["partner_price"] < row["price"], code


def test_old_database_gets_partner_prices(tmp_path):
    """Базае, ки то ин навсозӣ сохта шудааст, нархи шарикиро мегирад."""
    import sqlite3

    from shop.db import Database

    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE products (code TEXT PRIMARY KEY, category TEXT NOT NULL, "
        "title TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL, "
        "sku TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'game', "
        "sort INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);"
        "INSERT INTO products(code,category,title,amount,price,sku,kind,sort) VALUES "
        "('pubg_660','pubg','600 + 60 UC',660,9370,'pubg_uc_660','game',0);"
    )
    con.commit()
    con.close()

    upgraded = Database(path)
    assert upgraded.product("pubg_660")["partner_price"] == 9200
    upgraded.close()


def test_cleared_partner_price_does_not_come_back(tmp_path):
    """Админ нархро бардошт — пас аз азнавоғозкунӣ барнагардад."""
    from shop.db import Database

    path = tmp_path / "shop.sqlite3"
    first = Database(path)
    assert first.product("pubg_660")["partner_price"] == 9200
    first.set_partner_price("pubg_660", None)
    first.close()

    second = Database(path)
    assert second.product("pubg_660")["partner_price"] is None
    second.set_partner_price("pubg_660", 8500)
    second.close()

    third = Database(path)
    assert third.product("pubg_660")["partner_price"] == 8500
    third.close()
