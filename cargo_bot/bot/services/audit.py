"""Журналирование всех изменений (тарифы, курсы, статусы и т.д.)."""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Log


def snapshot(obj: Any, fields: list[str] | None = None) -> dict:
    """Снимок значений полей ORM-объекта для журнала."""
    if obj is None:
        return {}
    cols = fields or [c.name for c in obj.__table__.columns]
    out = {}
    for name in cols:
        val = getattr(obj, name, None)
        out[name] = str(val) if val is not None else None
    return out


async def log_action(session: AsyncSession, actor_tg_id: int | None, action: str,
                     entity: str, entity_id: int | None = None,
                     old: dict | None = None, new: dict | None = None) -> None:
    session.add(Log(
        actor_tg_id=actor_tg_id, action=action, entity=entity, entity_id=entity_id,
        old_data=json.dumps(old, ensure_ascii=False) if old else None,
        new_data=json.dumps(new, ensure_ascii=False) if new else None,
    ))
    await session.commit()
