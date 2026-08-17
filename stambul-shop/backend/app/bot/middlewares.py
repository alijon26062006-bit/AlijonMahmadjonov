"""Сессия БД и пользователь для каждого апдейта."""
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy import select

from app.config import get_settings
from app.db.base import SessionMaker
from app.db.models import User


class DbMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict[str, Any]):
        async with SessionMaker() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """get_or_create пользователя; права сверяются с ADMIN_IDS каждый раз."""

    async def __call__(self, handler, event: Update, data: dict[str, Any]):
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if not tg_user or session is None:
            return await handler(event, data)

        should_be_admin = tg_user.id in get_settings().admin_id_list
        user = await session.scalar(select(User).where(User.tg_id == tg_user.id))
        if user is None:
            user = User(tg_id=tg_user.id, username=tg_user.username,
                        first_name=tg_user.first_name or "",
                        is_admin=should_be_admin)
            session.add(user)
            await session.commit()
        else:
            changed = False
            if user.username != tg_user.username:
                user.username, changed = tg_user.username, True
            if tg_user.first_name and user.first_name != tg_user.first_name:
                user.first_name, changed = tg_user.first_name, True
            if user.is_admin != should_be_admin:
                user.is_admin, changed = should_be_admin, True
            if changed:
                await session.commit()

        if user.is_banned:
            return None
        data["user"] = user
        return await handler(event, data)
