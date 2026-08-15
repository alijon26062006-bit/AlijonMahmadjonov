"""Одобрение и отклонение объявлений.

Один код для кнопок в группе модерации и для админ-панели: иначе логика
разъедется. Блокировка строки исключает двойную обработку, когда два
администратора нажимают одновременно.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ST_APPROVED, ST_PENDING, ST_REJECTED, Listing, ModerationLog, User,
)


class AlreadyHandled(Exception):
    """Объявление уже обработано другим администратором."""

    def __init__(self, status: str):
        self.status = status
        super().__init__(status)


async def _lock(session: AsyncSession, listing_id: int) -> Listing:
    listing = await session.scalar(
        select(Listing).where(Listing.id == listing_id).with_for_update())
    if listing is None:
        raise AlreadyHandled("удалено")
    if listing.status != ST_PENDING:
        raise AlreadyHandled(listing.status)
    return listing


async def approve(session: AsyncSession, listing_id: int, admin: User) -> Listing:
    """Одобряет и ставит публикацию в очередь. Бросает AlreadyHandled."""
    listing = await _lock(session, listing_id)
    listing.status = ST_APPROVED
    session.add(ModerationLog(listing_id=listing.id, admin_id=admin.id,
                              action="approve"))
    await session.commit()

    from app.workers.queue import enqueue_publish
    await enqueue_publish(listing.id)
    return listing


async def reject(session: AsyncSession, listing_id: int, admin: User,
                 reason: str) -> Listing:
    """Отклоняет с причиной и уведомляет автора. Бросает AlreadyHandled."""
    listing = await _lock(session, listing_id)
    listing.status = ST_REJECTED
    listing.reject_reason = reason[:500]
    session.add(ModerationLog(listing_id=listing.id, admin_id=admin.id,
                              action="reject", reason=reason[:500]))
    await session.commit()

    from app.workers.queue import enqueue_notify_rejected
    await enqueue_notify_rejected(listing.id)
    return listing


async def set_ban(session: AsyncSession, user_id: int, admin: User,
                  banned: bool) -> User | None:
    user = await session.get(User, user_id)
    if user is None or user.id == admin.id:      # себя банить нельзя
        return None
    user.is_banned = banned
    session.add(ModerationLog(listing_id=None, admin_id=admin.id,
                              action="ban_user" if banned else "unban_user",
                              reason=f"user={user_id}"))
    await session.commit()
    return user
