"""Панель: сводка, экраны, правка настроек, устойчивость к неверному вводу."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import BattleEngine
from core.models import VoteSource
from handlers import panel
from services import main_post, panel_ui
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import FakeBot, make_config, join_users


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "panel.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, admin_ids=[1])
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    engine = BattleEngine(FakeBot(), repo, config)
    return repo, config, settings, engine


# ------------------------------------------------------------------ доступ

def test_only_admins_get_in(env):
    _, config, _, _ = env
    assert panel.is_admin(1, config) is True
    assert panel.is_admin(999, config) is False


# ------------------------------------------------------------------ сводка

def test_summary_on_an_empty_bot_does_not_crash(env):
    repo, config, settings, engine = env
    stats = panel.collect(repo, engine)

    assert stats["users"] == 0
    assert stats["battle"] is None
    assert stats["deadline"] == "—"
    panel_ui.home(stats)  # экран должен собираться и без данных


@pytest.mark.asyncio
async def test_summary_counts_people_votes_and_money(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, voter_id=500, target_id=1, source=VoteSource.FREE)
    repo.record_payment(1, "charge-1", stars=60, votes=5)

    stats = panel.collect(repo, engine)

    assert stats["users"] == 4
    assert stats["participants"] == 4
    assert stats["votes"] == 1
    assert stats["sold_votes"] == 5 and stats["sold_stars"] == 60
    assert stats["battle"] is not None
    assert "→" in stats["projection"], "прогноз сетки должен считаться"


@pytest.mark.asyncio
async def test_every_screen_builds_with_real_data(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)
    stats = panel.collect(repo, engine)

    screens = [
        panel_ui.home(stats),
        panel_ui.battle(stats),
        panel_ui.prizes(settings.get("prizes")),
        panel_ui.votes(settings.vote_price, True, repo.sold_votes()),
        panel_ui.channel(main_post.state(repo, config, settings)),
        panel_ui.people(stats),
        panel_ui.settings_screen(settings.all()),
        panel_ui.confirm("Точно?", "battle:cancel:do", "battle"),
        panel_ui.ask("Призы", "1000,500,250", "числа через запятую", "p:prizes"),
    ]
    for text, markup in screens:
        assert text.strip()
        assert markup.inline_keyboard, "на каждом экране должна быть хотя бы одна кнопка"


def test_person_card_builds(env):
    repo, _, _, _ = env
    repo.upsert_user(7, "Satoorov", "Alijon")
    text, markup = panel_ui.person(repo.get_user(7), repo.stats_for(7), 0)

    assert "@Satoorov" in text
    assert markup.inline_keyboard


# -------------------------------------------------------- правка настроек

@pytest.mark.parametrize("key,raw,expected", [
    ("prizes", "2000, 1000, 500", [2000, 1000, 500]),
    ("vote_price", "7", 7),
    ("min_participants", "6", 6),
    ("max_participants", "128", 128),
])
def test_valid_input_is_saved(env, key, raw, expected):
    _, _, settings, _ = env
    value = panel.EDITORS[key]["check"](raw)
    settings.set(key, value)
    assert settings.get(key) == expected


@pytest.mark.parametrize("key,raw", [
    ("prizes", "тысяча, 500"),
    ("vote_price", "бесплатно"),
    ("vote_price", "0"),
    ("vote_price", "-5"),
    ("min_participants", "1"),
    ("max_participants", "999999"),
    ("round_times", "25:00"),
    ("main_channel_id", "мой канал"),
])
def test_bad_input_is_explained_not_swallowed(env, key, raw):
    """Каждое неверное значение должно давать понятное сообщение, а не падение."""
    from services.validation import InputError

    with pytest.raises(InputError) as caught:
        panel.EDITORS[key]["check"](raw)
    assert str(caught.value).strip()


def test_every_editable_field_has_a_check_and_a_way_back(env):
    from storage.settings import FIELDS

    for key, editor in panel.EDITORS.items():
        assert callable(editor["check"]), f"{key} без проверки ввода"
        assert editor["back"], f"{key} некуда возвращаться"
        if key in FIELDS:
            assert FIELDS[key].title, f"{key} без названия"


def test_editing_prizes_reaches_the_running_battle(env):
    """Смена призов должна работать без перезапуска."""
    _, config, settings, _ = env
    settings.set("prizes", panel.EDITORS["prizes"]["check"]("3000,2000,1000"))
    assert config.prizes == [3000, 2000, 1000]


# ------------------------------------------------------------ главный пост

def test_main_post_needs_a_channel_and_a_photo(env):
    repo, config, settings, _ = env
    state = main_post.state(repo, config, settings)

    assert state["main_channel_id"] == 0
    assert not state["photo"]
    text, markup = panel_ui.channel(state)
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert not any("Опубликовать" in label for label in labels), (
        "без канала и фото публиковать нечего"
    )


def test_publish_button_appears_once_the_channel_is_set(env):
    repo, config, settings, _ = env
    settings.set("main_channel_id", -1001111111111)
    settings.set("main_post_photo", "file-id")

    _, markup = panel_ui.channel(main_post.state(repo, config, settings))
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Опубликовать" in label for label in labels)


@pytest.mark.asyncio
async def test_publishing_without_a_channel_says_why(env):
    repo, config, settings, _ = env
    with pytest.raises(main_post.MainPostError, match="главного канала"):
        await main_post.publish(FakeBot(), repo, config, settings)


@pytest.mark.asyncio
async def test_publishing_without_a_photo_says_why(env):
    repo, config, settings, _ = env
    settings.set("main_channel_id", -1001111111111)
    with pytest.raises(main_post.MainPostError, match="фото"):
        await main_post.publish(FakeBot(), repo, config, settings)


def test_main_post_caption_shows_the_participant_count(env):
    _, _, settings, _ = env
    assert "Уже в игре" not in main_post.caption(settings, 0)
    assert "<b>3 участника</b>" in main_post.caption(settings, 3)
    assert "<b>5 участников</b>" in main_post.caption(settings, 5)


def test_join_button_points_at_the_bot(env):
    _, config, _, _ = env
    markup = main_post.keyboard(config.bot_username)
    button = markup.inline_keyboard[0][0]

    assert button.url.endswith("?start=join")
    assert config.bot_username in button.url


# --------------------------------------------------- учёт постов и удаление

@pytest.mark.asyncio
async def test_published_posts_are_remembered_so_they_can_be_deleted(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)

    posts = repo.posts(chat_id=config.channel_id)
    assert len(posts) == 2, "две пары — два поста"
    assert all(row["kind"] == "match" for row in posts)


@pytest.mark.asyncio
async def test_results_and_announcements_are_remembered_too(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)
    await engine.close_round()

    kinds = {row["kind"] for row in repo.posts(chat_id=config.channel_id)}
    assert "result" in kinds, "итоги раунда тоже надо уметь удалять"
    assert "announce" in kinds, "анонс следующего раунда тоже"


@pytest.mark.asyncio
async def test_wipe_deletes_posts_and_forgets_them(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)

    class DeletingBot:
        def __init__(self):
            self.deleted = []

        async def delete_message(self, chat_id, message_id):
            self.deleted.append(message_id)

    bot = DeletingBot()
    deleted, failed = await main_post.wipe_battle_posts(bot, repo, config)

    assert deleted == 2 and failed == 0
    assert repo.posts(chat_id=config.channel_id) == [], "записи должны исчезнуть"


@pytest.mark.asyncio
async def test_posts_older_than_two_days_are_counted_but_not_lost(env):
    """Telegram не даёт удалять старые сообщения — панель должна это пережить."""
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    repo, config, settings, engine = env
    await join_users(engine, repo, 4)

    class StubbornBot:
        async def delete_message(self, chat_id, message_id):
            raise TelegramBadRequest(
                method=SendMessage(chat_id=1, text="t"),
                message="Bad Request: message can't be deleted",
            )

    deleted, failed = await main_post.wipe_battle_posts(StubbornBot(), repo, config)

    assert deleted == 0 and failed == 2
    assert repo.posts(chat_id=config.channel_id) == []
