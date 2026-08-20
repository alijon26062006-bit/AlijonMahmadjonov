"""«Вас обошли»: приходит вовремя, никого не спамит."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Slot
from services import nudges
from storage.db import connect
from storage.repo import Repo
from tests.test_engine import make_config


class Bot:
    def __init__(self) -> None:
        self.sent: dict[int, list[str]] = {}

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        self.sent.setdefault(chat_id, []).append(text)


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "nudge.db")
    repo = Repo(connect(path))
    for user_id in (1, 2, 3):
        repo.upsert_user(user_id, f"nick{user_id}", "N")
    return Bot(), repo, make_config(db_path=path)


def board(*pairs) -> list[Slot]:
    return [Slot(user_id, f"nick{user_id}", votes) for user_id, votes in pairs]


# ------------------------------------------------------------- кто лидер

def test_the_leader_is_the_one_in_front():
    assert nudges.leader(board((1, 5), (2, 3))).user_id == 1


def test_a_tie_has_no_leader():
    """При равном счёте обходить ещё некого."""
    assert nudges.leader(board((1, 3), (2, 3))) is None


def test_zero_votes_have_no_leader():
    assert nudges.leader(board((1, 0), (2, 0))) is None
    assert nudges.leader([]) is None


# --------------------------------------------------------- само сообщение

@pytest.mark.asyncio
async def test_the_one_who_lost_the_lead_is_told(env):
    bot, repo, config = env

    overtaken = await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )

    assert overtaken == 1
    letter = "".join(bot.sent[1])
    assert "Вас обошли" in letter
    assert "@nick2" in letter, "видно, кто обошёл"
    assert "<b>6</b>" in letter and "<b>5</b>" in letter, "видно счёт"
    assert "Разрыв" in letter


@pytest.mark.asyncio
async def test_the_new_leader_is_congratulated(env):
    bot, repo, config = env

    await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )

    assert "вырвались вперёд" in "".join(bot.sent[2])


@pytest.mark.asyncio
async def test_the_message_carries_the_call_to_action(env):
    """Смысл сообщения — чтобы человек пошёл звать своих, значит нужны кнопки."""
    bot, repo, config = env

    await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )

    assert "Позовите своих" in "".join(bot.sent[1])


# ------------------------------------------------------------ без спама

@pytest.mark.asyncio
async def test_nothing_is_sent_when_the_leader_did_not_change(env):
    bot, repo, config = env

    result = await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 6), (2, 3))
    )

    assert result is None and bot.sent == {}


@pytest.mark.asyncio
async def test_nothing_is_sent_on_the_very_first_vote(env):
    """Пока лидера не было, обходить некого."""
    bot, repo, config = env

    result = await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 0), (2, 0)), board((1, 1), (2, 0))
    )

    assert result is None and bot.sent == {}


@pytest.mark.asyncio
async def test_a_shootout_does_not_turn_into_spam(env):
    """Лидер меняется туда-сюда — человек не должен получить десять сообщений."""
    bot, repo, config = env

    await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )
    for _ in range(5):
        await nudges.notify_lead_change(
            bot, repo, config, 7, board((1, 5), (2, 6)), board((1, 7), (2, 6))
        )
        await nudges.notify_lead_change(
            bot, repo, config, 7, board((1, 7), (2, 6)), board((1, 7), (2, 8))
        )

    assert len(bot.sent[1]) == 1, "первому — одно сообщение за паузу"


@pytest.mark.asyncio
async def test_different_matches_are_counted_separately(env):
    bot, repo, config = env

    await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )
    await nudges.notify_lead_change(
        bot, repo, config, 8, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )

    assert len(bot.sent[1]) == 2, "в разных матчах предупреждаем отдельно"


def test_the_cooldown_is_per_person_and_match(env):
    _, repo, _ = env

    assert repo.can_nudge(7, 1) is True
    assert repo.can_nudge(7, 1) is False, "второй раз подряд — нет"
    assert repo.can_nudge(7, 2) is True, "другому человеку — можно"
    assert repo.can_nudge(8, 1) is True, "в другом матче — можно"


@pytest.mark.asyncio
async def test_a_blocked_user_is_marked_and_does_not_break_the_rest(env):
    bot, repo, config = env

    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage

    class Blocked(Bot):
        async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
            if chat_id == 1:
                raise TelegramForbiddenError(
                    method=SendMessage(chat_id=1, text="t"), message="bot was blocked"
                )
            await super().send_message(chat_id, text, reply_markup, **kwargs)

    bot = Blocked()
    await nudges.notify_lead_change(
        bot, repo, config, 7, board((1, 5), (2, 3)), board((1, 5), (2, 6))
    )

    assert repo.get_user(1)["is_blocked"] == 1
    assert bot.sent.get(2), "второй участник всё равно получил своё"
