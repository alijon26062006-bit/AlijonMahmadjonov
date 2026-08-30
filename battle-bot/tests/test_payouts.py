"""Выплаты призов и зал славы.

Обещанные призы ничего не стоят, выплаченные — стоят всего.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import panel_ui, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

WINNER, SECOND = 101, 102


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "payouts.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[9])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("prizes", ["1000", "500", "250"])

    repo.upsert_user(WINNER, "first", "Первый")
    repo.upsert_user(SECOND, "second", "Второй")
    battle_id = repo.create_battle(datetime.now() + timedelta(hours=1))
    repo.add_participant(battle_id, WINNER, "first")
    repo.add_participant(battle_id, SECOND, "second")
    repo.set_place(battle_id, WINNER, 1)
    repo.set_place(battle_id, SECOND, 2)
    from core.models import BattleStatus

    repo.close_battle(battle_id, BattleStatus.FINISHED)
    return repo, settings, battle_id


# ------------------------------------------------------------- кто ждёт

def test_winners_wait_until_they_are_paid(env):
    repo, _, battle_id = env

    waiting = repo.unpaid_winners(3)
    assert [int(row["user_id"]) for row in waiting] == [WINNER, SECOND]

    repo.record_payout(battle_id, WINNER, 1, "1000", "photo-1")

    assert [int(row["user_id"]) for row in repo.unpaid_winners(3)] == [SECOND]


def test_only_prize_places_are_listed(env):
    """Призов два — ждут двое, четвёртое место ничего не ждёт."""
    repo, _, _ = env

    assert len(repo.unpaid_winners(1)) == 1


def test_an_unfinished_battle_is_not_in_the_list(tmp_path):
    path = str(tmp_path / "live.db")
    repo = Repo(connect(path))
    repo.upsert_user(WINNER, "first", "Первый")
    battle_id = repo.create_battle(datetime.now() + timedelta(hours=1))
    repo.add_participant(battle_id, WINNER, "first")
    repo.set_place(battle_id, WINNER, 1)

    assert repo.unpaid_winners(3) == []


# ------------------------------------------------------------- выплата

def test_a_prize_is_paid_once(env):
    """Два админа нажали одновременно — выплата записывается один раз."""
    repo, _, battle_id = env

    assert repo.record_payout(battle_id, WINNER, 1, "1000", "photo-1") is True
    assert repo.record_payout(battle_id, WINNER, 1, "1000", "photo-2") is False
    assert repo.payout_count() == 1


def test_the_post_id_is_remembered(env):
    repo, _, battle_id = env
    repo.record_payout(battle_id, WINNER, 1, "1000", "photo-1")

    repo.set_payout_post(battle_id, WINNER, 777)

    assert int(repo.payouts()[0]["message_id"]) == 777


# ------------------------------------------------------------- зал славы

def test_the_hall_names_everyone_paid(env):
    repo, _, battle_id = env
    repo.record_payout(battle_id, WINNER, 1, "1000", "photo-1")
    repo.record_payout(battle_id, SECOND, 2, "Telegram Premium", "photo-2")

    body = texts.hall_of_fame(repo.payouts())

    assert "@first" in body and "@second" in body
    assert "1000⭐" in body, "число показывается звёздами"
    assert "Telegram Premium" in body, "текстовый приз — как есть"


def test_an_empty_hall_does_not_look_broken():
    assert "Пока пусто" in texts.hall_of_fame([])


def test_a_prize_with_html_is_escaped(env):
    """Приз пишет админ — в зале славы он не должен ломать разметку."""
    repo, _, battle_id = env
    repo.record_payout(battle_id, WINNER, 1, "<b>взлом</b>", "photo-1")

    body = texts.hall_of_fame(repo.payouts())

    assert "&lt;b&gt;взлом&lt;/b&gt;" in body


# ------------------------------------------------------------- панель

def test_the_panel_shows_who_is_waiting(env):
    repo, settings, _ = env

    text, markup = panel_ui.payouts(repo.unpaid_winners(3), repo.payouts(5), 0)

    assert "Ждут приз" in text
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert any(action.startswith("p:pays:do:") for action in actions)


def test_the_panel_says_when_nobody_waits(env):
    repo, _, battle_id = env
    repo.record_payout(battle_id, WINNER, 1, "1000")
    repo.record_payout(battle_id, SECOND, 2, "500")

    text, _ = panel_ui.payouts(repo.unpaid_winners(3), repo.payouts(5), 2)

    assert "все призы выплачены" in text


def test_the_admin_is_reminded_after_the_final():
    from core.models import Slot

    body = texts.pay_the_winners(12, [Slot(1, "first", 0, 1), Slot(2, "second", 0, 2)])

    assert "#12" in body and "@first" in body
    assert "Выплаты" in body, "админу говорят, куда идти"
