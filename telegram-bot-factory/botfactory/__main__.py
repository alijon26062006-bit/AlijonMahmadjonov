"""Точка входа: python -m botfactory"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import ConfigError, load_settings
from .crypto import TokenCipher
from .generator import AIHub
from .mother import Factory, build_router
from .storage import Storage
from .supervisor import Supervisor

log = logging.getLogger("botfactory")

MOTHER_COMMANDS = [
    BotCommand(command="start", description="Начать"),
    BotCommand(command="new", description="Создать бота"),
    BotCommand(command="mybots", description="Мои боты"),
    BotCommand(command="keys", description="Мои ключи ИИ"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="cancel", description="Отменить действие"),
]


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def run() -> None:
    settings = load_settings()

    storage = Storage(settings.db_path)
    await storage.open()

    cipher = TokenCipher(settings.fernet_key)
    hub = AIHub(settings=settings, storage=storage, cipher=cipher)

    bot = Bot(
        token=settings.mother_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    async def notify(user_id: int, text: str) -> None:
        await bot.send_message(user_id, text)

    supervisor = Supervisor(
        storage=storage,
        cipher=cipher,
        hub=hub,
        settings=settings,
        notify=notify,
    )
    factory = Factory(
        settings=settings,
        storage=storage,
        cipher=cipher,
        hub=hub,
        supervisor=supervisor,
    )

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(build_router(factory))

    me = await bot.get_me()
    await bot.set_my_commands(MOTHER_COMMANDS)
    log.info("Фабрика @%s запущена", me.username)

    restored = await supervisor.restore()
    if restored:
        log.info("Подняли ботов после перезапуска: %s", restored)

    try:
        await dispatcher.start_polling(bot)
    finally:
        log.info("Останавливаюсь…")
        await supervisor.shutdown()
        await hub.close()
        await storage.close()
        await bot.session.close()


def main() -> int:
    setup_logging()
    try:
        asyncio.run(run())
    except ConfigError as exc:
        print(f"Ошибка настройки: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
