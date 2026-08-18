"""Переносит ключи из .env в настройки магазина.

Нужен для обновления одной командой: владелец дописывает ключ в .env, а
скрипт кладёт его туда, где его ищет приложение. Пустые значения
игнорируются — случайно затереть уже работающий ключ нельзя.

Запуск: python -m app.db.settings_from_env
"""
import asyncio
import os

from app.db.base import SessionMaker
from app.services import settings_store

# переменная окружения → ключ настройки
MAPPING = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "AI_PROVIDER": "ai_provider",
    "AI_API_KEY": "ai_api_key",
}


async def main() -> None:
    applied = []
    async with SessionMaker() as session:
        for env_name, key in MAPPING.items():
            value = (os.getenv(env_name) or "").strip()
            if not value:
                continue
            await settings_store.set_value(session, key, value)
            applied.append(key)
    if applied:
        print("Настройки перенесены из .env:", ", ".join(applied))
    else:
        print("В .env нечего переносить — настройки не тронуты")


if __name__ == "__main__":
    asyncio.run(main())
