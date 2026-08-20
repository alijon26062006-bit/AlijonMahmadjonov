"""Покупка голосов: подсчёт суммы, границы и второй способ — друзья."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import payments
from services import keyboards, texts
from services.validation import InputError, as_int
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "buy.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("vote_price", 5)
    return repo, config, settings


# ------------------------------------------------------------- подсчёт

@pytest.mark.parametrize("votes,price,total", [(1, 5, 5), (10, 5, 50), (3, 15, 45), (7, 1, 7)])
def test_the_total_is_votes_times_price(votes, price, total):
    body = texts.buy_confirm(votes, price)
    assert f"<b>{total}⭐</b>" in body
    assert f"<b>{votes}</b>" in body


def test_the_screen_shows_the_price_per_vote(env):
    _, _, settings = env
    body = texts.buy_screen(price=5, balance=2, stars_link="", max_votes=500)

    assert "1 голос = 5⭐" in body
    assert "Введите количество голосов" in body
    assert "от 1 до 500" in body


def test_the_cheap_stars_line_appears_only_when_a_link_is_set():
    with_link = texts.buy_screen(5, 0, "https://t.me/stars", 500)
    without = texts.buy_screen(5, 0, "", 500)

    assert 'href="https://t.me/stars"' in with_link and "тут" in with_link
    assert "Звёзды по низкой цене" not in without


# -------------------------------------------------------------- границы

def test_one_invoice_cannot_exceed_the_telegram_limit():
    """Telegram не принимает счёт дороже 2500⭐ — количество ограничено ценой."""
    assert payments.max_votes(5) == 500
    assert payments.max_votes(1) == 2500
    assert payments.max_votes(2500) == 1
    assert payments.max_votes(9999) == 1, "хотя бы один голос купить можно всегда"


@pytest.mark.parametrize("raw", ["0", "-3", "501", "много", "", "5.5"])
def test_a_bad_amount_is_explained(raw):
    with pytest.raises(InputError):
        as_int(raw, minimum=1, maximum=500, example="5")


@pytest.mark.parametrize("raw,expected", [("5", 5), (" 10 ", 10), ("1", 1), ("500", 500)])
def test_a_good_amount_passes(raw, expected):
    assert as_int(raw, minimum=1, maximum=500, example="5") == expected


# ------------------------------------------------------------- клавиатура

def test_quick_amounts_show_their_price(env):
    markup = keyboards.buy(price=5, referrals_on=True, max_votes=500)
    quick = markup.inline_keyboard[0]

    assert [b.text for b in quick] == ["1 — 5⭐", "5 — 25⭐", "10 — 50⭐"]
    assert all(b.callback_data.startswith("buy:") for b in quick)


def test_invite_is_offered_as_the_second_way(env):
    markup = keyboards.buy(price=5, referrals_on=True, max_votes=500)
    labels = [b.text for row in markup.inline_keyboard for b in row]

    assert any("друзей" in label for label in labels), "второй способ — позвать друзей"


def test_invite_button_disappears_when_referrals_are_off(env):
    markup = keyboards.buy(price=5, referrals_on=False, max_votes=500)
    labels = [b.text for row in markup.inline_keyboard for b in row]

    assert not any("друзей" in label for label in labels)


def test_quick_amounts_never_exceed_the_limit():
    """При дорогой цене крупные кнопки не должны предлагать неоплачиваемый счёт."""
    markup = keyboards.buy(price=2500, referrals_on=False, max_votes=1)
    quick = [b for row in markup.inline_keyboard for b in row]

    assert [b.text for b in quick] == ["1 — 2500⭐"]


def test_pay_button_shows_the_total():
    markup = keyboards.pay(votes=10, total=50)
    assert markup.inline_keyboard[0][0].text == "Оплатить 50⭐"
    assert markup.inline_keyboard[0][0].callback_data == "buy:10"


# ------------------------------------------------------------------ меню

def test_the_main_menu_no_longer_carries_the_invite_button(env):
    """Приглашения переехали внутрь покупки — в меню их быть не должно."""
    _, config, _ = env
    menu = keyboards.main_menu(config)
    labels = [b.text for row in menu.keyboard for b in row]

    assert not any("Пригласить" in label for label in labels)
    assert any("Купить голоса" in label for label in labels)


def test_price_changed_in_the_panel_reaches_the_buy_screen(env):
    repo, config, settings = env
    settings.set("vote_price", 7)

    assert settings.vote_price == 7
    assert "1 голос = 7⭐" in texts.buy_screen(settings.vote_price, 0, "", 357)
    assert texts.buy_confirm(3, settings.vote_price).count("21⭐") == 1
