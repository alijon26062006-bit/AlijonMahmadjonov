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
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert texts.BTN_TELEGRAM in labels
    assert texts.BTN_FF_CIS in labels
    assert texts.BTN_FF_ID in labels
    assert texts.BTN_PUBG in labels
    assert texts.BTN_TOPUP in labels
    assert texts.BTN_ADMIN not in labels


def test_admin_button_only_for_admin():
    kb = keyboards.main_menu(is_admin=True)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert texts.BTN_ADMIN in labels


def test_telegram_submenu_has_stars_and_premium():
    labels = [b.text for row in keyboards.telegram_menu().inline_keyboard for b in row]
    assert texts.BTN_STARS in labels and texts.BTN_PREMIUM in labels


def test_product_buttons_carry_price(db):
    rows = db.products(catalog.CAT_PREMIUM)
    kb = keyboards.products(rows, catalog.CAT_PREMIUM)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("3 моҳ" in label and "165.00" in label for label in labels)


def test_payment_keyboard_hides_link_when_missing():
    labels = [b.text for row in keyboards.payment(1, None).inline_keyboard for b in row]
    assert texts.BTN_OPEN_LINK not in labels
    labels = [b.text for row in keyboards.payment(1, "https://x").inline_keyboard for b in row]
    assert texts.BTN_OPEN_LINK in labels


def test_all_texts_are_tajik_not_russian():
    """Назорат: дар менюи асосӣ калимаҳои русӣ набошанд."""
    russian_words = ("Купить", "Пополнить", "Поддержка", "Отзывы", "Назад", "Баланс")
    all_labels = " ".join(
        b.text for row in keyboards.main_menu().inline_keyboard for b in row
    )
    for word in russian_words:
        assert word not in all_labels
