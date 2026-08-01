"""Универсальный репозиторий CRUD-операций."""
from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class Repository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, obj_id: int) -> T | None:
        return await self.session.get(self.model, obj_id)

    async def list(self, offset: int = 0, limit: int | None = None,
                   order_by: Sequence[Any] = (), **filters) -> list[T]:
        stmt = select(self.model).filter_by(**filters)
        for ob in order_by:
            stmt = stmt.order_by(ob)
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def count(self, **filters) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return await self.session.scalar(stmt) or 0

    async def add(self, **values) -> T:
        obj = self.model(**values)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T, **values) -> T:
        for k, v in values.items():
            setattr(obj, k, v)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj_id: int) -> None:
        await self.session.execute(
            sa_delete(self.model).where(self.model.id == obj_id)
        )
        await self.session.commit()
