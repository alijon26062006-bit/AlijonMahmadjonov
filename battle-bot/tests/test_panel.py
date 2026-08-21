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
        panel_ui.settings_screen(settings.all(), [-1001111111111]),
        panel_ui.subscription_check([(-1001111111111, ""), (-1002222222222, "chat not found")]),
        panel_ui.referrals(1, True, repo.referral_report(), repo.top_inviters(10)),
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
    ("prizes", "2000, 1000, 500", ["2000", "1000", "500"]),
    ("vote_price", "7", 7),
    ("min_participants", "6", 6),
    ("max_participants", "128", 128),
    ("late_join_until_round", "3", 3),
])
def test_valid_input_is_saved(env, key, raw, expected):
    _, _, settings, _ = env
    value = panel.EDITORS[key]["check"](raw)
    settings.set(key, value)
    assert settings.get(key) == expected


@pytest.mark.parametrize("key,raw", [
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
    assert config.prizes == ["3000", "2000", "1000"]


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
    assert "1 место — <b>1000⭐</b>" in body
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

    matches = [row for row in repo.posts(chat_id=config.channel_id) if row["kind"] == "match"]
    assert len(matches) == 2, "две пары — два поста"
    announces = [row for row in repo.posts(chat_id=config.channel_id) if row["kind"] == "announce"]
    assert announces, "плюс анонс раунда"


@pytest.mark.asyncio
async def test_results_and_announcements_are_remembered_too(env):
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)
    repo.add_vote(1, 900, 1, VoteSource.FREE)
    repo.add_vote(2, 901, 3, VoteSource.FREE)
    await engine.close_round(force=True)

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
    before = len(repo.posts(chat_id=config.channel_id))
    deleted, failed = await main_post.wipe_battle_posts(bot, repo, config)

    assert deleted == before and failed == 0
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

    before = len(repo.posts(chat_id=config.channel_id))
    deleted, failed = await main_post.wipe_battle_posts(StubbornBot(), repo, config)

    assert deleted == 0 and failed == before
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
async def test_editing_survives_an_unchanged_screen_and_a_dead_one():
    """Панель живёт одним сообщением — и не должна умирать вместе с ним."""
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    from handlers.panel import edit_in_place

    class Screen:
        def __init__(self, error=None):
            self.error = error
            self.edits = 0
            self.answers = 0

        async def edit_text(self, text, reply_markup=None):
            self.edits += 1
            if self.error:
                raise self.error

        async def answer(self, text, reply_markup=None, **kwargs):
            self.answers += 1

    def failure(text: str) -> TelegramBadRequest:
        return TelegramBadRequest(method=SendMessage(chat_id=1, text="t"), message=text)

    ok = Screen()
    await edit_in_place(ok, "текст", None)
    assert ok.edits == 1 and ok.answers == 0

    unchanged = Screen(failure("Bad Request: message is not modified"))
    await edit_in_place(unchanged, "текст", None)
    assert unchanged.answers == 0, "тот же экран перерисовывать нечем и незачем"

    # сообщение удалили: раньше здесь падало и панель переставала отвечать
    dead = Screen(failure("Bad Request: message to edit not found"))
    await edit_in_place(dead, "текст", None)
    assert dead.answers == 1, "экран должен прийти новым сообщением"


@pytest.mark.asyncio
async def test_a_button_on_an_inaccessible_message_still_answers():
    """Кнопка на слишком старом сообщении — не повод падать."""
    from aiogram.types import Chat, InaccessibleMessage

    from services import ui

    stale = InaccessibleMessage(chat=Chat(id=7, type="private"), message_id=1, date=0)
    assert not ui.editable(stale), "у недоступного сообщения нет edit_text"
    assert ui.photo_of(stale) is None

    class Stale:
        """То же, что присылает Telegram: есть answer, нет edit_text."""

        def __init__(self) -> None:
            self.sent: list[str] = []

        async def answer(self, text, reply_markup=None, **kwargs):
            self.sent.append(text)

    target = Stale()
    await ui.edit_or_send(target, "экран", None)
    assert target.sent == ["экран"], "вместо падения приходит новое сообщение"


# ------------------------------------- каждая кнопка обязана быть живой

class CallbackStub:
    def __init__(self, data: str) -> None:
        self.data = data


def handlers_for(data: str) -> list[str]:
    """Кто возьмётся обработать такую кнопку.

    Смотрим все роутеры, а не только панель: часть её кнопок обслуживают
    соседние — например, «Рассылка» живёт в своём мастере.
    """
    from handlers import broadcast as broadcast_module
    from handlers import panel as panel_module

    found = []
    for module in (panel_module, broadcast_module):
        for handler in module.router.callback_query.handlers:
            if handler.callback.__name__ == "unknown_button":
                continue  # страховка ловит всё, для проверки она не считается
            if all(f.callback(CallbackStub(data)) for f in handler.filters or []):
                found.append(handler.callback.__name__)
    return found


def every_button(screens: list[tuple]) -> list[str]:
    return [
        button.callback_data
        for _, markup in screens
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


@pytest.mark.asyncio
async def test_every_button_on_every_screen_has_a_handler(env):
    """Мёртвая кнопка ничем себя не выдаёт — ловим её тестом."""
    repo, config, settings, engine = env
    await join_users(engine, repo, 4)
    settings.set("main_channel_id", -1001111111111)
    stats = panel.collect(repo, engine)
    repo.upsert_user(77, "Satoorov", "A")
    repo.add_promo("Рекламный текст", "Перейти", "https://t.me/realed")

    screens = [
        panel_ui.home(stats),
        panel_ui.battle(stats),
        panel_ui.prizes(settings.get("prizes")),
        panel_ui.votes(settings.vote_price, True, repo.sold_votes()),
        panel_ui.channel(main_post.state(repo, config, settings)),
        panel_ui.people(stats),
        panel_ui.settings_screen(settings.all(), [-1001111111111]),
        panel_ui.subscription_check([(-1001111111111, ""), (-1002222222222, "chat not found")]),
        panel_ui.referrals(1, True, repo.referral_report(), repo.top_inviters(10)),
        panel_ui.autopilot(settings.all(), repo.promos()),
        panel_ui.fraud(panel._fraud_signals(repo)),
        panel_ui.promo_list(repo.promos()),
        panel_ui.member_channels(True, 1, 1, 3, repo.member_channels()),
        panel_ui.health(repo.error_summary(), repo.recent_errors(), {"итоги раундов": True}),
        panel_ui.person(repo.get_user(77), repo.stats_for(77), 0),
        panel_ui.confirm("Точно?", "battle:cancel:do", "battle"),
        panel_ui.ask("Призы", "1000,500,250", "подсказка", "prizes"),
    ]

    dead = [data for data in every_button(screens) if not handlers_for(data)]
    assert not dead, f"кнопки без обработчика: {dead}"


def test_cancel_button_returns_to_its_section():
    """Отмена должна вести в раздел, а не в никуда."""
    for section in ("prizes", "votes", "channel", "settings", "people", "referrals", "auto"):
        _, markup = panel_ui.ask("Поле", "—", "", section)
        cancel = markup.inline_keyboard[0][0]

        assert cancel.callback_data == f"p:{section}", "лишний или потерянный префикс"
        assert handlers_for(cancel.callback_data), f"«Отмена» из {section} никуда не ведёт"


def test_prefix_is_never_doubled_whichever_form_the_caller_used():
    """Именно этот баг ломал «Отмену» на всех экранах.

    Префикс добавляется в одном месте, поэтому оба написания дают одно и то же.
    """
    assert panel_ui.button("Отмена", "channel").callback_data == "p:channel"
    assert panel_ui.button("Отмена", "p:channel").callback_data == "p:channel"

    for section in ("channel", "p:channel"):
        _, markup = panel_ui.ask("Поле", "—", "", section)
        cancel = markup.inline_keyboard[0][0]
        assert cancel.callback_data == "p:channel"
        assert handlers_for(cancel.callback_data), "«Отмена» обязана вести в раздел"


def test_navigation_clears_the_input_mode():
    """Кнопки разделов сбрасывают ожидание значения, кнопки ввода — нет."""
    from handlers.panel import leave_input_mode  # noqa: F401  - проверяем факт наличия

    from handlers import panel as panel_module

    middlewares = [m.__name__ for m in panel_module.router.callback_query.outer_middleware]
    assert "leave_input_mode" in middlewares


def first_handler(data: str) -> str:
    """Кто на самом деле обработает кнопку с учётом порядка роутеров."""
    import bot as bot_module

    for router in bot_module.ROUTERS:
        for handler in router.callback_query.handlers:
            if all(f.callback(CallbackStub(data)) for f in handler.filters or []):
                return handler.callback.__name__
    return ""


def test_the_fallback_is_registered_last():
    """Страховка должна стоять после всех, иначе она съедает чужие кнопки."""
    import bot as bot_module

    assert bot_module.ROUTERS[-1].name == "panel-fallback"
    assert bot_module.ROUTERS[-1] is not bot_module.ROUTERS[1], "это отдельный роутер"


def test_the_fallback_does_not_steal_buttons_of_other_sections():
    """Ровно эта ошибка ломала «Рассылку»: страховка панели забирала её кнопку."""
    assert first_handler("p:broadcast") == "start_cast"
    assert first_handler("p:home") == "go_home"
    assert first_handler("p:battle") == "show_battle"
    assert first_handler("p:referrals") == "show_referrals"


def test_a_truly_unknown_button_still_reaches_the_fallback():
    assert first_handler("p:такого-нет") == "unknown_button"


# ------------------------------------- сценарий «задать главный канал»

class FakeUser:
    def __init__(self, user_id: int = 1) -> None:
        self.id = user_id
        self.username = "admin"
        self.first_name = "Admin"


class FakeMessage:
    """Сообщение от админа: текст или пересылка."""

    def __init__(self, text: str = "", forward_origin=None, user_id: int = 1) -> None:
        self.text = text
        self.forward_origin = forward_origin
        self.photo = None
        self.from_user = FakeUser(user_id)
        self.replies: list[str] = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.replies.append(text)
        return self


class FakeState:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.cleared = False

    async def get_data(self):
        return self.data

    async def clear(self):
        self.cleared = True

    async def set_state(self, *args, **kwargs):
        pass

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


@pytest.mark.asyncio
async def test_setting_the_main_channel_by_id(env):
    repo, config, settings, engine = env
    message = FakeMessage(text="-1003775036903")
    state = FakeState({"key": "main_channel_id", "back": "channel"})

    await panel.receive_value(message, repo, config, engine, settings, state)

    assert settings.get("main_channel_id") == -1003775036903
    assert state.cleared, "после сохранения ожидание ввода должно сняться"
    assert any("Главный канал" in reply for reply in message.replies)


@pytest.mark.asyncio
async def test_setting_the_main_channel_by_forwarding_a_post(env):
    """Ровно тот сценарий, который падал с NameError."""
    from datetime import datetime

    from aiogram.types import Chat, MessageOriginChannel

    repo, config, settings, engine = env
    message = FakeMessage(
        forward_origin=MessageOriginChannel(
            type="channel",
            date=datetime(2026, 8, 20),
            chat=Chat(id=-1003775036903, type="channel", title="Батлы"),
            message_id=7,
        )
    )
    state = FakeState({"key": "main_channel_id", "back": "channel"})

    await panel.receive_value(message, repo, config, engine, settings, state)

    assert settings.get("main_channel_id") == -1003775036903
    assert state.cleared


@pytest.mark.asyncio
async def test_a_wrong_channel_value_is_explained_and_input_stays_open(env):
    repo, config, settings, engine = env
    message = FakeMessage(text="мой канал")
    state = FakeState({"key": "main_channel_id", "back": "channel"})

    await panel.receive_value(message, repo, config, engine, settings, state)

    assert settings.get("main_channel_id") == 0, "мусор не должен сохраняться"
    assert not state.cleared, "человек остаётся в вводе и может попробовать снова"
    assert any("Нужно число" in reply for reply in message.replies)


@pytest.mark.asyncio
async def test_changing_the_channel_forgets_the_old_post(env):
    """Новый канал — старый message_id больше ни на что не указывает."""
    repo, config, settings, engine = env
    settings.set("main_post_message_id", 555)

    message = FakeMessage(text="-1004444444444")
    state = FakeState({"key": "main_channel_id", "back": "channel"})
    await panel.receive_value(message, repo, config, engine, settings, state)

    assert settings.get("main_post_message_id") == 0


@pytest.mark.asyncio
async def test_saving_prizes_from_the_panel(env):
    repo, config, settings, engine = env
    message = FakeMessage(text="3000, 2000, 1000")
    state = FakeState({"key": "prizes", "back": "prizes"})

    await panel.receive_value(message, repo, config, engine, settings, state)

    assert settings.get("prizes") == ["3000", "2000", "1000"]
    assert config.prizes == ["3000", "2000", "1000"], "должно примениться без перезапуска"
    assert state.cleared


# --------------------------------------- выход из ввода кнопкой меню

@pytest.mark.asyncio
async def test_a_menu_button_escapes_the_input_screen():
    """Кнопка меню — не значение, а желание уйти: она не должна застревать.

    Именно так человек запирался: искал участника, нажал «Принять участие» и
    получал «это не похоже на ник» на каждое нажатие.
    """
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
    assert state.cleared


def test_the_escape_filter_covers_commands_and_every_menu_button():
    from services import keyboards
    from handlers import panel as panel_module

    handler = next(
        h for h in panel_module.router.message.handlers
        if h.callback.__name__ == "command_escapes_input"
    )

    class Stub:
        def __init__(self, text):
            self.text = text

    def caught(text: str) -> bool:
        magic = handler.filters[-1].callback
        return bool(magic(Stub(text)))

    assert caught("/start") and caught("/panel")
    for label in keyboards.menu_labels():
        assert caught(label), f"кнопка «{label}» не выпускает из ввода"
    assert not caught("Satoorov"), "обычный ввод должен доходить до проверки"


def test_buying_also_releases_on_a_menu_button():
    from services import keyboards
    from handlers import payments as payments_module

    handler = next(
        h for h in payments_module.router.message.handlers
        if h.callback.__name__ == "command_leaves_buying"
    )

    class Stub:
        def __init__(self, text):
            self.text = text

    magic = handler.filters[-1].callback
    assert magic(Stub("👤 Профиль"))
    assert magic(Stub("/start"))
    assert not magic(Stub("15"))
