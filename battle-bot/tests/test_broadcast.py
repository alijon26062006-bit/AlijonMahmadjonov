"""Рассылка: любой тип сообщения, кнопки и честный отчёт о доставке."""
import sys
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods import SendMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import broadcast


class Recorder:
    """Запоминает, каким методом и с чем бот отправил сообщение."""

    def __init__(self, blocked: set[int] | None = None, broken: set[int] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.blocked = blocked or set()
        self.broken = broken or set()

    def __getattr__(self, name):
        if not name.startswith("send_"):
            raise AttributeError(name)

        async def call(**kwargs):
            chat_id = kwargs.get("chat_id")
            if chat_id in self.blocked:
                raise TelegramForbiddenError(
                    method=SendMessage(chat_id=1, text="t"), message="bot was blocked"
                )
            if chat_id in self.broken:
                raise TelegramBadRequest(
                    method=SendMessage(chat_id=1, text="t"), message="chat not found"
                )
            self.calls.append((name, kwargs))

        return call

    def methods(self) -> list[str]:
        return [name for name, _ in self.calls]


# ------------------------------------------------- все виды сообщений

@pytest.mark.parametrize("kind,method", [
    ("photo", "send_photo"),
    ("video", "send_video"),
    ("animation", "send_animation"),
    ("document", "send_document"),
    ("audio", "send_audio"),
    ("voice", "send_voice"),
    ("video_note", "send_video_note"),
    ("sticker", "send_sticker"),
])
@pytest.mark.asyncio
async def test_every_media_type_is_sent_by_its_own_method(kind, method):
    bot = Recorder()
    draft = broadcast.Draft(media_type=kind, file_id="file-1")

    await broadcast.deliver(bot, draft, 500)

    assert bot.methods() == [method]
    assert bot.calls[0][1][kind] == "file-1"


@pytest.mark.asyncio
async def test_plain_text_goes_as_a_message():
    bot = Recorder()
    await broadcast.deliver(bot, broadcast.Draft(text="привет"), 500)

    assert bot.methods() == ["send_message"]
    assert bot.calls[0][1]["text"] == "привет"


@pytest.mark.asyncio
async def test_a_photo_with_text_goes_as_one_message_with_a_caption():
    bot = Recorder()
    draft = broadcast.Draft(media_type="photo", file_id="f", text="подпись")

    await broadcast.deliver(bot, draft, 500)

    assert bot.methods() == ["send_photo"], "два сообщения вместо одного — некрасиво"
    assert bot.calls[0][1]["caption"] == "подпись"


@pytest.mark.asyncio
async def test_a_sticker_with_text_needs_a_second_message():
    """Стикер подпись не несёт — текст уходит следом."""
    bot = Recorder()
    draft = broadcast.Draft(media_type="sticker", file_id="f", text="привет")

    await broadcast.deliver(bot, draft, 500)

    assert bot.methods() == ["send_sticker", "send_message"]


@pytest.mark.asyncio
async def test_a_video_note_with_text_needs_a_second_message():
    bot = Recorder()
    draft = broadcast.Draft(media_type="video_note", file_id="f", text="привет")

    await broadcast.deliver(bot, draft, 500)

    assert bot.methods() == ["send_video_note", "send_message"]


@pytest.mark.asyncio
async def test_a_long_text_does_not_fit_a_caption_and_goes_separately():
    """Подпись Telegram ограничена 1024 символами — иначе сообщение не уйдёт."""
    bot = Recorder()
    draft = broadcast.Draft(media_type="photo", file_id="f", text="я" * 1500)

    await broadcast.deliver(bot, draft, 500)

    assert bot.methods() == ["send_photo", "send_message"]


# ------------------------------------------------------------- кнопки

@pytest.mark.asyncio
async def test_buttons_are_attached_to_the_message():
    bot = Recorder()
    draft = broadcast.Draft(text="привет", buttons=[("Участвовать", "https://t.me/x")])

    await broadcast.deliver(bot, draft, 500)

    markup = bot.calls[0][1]["reply_markup"]
    assert markup.inline_keyboard[0][0].text == "Участвовать"
    assert markup.inline_keyboard[0][0].url == "https://t.me/x"


@pytest.mark.asyncio
async def test_buttons_ride_with_the_text_when_it_is_separate():
    """У стикера кнопки должны оказаться на текстовом сообщении, а не потеряться."""
    bot = Recorder()
    draft = broadcast.Draft(
        media_type="sticker", file_id="f", text="привет",
        buttons=[("Тык", "https://t.me/x")],
    )

    await broadcast.deliver(bot, draft, 500)

    sticker_markup = bot.calls[0][1].get("reply_markup")
    text_markup = bot.calls[1][1].get("reply_markup")
    assert sticker_markup is None
    assert text_markup is not None and text_markup.inline_keyboard


@pytest.mark.asyncio
async def test_a_lone_sticker_keeps_its_buttons():
    bot = Recorder()
    draft = broadcast.Draft(
        media_type="sticker", file_id="f", buttons=[("Тык", "https://t.me/x")]
    )

    await broadcast.deliver(bot, draft, 500)

    assert bot.calls[0][1]["reply_markup"].inline_keyboard


def test_several_buttons_stack_one_per_row():
    draft = broadcast.Draft(text="t", buttons=[("A", "https://a"), ("B", "https://b")])
    markup = draft.keyboard()

    assert len(markup.inline_keyboard) == 2


def test_no_buttons_means_no_keyboard():
    assert broadcast.Draft(text="t").keyboard() is None


# ------------------------------------------------------------- отчёт

@pytest.mark.asyncio
async def test_the_report_counts_delivered_blocked_and_failed():
    bot = Recorder(blocked={2, 3}, broken={4})
    draft = broadcast.Draft(text="привет")

    report = await broadcast.run(bot, draft, [1, 2, 3, 4, 5], delay=0)

    assert report.sent == 2
    assert report.blocked == 2, "заблокировавшие — не ошибка, а обычное дело"
    assert report.failed == 1
    assert report.total == 5


@pytest.mark.asyncio
async def test_one_blocked_user_does_not_stop_the_rest():
    bot = Recorder(blocked={1})
    report = await broadcast.run(bot, broadcast.Draft(text="t"), [1, 2, 3], delay=0)

    assert report.sent == 2


@pytest.mark.asyncio
async def test_progress_is_reported_along_the_way():
    seen = []

    async def on_progress(done, total, report):
        seen.append((done, total))

    await broadcast.run(
        Recorder(), broadcast.Draft(text="t"), list(range(1, 11)),
        delay=0, on_progress=on_progress, every=5,
    )

    assert seen == [(5, 10), (10, 10)]


# ------------------------------------------------------------ черновик

def test_an_empty_draft_is_recognised():
    assert broadcast.Draft().is_empty is True
    assert broadcast.Draft(text="t").is_empty is False
    assert broadcast.Draft(media_type="photo", file_id="f").is_empty is False


def test_the_draft_describes_itself_for_the_preview():
    draft = broadcast.Draft(
        media_type="voice", file_id="f", text="привет", buttons=[("A", "https://a")]
    )
    assert draft.describe() == "голосовое · текст 6 симв. · кнопок: 1"


def test_every_supported_type_has_a_human_name():
    for kind in broadcast.SENDERS:
        assert kind in broadcast.HUMAN, f"{kind} нечем назвать в интерфейсе"


# ------------------------------------------------- разбор входящего

def test_media_is_recognised_in_an_incoming_message():
    class Photo:
        file_id = "small"

    class Big:
        file_id = "big"

    class WithPhoto:
        photo = [Photo(), Big()]

    kind, file_id = broadcast.extract_media(WithPhoto())
    assert kind == "photo"
    assert file_id == "big", "берём самый крупный размер"


def test_every_media_field_is_recognised():
    class File:
        file_id = "f"

    for kind in broadcast.SENDERS:
        if kind == "photo":
            continue
        message = type("M", (), {kind: File()})()
        assert broadcast.extract_media(message) == (kind, "f")


def test_a_text_message_has_no_media():
    class Text:
        text = "просто текст"

    assert broadcast.extract_media(Text()) is None


# ------------------------------------------------------- ссылки кнопок

@pytest.mark.parametrize("raw,expected", [
    ("https://t.me/realed", "https://t.me/realed"),
    ("@realed", "https://t.me/realed"),
    ("t.me/realed", "https://t.me/realed"),
    ("tg://user?id=1", "tg://user?id=1"),
])
def test_button_links_are_normalised(raw, expected):
    from services.validation import as_url

    assert as_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "не ссылка", "ftp://x", "https://x y"])
