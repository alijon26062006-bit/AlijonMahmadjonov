"""Мини-стенд: поддельный Телеграм, чтобы гонять обработчики без сети."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

pytest.importorskip("telegram", reason="нужен python-telegram-bot")

from minesbot import db  # noqa: E402
from minesbot.config import Config  # noqa: E402


class FakeUser:
    def __init__(self, user_id, name="Игрок", is_bot=False):
        self.id = user_id
        self.full_name = name
        self.username = name
        self.is_bot = is_bot


class FakeChat:
    def __init__(self, chat_id=10, chat_type="private"):
        self.id = chat_id
        self.type = chat_type


class FakeMessage:
    _next_id = 1

    def __init__(self, text="", user=None, chat=None, reply_to=None):
        FakeMessage._next_id += 1
        self.message_id = FakeMessage._next_id
        self.text = text
        self.from_user = user
        self.chat = chat or FakeChat()
        self.reply_to_message = reply_to
        self.sent = []          # что бот ответил на это сообщение

    async def reply_text(self, text, **kwargs):
        answer = FakeMessage(text, user=None, chat=self.chat)
        answer.markup = kwargs.get("reply_markup")
        self.sent.append(answer)
        return answer


class FakeUpdate:
    def __init__(self, message, user):
        self.effective_message = message
        self.effective_user = user
        self.effective_chat = message.chat


class FakeQuery:
    """Нажатие на кнопку."""

    def __init__(self, data, user, message):
        self.data = data
        self.from_user = user
        self.message = message
        self.answers = []       # всплывашки
        self.edits = []         # новые тексты сообщения
        self.markups = []       # новые клавиатуры

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)
        self.markups.append(kwargs.get("reply_markup"))

    async def edit_message_reply_markup(self, reply_markup=None):
        self.markups.append(reply_markup)


class FakeBot:
    def __init__(self):
        self.messages = []
        self.edits = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def edit_message_text(self, chat_id=None, message_id=None, text="", **kwargs):
        self.edits.append((chat_id, message_id, text))


class FakeApplication:
    def __init__(self, bot_data):
        self.bot_data = bot_data


class FakeContext:
    def __init__(self, app, args=None, user_data=None, bot=None):
        self.application = app
        self.args = args or []
        self.user_data = user_data if user_data is not None else {}
        self.bot = bot or FakeBot()


@pytest.fixture
def cfg(tmp_path):
    return Config(
        token="1:" + "x" * 35,
        db_path=tmp_path / "mines.db",
        admin_ids=frozenset(),
        start_balance=1000,
        bonus_amount=500,
        bonus_hours=12,
        min_bet=10,
        max_bet=100_000,
        default_mines=3,
        house_edge=0.03,
        log_level="INFO",
    )


@pytest.fixture
def conn(cfg):
    connection = db.connect(cfg.db_path)
    yield connection
    connection.close()


@pytest.fixture
def app(cfg, conn):
    return FakeApplication({"config": cfg, "conn": conn})
