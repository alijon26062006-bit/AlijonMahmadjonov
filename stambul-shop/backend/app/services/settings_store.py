"""Настройки, которые владелец задаёт из панели, а не через .env.

Ключ стороннего сервиса нельзя держать в коде и нельзя отдавать в браузер.
Он лежит здесь, читает его только сервер, наружу уходит лишь признак
«задан или нет» и последние четыре знака — чтобы владелец узнал свой ключ,
не видя его целиком.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting

# Ключи, которые считаются секретами: их значение не покидает сервер
SECRETS = {"ai_api_key", "openai_api_key"}


async def get(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    return row.value if row and row.value else default


async def set_value(session: AsyncSession, key: str, value: str) -> None:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


def masked(value: str) -> str:
    """Показываем ровно столько, чтобы владелец узнал свой ключ."""
    if not value:
        return ""
    return "••••" + value[-4:] if len(value) > 4 else "••••"


DEFAULT_MODEL = "gpt-4o-mini"


async def openai(session: AsyncSession) -> tuple[str, str]:
    """Ключ и модель для разбора фотографий."""
    return (await get(session, "openai_api_key"),
            await get(session, "openai_model", DEFAULT_MODEL))


async def public(session: AsyncSession) -> dict:
    provider = await get(session, "ai_provider", "local")
    key = await get(session, "ai_api_key")
    openai_key = await get(session, "openai_api_key")
    return {
        "ai_provider": provider,
        "ai_key_set": bool(key),
        "ai_key_hint": masked(key),
        "openai_key_set": bool(openai_key),
        "openai_key_hint": masked(openai_key),
        "openai_model": await get(session, "openai_model", DEFAULT_MODEL),
    }
