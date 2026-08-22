"""Экран «Помощь»: короткий текст и кнопки-ссылки."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import start
from services import keyboards, panel_ui, texts
from services.validation import InputError
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

ALL_LINKS = {
    "link_main_channel": "https://t.me/main",
    "link_battles": "https://t.me/battles",
    "link_payouts": "https://t.me/pay",
    "link_contact": "https://t.me/admin",
    "link_rules": "https://t.me/rules",
}


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "help.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, channel_url="https://t.me/testchannel")
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    return repo, config, settings


def labels(markup) -> list[list[str]]:
    return [[b.text for b in row] for row in markup.inline_keyboard]


# ------------------------------------------------------------------ текст

def test_the_screen_is_short_and_warns_about_blocking():
    body = texts.help_screen()
    assert "заявку на участие" in body
    assert "не блокируйте его" in body
    assert "<blockquote>" in body, "предупреждение отдельным блоком, как на образце"


# --------------------------------------------------------------- кнопки

def test_all_five_links_go_in_three_rows():
    rows = labels(keyboards.help_links(ALL_LINKS))
    assert rows[:3] == [
        ["📣 Основной канал"],
        ["⚔️ Канал с батлами", "⭐ Выплаты"],
        ["✉️ Связаться", "📄 Правила"],
    ]


def test_the_rules_button_is_always_there():
    assert labels(keyboards.help_links({}))[-1] == ["📖 Как это работает"]


def test_an_unset_link_leaves_no_hole():
    """Не задал ссылку — кнопки просто нет, пустого ряда не остаётся."""
    rows = labels(keyboards.help_links({"link_payouts": "https://t.me/pay"}))
    assert rows == [["⭐ Выплаты"], ["📖 Как это работает"]]


def test_every_link_button_actually_leads_somewhere():
    for row in keyboards.help_links(ALL_LINKS).inline_keyboard:
        for item in row:
            assert item.url or item.callback_data, f"мёртвая кнопка: {item.text}"


def test_premium_icons_do_not_break_the_labels():
    table = {"📣": "111", "📄": "222"}
    rows = labels(keyboards.help_links(ALL_LINKS, table))
    assert rows[0] == ["Основной канал"], "эмодзи уехало в премиум-иконку"
    assert "Правила" in rows[2][1]


# ------------------------------------------------------- ссылки из настроек

def test_the_battles_channel_works_without_being_set(env):
    """Канал с батлами бот знает сам — кнопка работает сразу."""
    _, config, settings = env
    links = start._help_links(config, settings)
    assert links["link_battles"] == "https://t.me/testchannel"


def test_an_admin_link_wins_over_the_known_one(env):
    _, config, settings = env
    settings.set("link_battles", "https://t.me/other")
    assert start._help_links(config, settings)["link_battles"] == "https://t.me/other"


def test_links_are_saved_and_shown(env):
    _, config, settings = env
    for key, url in ALL_LINKS.items():
        settings.set(key, url)

    text, markup = panel_ui.links(settings.all(), config.channel_url)
    assert "https://t.me/pay" in text
    assert len(markup.inline_keyboard) == len(keyboards.HELP_LINKS) + 1, "пять правок и «назад»"


def test_the_panel_says_which_button_is_missing(env):
    _, config, settings = env
    text, _ = panel_ui.links(settings.all(), config.channel_url)
    assert "кнопки нет" in text


# --------------------------------------------------------------- ввод ссылок

def test_a_dash_removes_the_button():
    from handlers.panel import _link_or_none

    assert _link_or_none("-") == ""
    assert _link_or_none("нет") == ""


def test_a_username_becomes_a_link():
    from handlers.panel import _link_or_none

    assert _link_or_none("@realed") == "https://t.me/realed"


def test_garbage_is_refused_with_an_explanation():
    from handlers.panel import _link_or_none

    with pytest.raises(InputError) as failure:
        _link_or_none("просто текст")
    assert "не похоже на ссылку" in str(failure.value)


# ------------------------------------------------------------- обработчики

class Msg:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.markups: list = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.sent.append(text)
        self.markups.append(reply_markup)


@pytest.mark.asyncio
async def test_help_answers_with_text_and_buttons(env):
    _, config, settings = env
    settings.set("link_rules", "https://t.me/rules")
    message = Msg()

    await start.help_command(message, config, settings)

    assert "заявку на участие" in message.sent[0]
    rows = labels(message.markups[0])
    # канал с батлами подставился сам, правила — из настройки
    assert rows == [
        ["⚔️ Канал с батлами"],   # подставился сам из адреса канала
        ["📄 Правила"],           # задан в настройках
        ["📖 Как это работает"],
    ]


@pytest.mark.asyncio
async def test_how_it_works_opens_the_full_rules():
    class Callback:
        def __init__(self) -> None:
            self.data = "help:how"
            self.message = Msg()
            self.from_user = type("U", (), {"id": 1})()
            self.bot = None
            self.answered = False

        async def answer(self, *args, **kwargs):
            self.answered = True

    callback = Callback()
    await start.how_it_works(callback)

    assert "Как это работает" in callback.message.sent[0]
    assert callback.answered, "кнопка обязана ответить, иначе она «зависает»"
