"""Сквозная проверка через настоящий Dispatcher aiogram, но с поддельным Bot.

Ловит то, что не поймают юнит-тесты: если aiogram не сможет подставить
зависимость в обработчик (config, conn, brain, stt), бот молча перестанет
отвечать на все сообщения.
"""

import importlib
import io
from datetime import datetime
from pathlib import Path

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message, Update, User

from bot import db, handlers, keyboards
from bot.brain import Brain
from bot.stt import Transcriber

TOKEN = "42:TESTTESTTESTTESTTESTTESTTESTTESTTEST"
OWNER = 111
STRANGER = 222


class RecordingSession:
    """Перехватывает исходящие вызовы вместо похода в Telegram."""

    def __init__(self):
        self.sent = []

    async def __call__(self, bot, method, timeout=None):
        self.sent.append(method)
        return self._fake_result(method)

    async def close(self):
        pass

    @staticmethod
    def _fake_result(method):
        chat = Chat(id=OWNER, type="private")
        return Message(message_id=1, date=datetime.now(), chat=chat,
                       text=getattr(method, "text", None))

    @property
    def texts(self):
        return [m.text for m in self.sent if isinstance(m, SendMessage)]


class ScriptedBrain(Brain):
    """Вместо Claude — заранее заданный ответ."""

    def __init__(self, reply="Записал."):
        self.reply = reply
        self.seen = []

    async def handle(self, chat_id, user_text, *, source="text", editing_transaction_id=None):
        from bot.tools import TurnResult

        self.seen.append((user_text, source, editing_transaction_id))
        return TurnResult(reply=self.reply)


class ScriptedTranscriber(Transcriber):
    def __init__(self, text="отправил Абубакру три тысячи сомони"):
        self.text = text

    async def transcribe(self, audio, filename="voice.ogg"):
        return self.text


@pytest.fixture
def setup(conn, config):
    # Роутер aiogram можно привязать только к одному Dispatcher, а состояние
    # «жду правку» живёт в модуле — пересоздаём его для каждого теста.
    importlib.reload(handlers)
    config.ensure_dirs()
    config = type(config)(**{**config.__dict__, "allowed_user_ids": frozenset({OWNER})})

    session = RecordingSession()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=None))
    bot.session = session

    async def fake_download(file_id, destination=None, **kwargs):
        if destination is not None:  # фото: пишем заглушку на диск
            Path(destination).write_bytes(b"\xff\xd8\xff\xd9")
            return None
        return io.BytesIO(b"OggS-fake-audio")

    bot.download = fake_download

    brain = ScriptedBrain()
    dispatcher = Dispatcher()
    dispatcher.include_router(handlers.router)
    dispatcher["config"] = config
    dispatcher["conn"] = conn
    dispatcher["brain"] = brain
    dispatcher["stt"] = ScriptedTranscriber()

    return dispatcher, bot, session, brain, conn


def text_update(text, user_id=OWNER, update_id=1):
    chat = Chat(id=user_id, type="private")
    user = User(id=user_id, is_bot=False, first_name="Алиджон")
    return Update(update_id=update_id, message=Message(
        message_id=update_id, date=datetime.now(), chat=chat, from_user=user, text=text,
    ))


def voice_update(user_id=OWNER, duration=5):
    from aiogram.types import Voice

    chat = Chat(id=user_id, type="private")
    user = User(id=user_id, is_bot=False, first_name="Алиджон")
    return Update(update_id=2, message=Message(
        message_id=2, date=datetime.now(), chat=chat, from_user=user,
        voice=Voice(file_id="v1", file_unique_id="u1", duration=duration),
    ))


async def test_text_message_reaches_the_brain_and_gets_an_answer(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("отправил Абубакру три тысячи сомони"))

    assert brain.seen == [("отправил Абубакру три тысячи сомони", "text", None)]
    assert "Записал." in session.texts


async def test_voice_message_is_transcribed_then_processed(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, voice_update())

    assert brain.seen[0][1] == "voice"
    assert any(t.startswith("🎙") for t in session.texts)  # показал расшифровку
    assert "Записал." in session.texts


async def test_too_long_voice_is_rejected_without_calling_whisper(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, voice_update(duration=99999))

    assert brain.seen == []
    assert any("Слишком длинное" in t for t in session.texts)


