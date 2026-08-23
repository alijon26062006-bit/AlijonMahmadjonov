"""Возврат людей: кнопки там, где человек готов нажать."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import BattleEngine
from core.models import Slot
from services import keyboards, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import enqueue_users, make_config, vote_for

MAIN = -1001111111111


class Bot:
    def __init__(self) -> None:
        self.by_chat: dict[int, list[tuple[str, object]]] = {}
        self._next_id = 100

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.by_chat.setdefault(chat_id, []).append((text, reply_markup))
        self._next_id += 1  # у каждого поста свой id, как в жизни
        return type("M", (), {"message_id": self._next_id})()

    async def edit_message_text(self, **kwargs):
        return None

    def buttons(self, chat_id) -> list[str]:
        return [
            b.text
            for _, markup in self.by_chat.get(chat_id, [])
            if markup is not None
            for row in markup.inline_keyboard
            for b in row
        ]

    def texts(self, chat_id) -> list[str]:
        return [text for text, _ in self.by_chat.get(chat_id, [])]


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "funnel.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=4)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    settings.set("main_channel_id", MAIN)
    bot = Bot()
    return repo, config, settings, bot, BattleEngine(bot, repo, config, settings=settings)


async def play_out(engine, repo, people: int = 4):
    await enqueue_users(engine, repo, people)
    await engine.create_from_queue()
    while repo.current_battle() is not None:
        battle = repo.current_battle()
        for match in repo.open_matches(1, int(battle["round_no"])):
            slots = repo.match_slots(int(match["id"]))
            vote_for(repo, int(match["id"]), slots[0].user_id,
                     range(match["id"] * 100, match["id"] * 100 + 3))
        await engine.close_round(force=True)


def losers(repo, battle_id: int = 1) -> list[int]:
    """Вылетевшие, кроме тех, кто ушёл на паузу призёра.

    Призёру кнопка «в следующий батл» не нужна: он всё равно отдыхает, и
    нажатие дало бы ему отказ. Ему приходит предложение выкупить паузу.
    """
    return [
        uid for uid in range(1, 5)
        if repo.cooldown_for(uid) is None
    ]


# ------------------------------------------------- кнопка после вылета

@pytest.mark.asyncio
async def test_a_knocked_out_player_gets_a_rematch_button(env):
    """Момент вылета — самый горячий: обида свежая, реванша хочется сразу."""
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    for user_id in losers(repo):
        assert any(
            "следующий батл" in label for label in bot.buttons(user_id)
        ), f"вылетевший id{user_id} остался без кнопки"


@pytest.mark.asyncio
async def test_the_rematch_button_leads_to_the_queue(env):
    repo, config, _, _, _ = env
    markup = keyboards.next_battle(config)
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]

    assert actions[0] == "join", "кнопка должна вести на подачу заявки"


@pytest.mark.asyncio
async def test_the_loser_is_also_offered_to_invite(env):
    """Второй способ вернуться в игру — привести друга, а не платить."""
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    assert any("Позвать друзей" in label for label in bot.buttons(losers(repo)[0]))


def test_without_referrals_there_is_no_such_button(env):
    _, config, _, _, _ = env
    markup = keyboards.next_battle(config, referrals=False)

    assert len(markup.inline_keyboard) == 1


@pytest.mark.asyncio
async def test_the_winner_is_not_pushed_to_rejoin(env):
    """Победителю это сообщение ни к чему — он и так на паузе призёра."""
    repo, _, _, bot, engine = env
    await play_out(engine, repo)
    winner = repo.leaderboard(limit=1)[0]["user_id"]
    assert repo.cooldown_for(winner) is not None, "победитель уходит на паузу"

    rematch = [label for label in bot.buttons(winner) if "следующий батл" in label]
    assert not rematch


# ------------------------------------------- итоги батла в главном канале

@pytest.mark.asyncio
async def test_the_final_reaches_the_main_channel(env):
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    finals = [t for t in bot.texts(MAIN) if "З А В Е Р Ш Ё Н" in t]
    assert len(finals) == 1, "итоги должны выйти в витрину ровно один раз"


@pytest.mark.asyncio
async def test_the_final_post_names_winners_and_prizes(env):
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    body = next(t for t in bot.texts(MAIN) if "З А В Е Р Ш Ё Н" in t)
    assert "🥇" in body and "1000⭐" in body


@pytest.mark.asyncio
async def test_the_final_post_invites_to_the_next_battle(env):
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    assert any("частв" in label for label in bot.buttons(MAIN))


@pytest.mark.asyncio
async def test_the_final_post_is_remembered_for_cleanup(env):
    repo, _, _, _, engine = env
    await play_out(engine, repo)

    kinds = [row["kind"] for row in repo.posts(chat_id=MAIN)]
    assert "final" in kinds


@pytest.mark.asyncio
async def test_no_main_channel_does_not_break_the_finish(env):
    repo, _, settings, _, engine = env
    settings.set("main_channel_id", 0)

    await play_out(engine, repo)

    assert repo.current_battle() is None, "батл обязан завершиться штатно"


@pytest.mark.asyncio
async def test_a_dead_main_channel_does_not_break_the_finish(env):
    """Бота выгнали из витрины — итоги всё равно должны подвестись."""
    repo, _, _, bot, engine = env

    async def refuse(chat_id, text, reply_markup=None, **kwargs):
        from aiogram.exceptions import TelegramForbiddenError

        if chat_id == MAIN:
            raise TelegramForbiddenError(method=None, message="bot is not a member")
        return type("M", (), {"message_id": 1})()

    bot.send_message = refuse
    await play_out(engine, repo)

    assert repo.current_battle() is None
    assert repo.leaderboard(limit=1), "победитель всё равно записан"


@pytest.mark.asyncio
async def test_a_finalist_without_a_prize_gets_the_button(env):
    """Вылетел в финале, но приза не взял — значит паузы нет и звать можно."""
    repo, _, settings, bot, engine = env
    settings.set("cooldown_places", 1)  # пауза только победителю
    await play_out(engine, repo)

    winner = repo.leaderboard(limit=1)[0]["user_id"]
    finalists = [uid for uid in range(1, 5) if uid != winner and repo.stats_for(uid)]
    with_button = [
        uid for uid in finalists
        if any("следующий батл" in label for label in bot.buttons(uid))
    ]

    assert len(with_button) == len(finalists), "без паузы кнопка нужна всем вылетевшим"


@pytest.mark.asyncio
async def test_a_prize_winner_is_offered_the_buyout_instead(env):
    """Призёру вместо «записаться» приходит выкуп паузы."""
    repo, _, _, bot, engine = env
    await play_out(engine, repo)

    winner = repo.leaderboard(limit=1)[0]["user_id"]
    labels = bot.buttons(winner)

    assert any("Вернуться сейчас" in label for label in labels)
    assert not any("следующий батл" in label for label in labels)


# ------------------------------------------------------------- сам текст

def test_the_post_lists_the_top_three():
    ranking = [
        Slot(1, "first", 9, 1), Slot(2, "second", 5, 2),
        Slot(3, "third", 3, 3), Slot(4, "fourth", 1, 4),
    ]
    body = texts.battle_finished_post(ranking, ["1000", "500", "250"])

    assert "first" in body and "third" in body
    assert "fourth" not in body, "четвёртое место призов не берёт"


def test_the_post_survives_fewer_prizes_than_places():
    ranking = [Slot(1, "a", 9, 1), Slot(2, "b", 5, 2), Slot(3, "c", 1, 3)]
    body = texts.battle_finished_post(ranking, ["1000"])

    assert "a" in body and "b" in body, "без приза место всё равно называется"


def test_a_text_prize_is_shown_as_is():
    ranking = [Slot(1, "a", 9, 1)]
    body = texts.battle_finished_post(ranking, ["Telegram Premium"])

    assert "Telegram Premium" in body
