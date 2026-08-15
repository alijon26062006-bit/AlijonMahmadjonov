"""Middleware бота: сессия БД, пользователь, сборка альбомов."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from sqlalchemy import select

from app.config import get_settings
from app.db.base import SessionMaker
from app.db.models import User


class DbMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]):
        async with SessionMaker() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """get_or_create пользователя; бан отсекается до хендлеров."""

    async def __call__(self, handler, event: Update, data: dict[str, Any]):
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if not tg_user or session is None:
            return await handler(event, data)

        user = await session.scalar(select(User).where(User.tg_id == tg_user.id))
        if user is None:
            user = User(tg_id=tg_user.id, username=tg_user.username,
                        first_name=tg_user.first_name or "",
                        is_admin=tg_user.id in get_settings().admin_id_list)
            session.add(user)
            await session.commit()
        elif user.username != tg_user.username:
            user.username = tg_user.username
            await session.commit()

        if user.is_banned:
            return None
        data["user"] = user
        return await handler(event, data)


class AlbumMiddleware(BaseMiddleware):
    """Склеивает альбом (media_group) в один вызов хендлера.

    Telegram шлёт каждое фото альбома отдельным апдейтом с общим media_group_id.
    Первый апдейт ждёт 0.7 с, собирая остальные, и вызывает хендлер один раз
    со списком сообщений в data["album"].
    """

    def __init__(self, wait: float = 0.7):
        self.wait = wait
        self.buffers: dict[str, list[Message]] = {}

    async def __call__(self, handler: Callable[[TelegramObject, dict], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]):
        if not isinstance(event, Message) or not event.media_group_id:
            if isinstance(event, Message) and event.photo:
                data["album"] = [event]
            return await handler(event, data)

        key = f"{event.chat.id}:{event.media_group_id}"
        if key in self.buffers:
            self.buffers[key].append(event)
            return None                          # обработает первый апдейт группы

        self.buffers[key] = [event]
        await asyncio.sleep(self.wait)
        album = self.buffers.pop(key, [event])
        album.sort(key=lambda m: m.message_id)
        data["album"] = album
        return await handler(event, data)
