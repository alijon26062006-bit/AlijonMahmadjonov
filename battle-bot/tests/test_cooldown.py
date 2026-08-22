"""Пауза призёрам: три дня отдыха или выкуп за звёзды."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.engine import BattleEngine
from core.models import Slot
from handlers import panel, payments, start
from services import panel_ui, texts
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, enqueue_users, make_config, vote_for


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "rest.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[99])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    bot = FakeBot()
    return repo, config, settings, bot, BattleEngine(bot, repo, config, settings=settings)


async def run_whole_battle(engine, repo, people: int = 4):
    """Довести батл до финала и вернуть итоговую тройку."""
    await enqueue_users(engine, repo, people)
    await engine.create_from_queue()
    while repo.current_battle() is not None:
        battle = repo.current_battle()
        round_no = int(battle["round_no"])
        for match in repo.open_matches(1, round_no):
            slots = repo.match_slots(int(match["id"]))
            vote_for(repo, int(match["id"]), slots[0].user_id,
                     range(match["id"] * 100, match["id"] * 100 + 3))
        await engine.close_round(force=True)


# ------------------------------------------------------- настройки правила

def test_the_defaults_match_the_agreement(env):
    _, _, settings, _, _ = env
    assert settings.get("cooldown_days") == 3
    assert settings.get("cooldown_places") == 3
    assert settings.get("cooldown_skip_price") == 50


# ---------------------------------------------------------- пауза в финале

@pytest.mark.asyncio
async def test_the_winner_is_sent_to_rest(env):
    repo, _, _, bot, engine = env
    await run_whole_battle(engine, repo)

    winner = repo.leaderboard(limit=1)[0]["user_id"]
    rest = repo.cooldown_for(winner)

    assert rest is not None, "победитель должен уйти на паузу"
    assert int(rest["place"]) == 1
    until = datetime.fromisoformat(rest["until"])
    assert 2 < (until - datetime.now(MSK)).days + 1 <= 3


@pytest.mark.asyncio
async def test_the_winner_is_told_about_it(env):
    repo, _, _, bot, engine = env
    await run_whole_battle(engine, repo)

    winner = repo.leaderboard(limit=1)[0]["user_id"]
    told = "\n".join(bot.direct.get(winner, []))

    assert "отдых" in told.lower()
    assert "50" in told, "должно быть сказано, что можно выкупить"


@pytest.mark.asyncio
async def test_a_rested_place_cannot_apply(env):
    repo, _, _, _, engine = env
    await run_whole_battle(engine, repo)
    winner = repo.leaderboard(limit=1)[0]["user_id"]

    accepted, note = await engine.join(winner, "champion")

    assert not accepted
    assert "отдыхаете" in note.lower()
    assert repo.queue_size() == 0, "в очередь он тоже не попадает"


@pytest.mark.asyncio
async def test_others_are_not_touched(env):
    """Пауза только призёрам, остальные записываются как обычно."""
    repo, _, settings, _, engine = env
    settings.set("cooldown_places", 1)
    await run_whole_battle(engine, repo)

    loser = next(
        uid for uid in range(1, 5)
        if repo.cooldown_for(uid) is None
    )
    accepted, _ = await engine.join(loser, f"n{loser}")

    assert accepted


@pytest.mark.asyncio
async def test_the_rule_can_be_switched_off(env):
    repo, _, settings, _, engine = env
    settings.set("cooldown_days", 0)

    await run_whole_battle(engine, repo)

    assert repo.cooldown_count() == 0, "нулём дней правило выключается"


@pytest.mark.asyncio
async def test_a_winner_waiting_in_the_queue_is_pulled_out(env):
    """Он мог записаться на следующий батл до того, как выиграл этот."""
    repo, _, _, _, engine = env
    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()
    repo.enqueue(1, "n1")  # как будто успел записаться снова

    while repo.current_battle() is not None:
        battle = repo.current_battle()
        for match in repo.open_matches(1, int(battle["round_no"])):
            slots = repo.match_slots(int(match["id"]))
            vote_for(repo, int(match["id"]), slots[0].user_id,
                     range(match["id"] * 100, match["id"] * 100 + 3))
        await engine.close_round(force=True)

    for user_id in range(1, 5):
        if repo.cooldown_for(user_id) is not None:
            assert not repo.in_queue(user_id), "отдыхающего в очереди быть не должно"


# ------------------------------------------------------------ снятие паузы

def test_an_expired_rest_counts_as_gone(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 1, 1, datetime.now(MSK) - timedelta(minutes=1))

    assert repo.cooldown_for(7) is None
    assert repo.cooldown_count() == 0


def test_the_admin_can_lift_it(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 1, 1, datetime.now(MSK) + timedelta(days=3))

    assert repo.clear_cooldown(7) is True
    assert repo.cooldown_for(7) is None


def test_a_new_win_replaces_the_old_rest(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 3, 1, datetime.now(MSK) + timedelta(days=1))
    repo.set_cooldown(7, 1, 2, datetime.now(MSK) + timedelta(days=3))

    rest = repo.cooldown_for(7)
    assert int(rest["place"]) == 1 and int(rest["battle_id"]) == 2


# --------------------------------------------------------------- выкуп

class Payment:
    def __init__(self, payload="cooldown", charge="ch-1", amount=50) -> None:
        self.invoice_payload = payload
        self.telegram_payment_charge_id = charge
        self.total_amount = amount


class PaidMessage:
    def __init__(self, user_id, payment) -> None:
        self.from_user = type("U", (), {"id": user_id})()
        self.successful_payment = payment
        self.sent: list[str] = []

    async def answer(self, text, **kwargs):
        self.sent.append(text)


@pytest.mark.asyncio
async def test_paying_lifts_the_rest(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 1, 1, datetime.now(MSK) + timedelta(days=3))

    message = PaidMessage(7, Payment())
    await payments.payment_done(message, repo)

    assert repo.cooldown_for(7) is None
    assert "выкуплена" in message.sent[0].lower()


@pytest.mark.asyncio
async def test_a_repeated_payment_update_is_ignored(env):
    """Telegram может прислать апдейт об оплате дважды."""
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 1, 1, datetime.now(MSK) + timedelta(days=3))

    await payments.payment_done(PaidMessage(7, Payment()), repo)
    repo.set_cooldown(7, 1, 2, datetime.now(MSK) + timedelta(days=3))
    second = PaidMessage(7, Payment())
    await payments.payment_done(second, repo)

    assert repo.cooldown_for(7) is not None, "второй апдейт не должен снимать новую паузу"
    assert second.sent == []


@pytest.mark.asyncio
async def test_buying_votes_still_works(env):
    """Выкуп не должен сломать обычную покупку голосов."""
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")

    message = PaidMessage(7, Payment(payload="votes:5", charge="ch-2", amount=25))
    await payments.payment_done(message, repo)

    assert repo.vote_balance(7) == 5


# ------------------------------------------------------------- как показано

def test_the_refusal_counts_the_days_left():
    now = datetime.now(MSK)
    body = texts.on_cooldown(1, now + timedelta(days=2, hours=5), now, 50)

    assert "<b>3</b> дня" in body, "неполные сутки округляются вверх"
    assert "50⭐" in body, "цена выкупа должна быть названа"


def test_the_last_hours_are_still_a_day():
    now = datetime.now(MSK)
    assert texts.rest_days(now + timedelta(minutes=30), now) == 1
    assert texts.rest_days(now - timedelta(minutes=1), now) == 0


def test_the_panel_screen_lists_who_is_resting(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "champion", "W")
    repo.set_cooldown(7, 1, 1, datetime.now(MSK) + timedelta(days=3))

    text, markup = panel_ui.cooldowns(repo.active_cooldowns(), 3, 3, 50)

    assert "@champion" in text and "50⭐" in text
    assert markup.inline_keyboard


def test_the_card_offers_to_lift_the_rest(env):
    repo, _, _, _, _ = env
    repo.upsert_user(7, "w", "W")
    repo.set_cooldown(7, 2, 1, datetime.now(MSK) + timedelta(days=3))

    _, markup = panel_ui.person(
        repo.get_user(7), repo.stats_for(7), 0, (0, 0), repo.cooldown_for(7)
    )
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]

    assert "p:person:rest:7" in actions


def test_the_card_without_a_rest_has_no_such_button(env):
    repo, _, _, _, _ = env
    repo.upsert_user(8, "plain", "P")

    _, markup = panel_ui.person(repo.get_user(8), repo.stats_for(8), 0, (0, 0), None)
    actions = [b.callback_data for row in markup.inline_keyboard for b in row]

    assert not any(a.startswith("p:person:rest") for a in actions)
