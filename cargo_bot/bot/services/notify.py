"""Уведомления администраторов и пользователей."""
import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.repositories import UserRepo

logger = logging.getLogger(__name__)


async def all_admin_ids(session: AsyncSession) -> list[int]:
    ids = set(get_settings().admin_ids)
    ids.update(await UserRepo(session).admin_tg_ids())
    return list(ids)


async def notify_admins(bot: Bot, session: AsyncSession, text: str) -> None:
    for tg_id in await all_admin_ids(session):
        try:
            await bot.send_message(tg_id, text)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", tg_id, e)


async def notify_user(bot: Bot, tg_id: int, text: str) -> bool:
    try:
        await bot.send_message(tg_id, text)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось уведомить пользователя %s: %s", tg_id, e)
        return False
