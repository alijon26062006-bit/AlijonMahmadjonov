"""Поддельные Telegram-объекты: гоняем обработчики без интернета."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FakeChat:
    def __init__(self, chat_id: int = 100, title: str = "Склад") -> None:
        self.id = chat_id
        self.title = title
        self.full_name = title


class FakeUser:
    def __init__(self, user_id: int = 7) -> None:
        self.id = user_id


@dataclass
class Sent:
    text: str = ""
    markup: Any = None
    document: Any = None
    caption: str = ""


class FakeMessage:
    def __init__(self, text: str | None = None, chat: FakeChat | None = None, **media: Any) -> None:
        self.text = text
        self.chat = chat or FakeChat()
        self.from_user = FakeUser()
        self.voice = media.get("voice")
        self.audio = media.get("audio")
        self.video_note = media.get("video_note")
        self.sent: list[Sent] = []
        self.deleted = False
        self.edits: list[Sent] = []

    async def answer(self, text: str, reply_markup: Any = None, **_: Any) -> "FakeMessage":
        self.sent.append(Sent(text=text, markup=reply_markup))
        reply = FakeMessage(chat=self.chat)
        reply.sent = self.sent          # ответы копятся в одном списке
        reply.parent = self             # noqa: attribute defined outside init
        return reply

    async def answer_document(self, document: Any, caption: str = "", **_: Any) -> None:
        self.sent.append(Sent(document=document, caption=caption))

    async def delete(self) -> None:
        self.deleted = True

    async def edit_text(self, text: str, reply_markup: Any = None, **_: Any) -> None:
        self.edits.append(Sent(text=text, markup=reply_markup))
        self.sent.append(Sent(text=text, markup=reply_markup))

    async def edit_reply_markup(self, reply_markup: Any = None, **_: Any) -> None:
        self.edits.append(Sent(markup=reply_markup))

    # удобное чтение в тестах
    @property
    def texts(self) -> list[str]:
        return [item.text for item in self.sent if item.text]

    @property
    def last(self) -> str:
        return self.texts[-1] if self.texts else ""


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.from_user = FakeUser()
        self.answers: list[str] = []

    async def answer(self, text: str = "", **_: Any) -> None:
        self.answers.append(text)


class FakeVoice:
    def __init__(self, duration: int = 3) -> None:
        self.duration = duration
        self.file_id = "voice-1"


class FakeBot:
    def __init__(self, payload: bytes = b"audio") -> None:
        self.payload = payload

    async def download(self, media: Any, destination: Any = None, **_: Any) -> Any:
        if destination is not None:
            destination.write(self.payload)
            return destination
        import io

        return io.BytesIO(self.payload)


class FakeRecognizer:
    """Вместо Vosk: отдаёт заранее заданный текст."""

    def __init__(self, text: str = "", problem: str | None = None) -> None:
        self.text = text
        self._problem = problem

    @property
    def ready(self) -> bool:
        return self._problem is None

    @property
    def problem(self) -> str | None:
        return self._problem

    async def prepare(self) -> None:
        return None

    async def recognize_async(self, audio: bytes) -> str:
        return self.text
