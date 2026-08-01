from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.repositories import UserRepo


class IsAdmin(BaseFilter):
    """Доступ: ID из .env (супер-админы) + активные записи в таблице admins."""

    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        tg_id = event.from_user.id
        if tg_id in get_settings().admin_ids:
            return True
        return tg_id in await UserRepo(session).admin_tg_ids()
