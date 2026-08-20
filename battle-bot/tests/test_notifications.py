"""Уведомления по итогам: каждый узнаёт свой результат, соперников и счёт."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import BattleEngine
from core.models import Slot, VoteSource
from services import texts
from storage.db import connect
from storage.repo import Repo
from tests.test_engine import FakeBot, join_users, make_config


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "notify.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path)
    bot = FakeBot()
    return bot, repo, BattleEngine(bot, repo, config)


def plain(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def inbox(bot: FakeBot, user_id: int) -> str:
    return plain("".join(bot.direct.get(user_id, [])))


# --------------------------------------------------- содержание письма

def test_the_winner_sees_the_whole_board():
    pair = [Slot(1, "winner", 12, 1), Slot(2, "loser", 7, 2)]
    body = plain(texts.match_result_dm(pair, 1, 1, False, True, False))

    assert "Вы прошли дальше" in body
    assert "@winner" in body and "@loser" in body, "соперник должен быть виден"
    assert "12 голосов" in body and "7 голосов" in body, "счёт обоих"
    assert "63%" in body and "37%" in body
    assert "← вы" in body


def test_the_loser_sees_exactly_the_same_numbers():
    """Обе стороны получают одну и ту же таблицу — скрывать нечего."""
    pair = [Slot(1, "winner", 12, 1), Slot(2, "loser", 7, 2)]
    winner_view = plain(texts.match_result_dm(pair, 1, 1, False, True, False))
    loser_view = plain(texts.match_result_dm(pair, 2, 1, False, False, False))

    for fragment in ("@winner", "@loser", "12 голосов", "7 голосов", "Всего голосов: 19"):
        assert fragment in winner_view and fragment in loser_view

    assert "Вы выбываете" in loser_view
    assert "Не расстраивайтесь" in loser_view


def test_the_you_marker_stands_next_to_the_right_person():
    pair = [Slot(1, "winner", 12, 1), Slot(2, "loser", 7, 2)]
    loser_view = plain(texts.match_result_dm(pair, 2, 1, False, False, False))

    lines = [line for line in loser_view.splitlines() if "@" in line]
    assert "← вы" in [line for line in lines if "@loser" in line][0]
    assert "← вы" not in [line for line in lines if "@winner" in line][0]


def test_a_coin_flip_is_disclosed():
    pair = [Slot(1, "a", 5, 1), Slot(2, "b", 5, 2)]
    body = plain(texts.match_result_dm(pair, 2, 1, False, False, True))

    assert "жребием" in body, "решение жребием нельзя скрывать от проигравшего"


def test_the_final_shows_places_and_medals():
    board = [Slot(1, "first", 40, 1), Slot(2, "second", 25, 2), Slot(3, "third", 10, 3)]
    view = plain(texts.match_result_dm(board, 2, 0, True, False, False))

    assert view.splitlines()[0].startswith("🥈"), "в заголовке — медаль получателя"

    board = view.split("итог", 1)[1]  # сама таблица идёт после заголовка
    assert board.index("🥇") < board.index("🥈") < board.index("🥉")
    assert "@first" in board and "@second" in board and "@third" in board


def test_a_group_of_four_shows_everyone():
    board = [Slot(i, f"n{i}", 40 - i * 10, i) for i in range(1, 5)]
    view = plain(texts.match_result_dm(board, 4, 2, False, False, False))

    for i in range(1, 5):
        assert f"@n{i}" in view, "в группе должны быть видны все четверо"


# ------------------------------------------------ доставка в бою

@pytest.mark.asyncio
async def test_everyone_in_a_pair_gets_their_result(env):
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(1, 901, 1, VoteSource.FREE)
    repo.add_vote(2, 902, 3, VoteSource.FREE)

    await engine.close_round()

    assert "Вы прошли дальше" in inbox(bot, 1)
    assert "Вы выбываете" in inbox(bot, 2)
    assert "Вы прошли дальше" in inbox(bot, 3)
    assert "Вы выбываете" in inbox(bot, 4)


@pytest.mark.asyncio
async def test_the_loser_learns_who_beat_them_and_by_how_much(env):
    bot, repo, engine = env
    await join_users(engine, repo, 2)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(1, 901, 1, VoteSource.FREE)

    await engine.close_round()

    letter = inbox(bot, 2)
    assert "@nick1" in letter, "имя победителя"
    assert "2 голоса" in letter, "его счёт"
    assert "0 голосов" in letter, "свой счёт"


@pytest.mark.asyncio
async def test_nobody_is_left_without_a_result(env):
    """Ни один участник батла не должен остаться без уведомления."""
    bot, repo, engine = env
    await join_users(engine, repo, 8)

    for match_id in (1, 2, 3, 4):
        repo.add_vote(match_id, 900 + match_id, match_id * 2 - 1, VoteSource.FREE)

    await engine.close_round()

    for user_id in range(1, 9):
        letter = inbox(bot, user_id)
        assert letter, f"участник {user_id} не получил ничего"
        assert ("Вы прошли дальше" in letter) or ("Вы выбываете" in letter), (
            f"участник {user_id} не узнал свой результат"
        )


@pytest.mark.asyncio
async def test_a_result_arrives_once_per_match(env):
    bot, repo, engine = env
    await join_users(engine, repo, 2)
    repo.add_vote(1, 900, 1, VoteSource.FREE)

    await engine.close_round()

    letters = bot.direct[2]
    outcomes = [text for text in letters if "Вы выбываете" in plain(text)]
    assert len(outcomes) == 1, "итог матча приходит ровно один раз"


@pytest.mark.asyncio
async def test_finalists_get_the_board_and_the_winner_gets_the_prize(env):
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)
    await engine.close_round()

    final_id = int(repo.open_matches(1, 2)[0]["id"])
    repo.add_vote(final_id, 902, 1, VoteSource.FREE)
    repo.add_vote(final_id, 903, 1, VoteSource.FREE)
    repo.add_vote(final_id, 904, 3, VoteSource.FREE)
    await engine.close_round()

    champion, runner_up = inbox(bot, 1), inbox(bot, 3)

    assert "1 место" in champion and "1000⭐" in champion
    assert "2 место" in runner_up
    assert "@nick3" in champion, "чемпион видит соперника"
    assert "@nick1" in runner_up, "второе место видит чемпиона"
    assert "500⭐" in runner_up, "приз за второе место"


@pytest.mark.asyncio
async def test_the_one_left_without_a_rival_is_told_so(env):
    bot, repo, engine = env
    await join_users(engine, repo, 3)
    repo.add_vote(1, 900, 1, VoteSource.FREE)

    await engine.close_round()

    assert "без боя" in inbox(bot, 3)
    assert "Вы выбываете" not in inbox(bot, 3)


# ------------------------------------------- кнопки следующего раунда

@pytest.mark.asyncio
async def test_advancing_players_get_buttons_for_the_new_match(env):
    """Перейдя в следующий раунд, человек сразу видит новых соперников и кнопки."""
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)

    await engine.close_round()

    letters = "".join(bot.direct[1])
    assert "Вы прошли дальше" in plain(letters)
    assert "@nick3" in letters, "новый соперник назван"

    links_on_buttons = [b.url for b in bot.buttons(1) if b.url]
    assert any("start=v3" in (link or "") for link in links_on_buttons), (
        "должна быть кнопка на новый матч, а не на прошлый"
    )


@pytest.mark.asyncio
async def test_a_group_round_lists_all_the_new_rivals(env):
    bot, repo, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)

    await engine.close_round()

    letters = plain("".join(bot.direct[1]))
    assert "Против вас" in letters
