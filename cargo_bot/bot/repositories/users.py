from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Admin, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg(self, tg_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_id == tg_id))

    async def upsert(self, tg_id: int, username: str | None,
                     full_name: str | None) -> tuple[User, bool]:
        """Возвращает (user, created)."""
        user = await self.get_by_tg(tg_id)
        if user:
            changed = user.username != username or user.full_name != full_name
            user.username, user.full_name = username, full_name
            if changed:
                await self.session.commit()
            return user, False
        user = User(tg_id=tg_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user, True

    async def admin_tg_ids(self) -> list[int]:
        rows = await self.session.scalars(select(Admin.tg_id).where(Admin.is_active.is_(True)))
        return list(rows.all())
