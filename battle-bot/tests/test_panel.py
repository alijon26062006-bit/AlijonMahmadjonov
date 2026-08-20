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

def test_main_post_needs_a_channel_first(env):
    repo, config, settings, _ = env
    state = main_post.state(repo, config, settings)

    assert state["main_channel_id"] == 0
    text, markup = panel_ui.channel(state)
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert not any("Опубликовать" in label for label in labels), (
        "без канала публиковать некуда"
    )


def test_publish_button_appears_once_the_channel_is_set(env):
    """Фото необязательно — без него выходит обычный пост с кнопкой."""
    repo, config, settings, _ = env
    settings.set("main_channel_id", -1001111111111)

    _, markup = panel_ui.channel(main_post.state(repo, config, settings))
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Опубликовать" in label for label in labels)


@pytest.mark.asyncio
async def test_publishing_without_a_channel_says_why(env):
    repo, config, settings, _ = env
    with pytest.raises(main_post.MainPostError, match="главного канала"):
        await main_post.publish(FakeBot(), repo, config, settings)


@pytest.mark.asyncio
async def test_publishing_without_a_photo_sends_a_text_post(env):
    repo, config, settings, _ = env
    settings.set("main_channel_id", -1001111111111)

    bot = FakeBot()
    message_id = await main_post.publish(bot, repo, config, settings)

    assert message_id, "пост должен выйти и без фото"
    assert bot.channel_posts, "текстовый пост ушёл в канал"
    assert "НАБОР НА БИТВУ НИКОВ" in bot.channel_posts[0]
    assert settings.get("main_post_message_id") == message_id


def test_main_post_looks_like_a_recruitment_card(env):
    _, _, settings, _ = env
    body = main_post.default_text([1000, 500, 250])

    assert "НАБОР НА БИТВУ НИКОВ" in body
    assert "<blockquote>" in body, "призы в цитате, как в образце"
    assert "1 место — <b>1000</b>⭐" in body
    assert "Участвовать по кнопке" in body


def test_join_button_can_carry_a_premium_icon(env):
    _, config, _, _ = env
    plain = main_post.keyboard(config.bot_username).inline_keyboard[0][0]
    assert plain.text == "⚡ Участвовать"
    assert plain.icon_custom_emoji_id is None

    fancy = main_post.keyboard(config.bot_username, {"⚡": "555"}).inline_keyboard[0][0]
    assert fancy.text == "Участвовать"
    assert fancy.icon_custom_emoji_id == "555"


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


# ------------------------------------------------- выход из режима ввода

@pytest.mark.asyncio
async def test_a_command_always_escapes_the_input_screen():
    """Из ожидания значения нужно уметь выйти командой, а не застрять в нём."""
    from aiogram.dispatcher.event.bases import SkipHandler

    from handlers.panel import command_escapes_input

    class FakeState:
        def __init__(self):
            self.cleared = False

        async def clear(self):
            self.cleared = True

    state = FakeState()
    with pytest.raises(SkipHandler):
        await command_escapes_input(message=None, state=state)

    assert state.cleared, "состояние должно сброситься, иначе человек заперт"


def test_the_input_handler_lets_commands_through_first():
    """Обработчик команд обязан стоять раньше приёма значения."""
    from handlers import panel as panel_module

    handlers = [h.callback.__name__ for h in panel_module.router.message.handlers]
    assert handlers.index("command_escapes_input") < handlers.index("receive_value")


def test_channel_id_is_read_from_a_forwarded_post():
    """Искать ID руками не нужно — достаточно переслать пост из канала."""
    from datetime import datetime

    from aiogram.types import Chat, MessageOriginChannel

    from handlers.panel import _channel_from_forward

    class Forwarded:
        forward_origin = MessageOriginChannel(
            type="channel",
            date=datetime(2026, 8, 20),
            chat=Chat(id=-1003775036903, type="channel", title="Батлы"),
            message_id=42,
        )

    assert _channel_from_forward(Forwarded()) == -1003775036903


def test_a_plain_message_has_no_channel_to_read():
    from handlers.panel import _channel_from_forward

    class Plain:
        forward_origin = None

    assert _channel_from_forward(Plain()) is None
    assert _channel_from_forward(object()) is None


# --------------------------------------------- «Обновить» без изменений

def test_unchanged_refresh_is_not_treated_as_a_failure():
    """Telegram отказывается перерисовывать одинаковый текст — это норма."""
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    from services.tg import is_not_modified

    same = TelegramBadRequest(
        method=SendMessage(chat_id=1, text="t"),
        message=(
            "Bad Request: message is not modified: specified new message content "
            "and reply markup are exactly the same as a current content and reply "
            "markup of the message"
        ),
    )
    other = TelegramBadRequest(
        method=SendMessage(chat_id=1, text="t"), message="Bad Request: chat not found"
    )

    assert is_not_modified(same) is True
    assert is_not_modified(other) is False


@pytest.mark.asyncio
async def test_editing_survives_an_unchanged_screen_but_not_real_errors():
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    from handlers.panel import edit_in_place

    class Screen:
        def __init__(self, error=None):
            self.error = error
            self.edits = 0

        async def edit_text(self, text, reply_markup=None):
            self.edits += 1
            if self.error:
                raise self.error

    def failure(text: str) -> TelegramBadRequest:
        return TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message=text)

    ok = Screen()
    await edit_in_place(ok, "текст", None)
    assert ok.edits == 1

    unchanged = Screen(failure("Bad Request: message is not modified"))
    await edit_in_place(unchanged, "текст", None)  # тихо проглатываем

    broken = Screen(failure("Bad Request: chat not found"))
    with pytest.raises(TelegramBadRequest):
        await edit_in_place(broken, "текст", None)
