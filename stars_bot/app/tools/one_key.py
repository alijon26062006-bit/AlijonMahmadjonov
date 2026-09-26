"""Один ключ FazerCards на всё: звёзды, Premium, игры, Steam и API.

Запуск (из папки бота):  python -m app.tools.one_key

Берёт ключ, заданный для игр (в панели или в .env), делает его основным,
а отдельный игровой убирает. После перезапуска бот тратит деньги только
с этого счёта; прежний ключ «Звёзды и Premium» больше не используется.

Сами ключи не печатает — только последние 4 знака, чтобы было видно,
какой стоит.
"""
from __future__ import annotations

import asyncio
import sys


def _tail(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 4 else "…"


async def main() -> int:
    import setup as wizard

    from app import db, runtime
    from app.config import settings
    from app.services import suppliers

    conn = await db.connect()
    try:
        await runtime.load(conn)
        key = suppliers.games_key()
        main_key = (settings.fazer_api_key or "").strip()
        if not key:
            print("❌ Ключ для игр не задан — переключать не на что.\n"
                  "   Задайте его: /panel → 🕹 Игры → 🔑 Ключ поставщика для игр")
            return 1

        values = wizard.read_existing()
        values["FAZER_API_KEY"] = key
        values["FAZER_GAMES_KEY"] = ""
        values["FRAGMENT_MODE"] = "fazer"
        values.setdefault("FAZER_BASE_URL", "https://api.fzr.cards")
        wizard.write_env(values)
        # Ключ из панели важнее .env — его тоже убираем, иначе останется
        # «отдельный игровой», равный основному.
        await runtime.reset(conn, "fazer_games_key")
    finally:
        await conn.close()

    if main_key == key:
        print(f"✅ И так один ключ ({_tail(key)}) — лишнее убрано.")
    else:
        print(f"✅ Основной ключ теперь игровой ({_tail(key)}).")
        print(f"   Прежний ключ звёзд ({_tail(main_key)}) больше не используется.")
    print("   Звёзды, Premium, игры, Steam и API — всё с одного счёта.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
