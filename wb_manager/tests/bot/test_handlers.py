"""Обработчик токена: сообщение удаляется первым делом, токен уходит только в сервис."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from tests.helpers import personal_token
from wbm.bot import handlers
from wbm.bot.services import BotServices, ConnectResult
from wbm.db.models import User


@dataclass
class FakeStatus:
    edits: list[str] = field(default_factory=list)

    async def edit_text(self, text: str, **_: Any) -> None:
        self.edits.append(text)


@dataclass
class FakeMessage:
    text: str
    events: list[str] = field(default_factory=list)
    status: FakeStatus = field(default_factory=FakeStatus)

    async def delete(self) -> None:
        self.events.append("delete")

    async def answer(self, text: str, **_: Any) -> FakeStatus:
        self.events.append(f"answer:{text[:20]}")
        return self.status


class FakeServices:
    def __init__(self) -> None:
        self.received: list[str] = []

    async def connect_token(self, user: User, text: str) -> ConnectResult:
        self.received.append(text)
        return ConnectResult(True, shop_name="Ромашка <b>", available=["content"], shop_id=7)


class FakeState:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    async def update_data(self, **kwargs: Any) -> None:
        self.data.update(kwargs)


async def test_token_message_deleted_first_and_shop_selected() -> None:
    token = personal_token()
    message = FakeMessage(token)
    services = FakeServices()
    state = FakeState()

    await handlers.on_token(
        cast(Message, message),
        User(id=1, phone="+79990000000"),
        cast(BotServices, services),
        cast(FSMContext, state),
    )

    assert message.events[0] == "delete"
    assert services.received == [token]
    assert state.data == {"shop_id": 7}
    assert "Ромашка &lt;b&gt;" in message.status.edits[0]
    assert all(token not in event for event in message.events + message.status.edits)


async def test_token_without_phone_is_deleted_and_not_saved() -> None:
    message = FakeMessage(personal_token())
    services = FakeServices()

    await handlers.on_token(
        cast(Message, message),
        User(id=1, phone=None),
        cast(BotServices, services),
        cast(FSMContext, FakeState()),
    )

    assert message.events[0] == "delete"
    assert services.received == []


def test_callback_id_parsing() -> None:
    assert handlers._id_from("pdf:15") == 15
    assert handlers._id_from("pdf:abc") is None
    assert handlers._id_from(None) is None
