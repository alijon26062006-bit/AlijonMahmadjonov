"""Запуск батла: зов в главный канал и приём заявок только в первом раунде."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramForbiddenError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import MSK
from core.engine import BattleEngine
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, enqueue_users, make_config, vote_for

MAIN = -1001111111111


class Bot(FakeBot):
    """Тот же фейк, но помнит, что и с какими кнопками ушло в каждый чат."""

    def __init__(self, dead: set[int] | None = None) -> None:
        super().__init__()
        self.by_chat: dict[int, list[tuple[str, object]]] = {}
        self.dead = dead or set()

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        if chat_id in self.dead:
            raise TelegramForbiddenError(method=None, message="bot is not a member")
        self.by_chat.setdefault(chat_id, []).append((text, reply_markup))
        return await super().send_message(chat_id, text, reply_markup, **kwargs)

    def texts(self, chat_id) -> list[str]:
        return [text for text, _ in self.by_chat.get(chat_id, [])]


def build(tmp_path, name="start.db", main_channel=MAIN, admins=(1,), **overrides):
    path = str(tmp_path / name)
    repo = Repo(connect(path))
    config = make_config(db_path=path, min_participants=4, admin_ids=list(admins), **overrides)
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    if main_channel:
        settings.set("main_channel_id", main_channel)
    bot = Bot()
    return repo, config, settings, bot, BattleEngine(bot, repo, config, settings=settings)


# --------------------------------------------------- зов в главный канал

@pytest.mark.asyncio
async def test_starting_a_battle_calls_the_main_channel(tmp_path):
    """Запустил батл — в главном канале сам появился пост с кнопкой."""
    repo, config, settings, bot, engine = build(tmp_path)
    await enqueue_users(engine, repo, 4)

    await engine.create_from_queue()

    posts = bot.texts(MAIN)
    assert len(posts) == 1, "ровно один зов на батл"
    assert "Б А Т Л" in posts[0], "заголовок с разрядкой, как в остальных постах"
    assert "первый раунд" in posts[0], "должно быть сказано, что заявку ещё примут"
    assert "1000⭐" in posts[0], "призы должны быть в посте"


@pytest.mark.asyncio
async def test_the_call_carries_a_join_button(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path)
    await enqueue_users(engine, repo, 4)

    await engine.create_from_queue()

    markup = bot.by_chat[MAIN][0][1]
    button = markup.inline_keyboard[0][0]
    assert "частв" in button.text, "кнопка «Участвовать»"
    assert button.url.endswith("?start=join"), "ведёт в бота на подачу заявки"


@pytest.mark.asyncio
async def test_the_call_says_how_many_are_already_in(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path)
    await enqueue_users(engine, repo, 6)

    await engine.create_from_queue()

    assert "<b>6</b>" in bot.texts(MAIN)[0]


@pytest.mark.asyncio
async def test_without_a_main_channel_the_battle_still_starts(tmp_path):
    """Главный канал не задан — просто некуда звать, батл идёт как обычно."""
    repo, config, settings, bot, engine = build(tmp_path, "nomain.db", main_channel=None)
    await enqueue_users(engine, repo, 4)

    started, _ = await engine.create_from_queue()

    assert started and repo.current_battle() is not None


@pytest.mark.asyncio
async def test_a_failed_call_does_not_break_the_battle(tmp_path):
    """Бота выгнали из главного канала — батл всё равно должен начаться."""
    repo, config, settings, bot, engine = build(tmp_path, "dead.db")
    bot.dead.add(MAIN)
    await enqueue_users(engine, repo, 4)

    started, _ = await engine.create_from_queue()

    assert started
    assert repo.open_matches(1, 1), "пары опубликованы, несмотря на сбой зова"


@pytest.mark.asyncio
async def test_the_call_is_remembered_for_cleanup(tmp_path):
    """Панель умеет удалять посты батла — зов должен попасть в этот список."""
    repo, config, settings, bot, engine = build(tmp_path)
    await enqueue_users(engine, repo, 4)

    await engine.create_from_queue()

    assert [row["kind"] for row in repo.posts(chat_id=MAIN)] == ["call"]


@pytest.mark.asyncio
async def test_the_second_round_does_not_call_again(tmp_path):
    """Зов уходит один раз — на запуске, а не на каждый раунд."""
    repo, config, settings, bot, engine = build(tmp_path)
    await enqueue_users(engine, repo, 8)
    await engine.create_from_queue()

    for match in repo.open_matches(1, 1):
        slots = repo.match_slots(int(match["id"]))
        vote_for(repo, int(match["id"]), slots[0].user_id, range(match["id"] * 100, match["id"] * 100 + 3))
    await engine.close_round(force=True)

    assert len(bot.texts(MAIN)) == 1


# ------------------------------------------- приём только в первом раунде

@pytest.mark.asyncio
async def test_a_newcomer_joins_during_the_first_round(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "round1.db")
    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()

    repo.upsert_user(99, "late", "L")
    accepted, text = await engine.join(99, "late")

    assert accepted and "в батле" in text.lower()
    assert repo.is_participant(1, 99)


@pytest.mark.asyncio
async def test_the_second_round_closes_the_door(tmp_path):
    """Начался второй раунд — новые заявки копятся на следующий батл."""
    repo, config, settings, bot, engine = build(tmp_path, "round2.db")
    await enqueue_users(engine, repo, 8)
    await engine.create_from_queue()

    for match in repo.open_matches(1, 1):
        slots = repo.match_slots(int(match["id"]))
        vote_for(repo, int(match["id"]), slots[0].user_id,
                 range(match["id"] * 100, match["id"] * 100 + 3))
    await engine.close_round(force=True)
    assert int(repo.current_battle()["round_no"]) == 2

    repo.upsert_user(99, "late", "L")
    accepted, text = await engine.join(99, "late")

    assert accepted and "очереди" in text
    assert not repo.is_participant(1, 99), "во второй раунд не подсаживаем"
    assert repo.queue_size() == 1, "заявка ждёт следующего батла"


def test_the_window_is_the_first_round_by_default(tmp_path):
    _, _, settings, _, engine = build(tmp_path, "window.db")
    assert engine.late_join_limit() == 1


def test_an_old_database_is_narrowed_to_the_first_round(tmp_path):
    """В базе уже лежало «2» — обновление должно поправить это само."""
    path = str(tmp_path / "old.db")
    repo = Repo(connect(path))
    repo.conn.execute("INSERT INTO settings(key, value) VALUES('late_join_until_round', '2')")
    repo.conn.commit()

    settings = Settings(repo.conn, make_config(db_path=path))
    settings.bootstrap()

    assert settings.get("late_join_until_round") == 1


def test_a_deliberate_choice_is_not_overwritten(tmp_path):
    """Админ сам поставил 2 после обновления — перезапуск это не откатывает."""
    path = str(tmp_path / "choice.db")
    repo = Repo(connect(path))
    settings = Settings(repo.conn, make_config(db_path=path))
    settings.bootstrap()
    settings.set("late_join_until_round", 2)

    again = Settings(repo.conn, make_config(db_path=path))
    again.bootstrap()

    assert again.get("late_join_until_round") == 2


# ------------------------------------------------- «людей набралось»

@pytest.mark.asyncio
async def test_the_admin_is_told_when_the_queue_is_ready(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "ready.db")

    await enqueue_users(engine, repo, 4)

    assert any("Очередь набралась" in text for text in bot.texts(1))


@pytest.mark.asyncio
async def test_the_admin_is_told_only_once(tmp_path):
    """Каждая следующая заявка не должна дёргать админа снова."""
    repo, config, settings, bot, engine = build(tmp_path, "once.db")

    await enqueue_users(engine, repo, 9)

    told = [text for text in bot.texts(1) if "Очередь набралась" in text]
    assert len(told) == 1


@pytest.mark.asyncio
async def test_nobody_is_bothered_while_a_battle_runs(tmp_path):
    """Батл идёт — запускать всё равно нечего, значит и писать не о чем."""
    repo, config, settings, bot, engine = build(tmp_path, "running.db")
    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()
    bot.by_chat.clear()

    for user_id in range(50, 54):
        repo.upsert_user(user_id, f"n{user_id}", "N")
        await engine.join(user_id, f"n{user_id}")

    assert not any("Очередь набралась" in text for text in bot.texts(1))


# ------------------------------- батл, созданный вечером, играется завтра

@pytest.mark.asyncio
async def test_a_battle_created_after_the_final_runs_until_tomorrow(tmp_path):
    """Финал закончился вечером, сразу создали новый — он не должен сгореть."""
    repo, config, settings, bot, engine = build(tmp_path, "evening.db")
    evening = datetime.now(MSK).replace(hour=21, minute=5, second=0, microsecond=0)
    engine.now = lambda: evening

    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()

    deadline = datetime.fromisoformat(repo.current_battle()["deadline"])
    assert deadline > evening + timedelta(hours=12), "первый раунд должен дожить до завтра"
    assert deadline.hour == 18, "и закончиться в первое время из списка"


@pytest.mark.asyncio
async def test_the_call_shows_the_real_deadline(tmp_path):
    """В посте главного канала должно стоять то же время, что у батла."""
    repo, config, settings, bot, engine = build(tmp_path, "calltime.db")
    evening = datetime.now(MSK).replace(hour=21, minute=5, second=0, microsecond=0)
    engine.now = lambda: evening

    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()

    deadline = datetime.fromisoformat(repo.current_battle()["deadline"])
    assert deadline.strftime("%H:%M") in bot.texts(MAIN)[0]


@pytest.mark.asyncio
async def test_a_daytime_battle_still_finishes_the_same_evening(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "daytime.db")
    noon = datetime.now(MSK).replace(hour=12, minute=0, second=0, microsecond=0)
    engine.now = lambda: noon

    await enqueue_users(engine, repo, 4)
    await engine.create_from_queue()

    deadline = datetime.fromisoformat(repo.current_battle()["deadline"])
    assert deadline.date() == noon.date() and deadline.hour == 18


# ------------------------------ батл создаётся первым, люди приходят потом

@pytest.mark.asyncio
async def test_an_empty_battle_can_be_created(tmp_path):
    """Главное: кнопка «Создать батл» работает при нуле в очереди."""
    repo, config, settings, bot, engine = build(tmp_path, "empty.db")

    started, note = await engine.create_from_queue()

    assert started and "Пока никого" in note
    assert repo.current_battle() is not None


@pytest.mark.asyncio
async def test_an_empty_battle_still_calls_the_channels(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "emptycall.db")

    await engine.create_from_queue()

    assert "Пока никого" in bot.texts(MAIN)[0], "зов ушёл в главный канал"
    assert any("НАБОР ОТКРЫТ" in text.replace(" ", "") or "Н А Б О Р" in text
               for text in bot.channel_posts), "и в канал батлов"


@pytest.mark.asyncio
async def test_people_arriving_after_the_start_get_paired(tmp_path):
    """Ровно сценарий админа: создал пустой батл, люди пришли по кнопке."""
    repo, config, settings, bot, engine = build(tmp_path, "arrive.db")
    await engine.create_from_queue()

    for user_id in (10, 11, 12):
        repo.upsert_user(user_id, f"nick{user_id}", "N")
        await engine.join(user_id, f"nick{user_id}")

    assert len(repo.open_matches(1, 1)) == 1, "первые двое встали в пару"
    assert len(repo.unassigned_players(1)) == 1, "третий ждёт соперника"
    assert repo.participant_count(1) == 3


@pytest.mark.asyncio
async def test_the_lonely_one_is_not_declared_a_winner(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "lonely.db")
    await enqueue_users(engine, repo, 1)

    await engine.create_from_queue()

    assert repo.current_battle() is not None, "батл не должен схлопнуться"
    assert not repo.open_matches(1, 1)


# --------------------------------------- если так никто и не пришёл

@pytest.mark.asyncio
async def test_a_battle_nobody_joined_is_closed_at_the_deadline(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "nobody.db")
    await engine.create_from_queue()

    await engine.close_round(force=True)

    assert repo.current_battle() is None, "пустой батл закрывается"
    assert any("НЕ СОСТОЯЛСЯ" in t.replace(" ", "") or "Н Е   С О" in t
               for t in bot.channel_posts)


@pytest.mark.asyncio
async def test_the_single_applicant_gets_his_place_back(tmp_path):
    """Он подал заявку и не виноват, что соперника не нашлось."""
    repo, config, settings, bot, engine = build(tmp_path, "giveback.db")
    await enqueue_users(engine, repo, 1)
    await engine.create_from_queue()
    assert repo.queue_size() == 0

    await engine.close_round(force=True)

    assert repo.queue_size() == 1, "заявка вернулась в очередь"
    assert any("вернулась в очередь" in text for text in bot.texts(1) + bot.texts(2))


@pytest.mark.asyncio
async def test_the_admin_learns_the_battle_did_not_happen(tmp_path):
    repo, config, settings, bot, engine = build(tmp_path, "tellme.db")
    await engine.create_from_queue()

    await engine.close_round(force=True)

    assert any("не состоялся" in text.lower() for text in bot.texts(1))


@pytest.mark.asyncio
async def test_a_battle_with_one_pair_is_not_given_up(tmp_path):
    """Пара есть — значит батл состоялся, закрывать нечего."""
    repo, config, settings, bot, engine = build(tmp_path, "onepair.db")
    await enqueue_users(engine, repo, 2)
    await engine.create_from_queue()

    match_id = int(repo.open_matches(1, 1)[0]["id"])
    slots = repo.match_slots(match_id)
    vote_for(repo, match_id, slots[0].user_id, range(700, 703))
    await engine.close_round(force=True)

    assert not any("не состоялся" in text.lower() for text in bot.texts(1))
