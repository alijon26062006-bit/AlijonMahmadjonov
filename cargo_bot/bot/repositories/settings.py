import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Setting


class SettingsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str | None = None) -> str | None:
        row = await self.session.scalar(select(Setting).where(Setting.key == key))
        return row.value if row else default

    async def get_json(self, key: str, default=None):
        raw = await self.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    async def set(self, key: str, value: str, description: str | None = None) -> Setting:
        row = await self.session.scalar(select(Setting).where(Setting.key == key))
        if row:
            row.value = value
            if description:
                row.description = description
        else:
            row = Setting(key=key, value=value, description=description)
            self.session.add(row)
        await self.session.commit()
        return row