def test_a_bad_button_link_is_refused(raw):
    from services.validation import InputError, as_url

    with pytest.raises(InputError):
        as_url(raw)


# ------------------------------------------------- адресат рассылки

@pytest.mark.asyncio
async def test_deliver_returns_the_sent_message_so_it_can_be_tracked():
    """Пост в канал надо запомнить, иначе панель не сможет его удалить."""
    class Returning(Recorder):
        def __getattr__(self, name):
            call = super().__getattr__(name)

            async def wrapped(**kwargs):
                await call(**kwargs)
                return type("M", (), {"message_id": 777})()

            return wrapped

    sent = await broadcast.deliver(Returning(), broadcast.Draft(text="t"), -1001111111111)
    assert sent.message_id == 777


@pytest.mark.asyncio
async def test_the_same_draft_works_for_a_channel_and_for_a_person():
    """Один черновик — любой адресат: канал ничем не отличается от чата."""
    bot = Recorder()
    draft = broadcast.Draft(media_type="photo", file_id="f", text="привет")

    await broadcast.deliver(bot, draft, 500)
    await broadcast.deliver(bot, draft, -1003775036903)

    assert bot.methods() == ["send_photo", "send_photo"]
    assert bot.calls[0][1]["chat_id"] == 500
    assert bot.calls[1][1]["chat_id"] == -1003775036903
    assert bot.calls[0][1]["caption"] == bot.calls[1][1]["caption"]


def test_the_preview_offers_a_channel_when_one_is_configured():
    """Кнопки адресатов должны быть живыми — иначе рассылка в канал недоступна."""
    from tests.test_panel import first_handler

    assert first_handler("cast:send:users") == "send_somewhere"
    assert first_handler("cast:send:main") == "send_somewhere"
    assert first_handler("cast:send:battles") == "send_somewhere"
