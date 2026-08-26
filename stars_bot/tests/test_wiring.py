"""Сборка диспетчера и проверка, что каждая кнопка ведёт в обработчик."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401  — фиксирует настройки до импорта app

from aiogram import Dispatcher

from app import db, keyboards
from app.handlers import admin, deposit, menu, profile, shop, support
from app.middlewares.guard import UserGuardMiddleware
from app.services.fragment import build_provider

ROUTERS = [admin.router, menu.router, shop.router, deposit.router,
           profile.router, support.router]


def declared_callbacks() -> set[str]:
    """Все callback_data, которые бот реально отдаёт в клавиатурах."""
    found = set()
    markups = [
        keyboards.main_menu(), keyboards.stars_entry(), keyboards.premium_menu(),
        keyboards.confirm(), keyboards.deposit_methods(), keyboards.profile(),
        keyboards.support_menu(True), keyboards.support_menu(False),
        keyboards.back(), keyboards.cancel(),
        keyboards.admin_deposit(1), keyboards.admin_retry(1),
    ]
    for markup in markups:
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data:
                    found.add(button.callback_data)
    return found


def handled_patterns() -> list[str]:
    """Строки, по которым фильтруются callback-хендлеры, — вытаскиваем из кода."""
    patterns = []
    for path in Path("app/handlers").glob("*.py"):
        text = path.read_text()
        patterns += re.findall(r'F\.data\s*==\s*"([^"]+)"', text)
        patterns += re.findall(r'F\.data\.startswith\("([^"]+)"\)', text)
    return patterns


async def main() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + suffix).unlink(missing_ok=True)

    conn = await db.connect()
    await db.init(conn)
    dp = Dispatcher(conn=conn, provider=build_provider())
    dp.message.middleware(UserGuardMiddleware())
    dp.callback_query.middleware(UserGuardMiddleware())
    for router in ROUTERS:
        dp.include_router(router)

    handlers = sum(len(o.handlers) for r in ROUTERS for o in r.observers.values())
    print(f"роутеров: {len(ROUTERS)}, хендлеров: {handlers}")
    print("типы апдейтов:", dp.resolve_used_update_types())

    exact = set(handled_patterns())
    orphans = []
    for data in sorted(declared_callbacks()):
        if data in exact:
            continue
        if any(data.startswith(prefix) for prefix in exact):
            continue
        orphans.append(data)

    if orphans:
        print("\n❌ Кнопки без обработчика:", ", ".join(orphans))
        sys.exit(1)

    print(f"\n✅ Все {len(declared_callbacks())} кнопок ведут в обработчики")
    await conn.close()


asyncio.run(main())