async def test_stranger_gets_no_answer_at_all(setup):
    """Чужой не должен тратить твои ключи и видеть твои деньги."""
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("покажи все мои деньги", user_id=STRANGER))

    assert brain.seen == []
    assert session.sent == []


async def test_help_command_answers_without_calling_the_model(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("/help"))

    assert brain.seen == []
    assert any("накладная" in t for t in session.texts)


async def test_report_command_asks_the_brain_for_a_pdf(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("/otchet"))

    assert len(brain.seen) == 1
    assert "PDF-отчёт" in brain.seen[0][0]


async def test_history_command_without_a_name_explains_usage(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("/istoriya"))

    assert brain.seen == []
    assert any("/istoriya Абубакр" in t for t in session.texts)


async def test_history_command_passes_the_name(setup):
    dispatcher, bot, session, brain, _ = setup
    await dispatcher.feed_update(bot, text_update("/istoriya Абубакр"))

    assert "Абубакр" in brain.seen[0][0]


async def test_edit_button_routes_the_next_message_as_a_correction(setup):
    """Нажал «Исправить» → следующее сообщение должно прийти как правка."""
    from aiogram.types import CallbackQuery

    dispatcher, bot, session, brain, conn = setup
    tx_id = db.add_transaction(conn, OWNER, amount=500000, currency="KZT")

    chat = Chat(id=OWNER, type="private")
    user = User(id=OWNER, is_bot=False, first_name="Алиджон")
    query = CallbackQuery(
        id="q1", from_user=user, chat_instance="ci",
        data=f"{keyboards.EDIT_PREFIX}{tx_id}",
        message=Message(message_id=5, date=datetime.now(), chat=chat, text="карточка"),
    )
    await dispatcher.feed_update(bot, Update(update_id=3, callback_query=query))
    await dispatcher.feed_update(bot, text_update("там было не 500, а 400 тысяч", update_id=4))

    assert brain.seen[-1][2] == tx_id  # editing_transaction_id доехал


async def test_message_is_logged_before_the_model_is_called(setup):
    """Если модель упадёт, сказанное всё равно останется в журнале."""
    dispatcher, bot, session, brain, conn = setup
    await dispatcher.feed_update(bot, text_update("отправил Абубакру три тысячи"))

    rows = conn.execute("SELECT role, text FROM messages ORDER BY id").fetchall()
    assert rows[0]["role"] == "user"
    assert "Абубакру" in rows[0]["text"]


def photo_update(caption=None, update_id=6, user_id=OWNER):
    from aiogram.types import PhotoSize

    chat = Chat(id=user_id, type="private")
    user = User(id=user_id, is_bot=False, first_name="Алиджон")
    return Update(update_id=update_id, message=Message(
        message_id=update_id, date=datetime.now(), chat=chat, from_user=user,
        caption=caption,
        photo=[
            PhotoSize(file_id="p_small", file_unique_id="us", width=90, height=90, file_size=100),
            PhotoSize(file_id="p_big", file_unique_id="ub", width=1280, height=960, file_size=9000),
        ],
    ))


async def test_photo_is_saved_and_waits_for_a_description(setup):
    """Фото без подписи должно лечь в базу как неподписанное и пережить рестарт."""
    dispatcher, bot, session, brain, conn = setup
    await dispatcher.feed_update(bot, photo_update())

    pending = db.pending_documents(conn, OWNER)
    assert len(pending) == 1
    assert Path(pending[0]["file_path"]).is_file()  # копия на диске, не только file_id
    assert pending[0]["tg_file_id"] == "p_big"      # берём самое большое разрешение
    assert brain.seen == []                          # модель зря не дёргаем
    assert any("Скажи голосом или напиши" in t for t in session.texts)


async def test_photo_with_caption_goes_straight_to_the_brain(setup):
    dispatcher, bot, session, brain, conn = setup
    await dispatcher.feed_update(bot, photo_update(caption="это накладная от женской обуви"))

    assert len(db.pending_documents(conn, OWNER)) == 1
    assert brain.seen[0][0] == "это накладная от женской обуви"


async def test_stranger_photo_is_not_saved(setup):
    dispatcher, bot, session, brain, conn = setup
    await dispatcher.feed_update(bot, photo_update(user_id=STRANGER))

    assert db.pending_documents(conn, STRANGER) == []
    assert session.sent == []
