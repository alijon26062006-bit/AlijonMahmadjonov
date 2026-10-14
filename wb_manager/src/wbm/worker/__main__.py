"""Запуск воркера: python -m wbm.worker"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

from wbm.analysis.runner import AnalysisDeps
from wbm.bootstrap import build_app
from wbm.config import get_worker_settings
from wbm.worker import Worker

logger = logging.getLogger("wbm.worker")


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def progress(self, chat_id: int, message_id: int | None, text: str) -> None:
        if message_id is None:
            return
        with contextlib.suppress(TelegramBadRequest):  # «message is not modified» и т. п.
            await self._bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)

    async def finished(
        self, chat_id: int, message_id: int | None, text: str, pdf: bytes, filename: str
    ) -> None:
        if message_id is not None:
            with contextlib.suppress(TelegramBadRequest):
                await self._bot.delete_message(chat_id, message_id)
        await self._bot.send_message(chat_id, text)
        await self._bot.send_document(chat_id, BufferedInputFile(pdf, filename=filename))

    async def failed(self, chat_id: int, message_id: int | None, text: str) -> None:
        if message_id is not None:
            try:
                await self._bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
                return
            except TelegramBadRequest:
                pass
        await self._bot.send_message(chat_id, text)


async def main() -> None:
    app = build_app()
    bot = Bot(app.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    deps = AnalysisDeps(
        sessionmaker=app.sessionmaker,
        cipher=app.cipher,
        wb_settings=app.wb_settings,
        report_writer=app.report_writer,
    )
    worker = Worker(deps, get_worker_settings(), TelegramNotifier(bot))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    try:
        await worker.run_forever(stop)
    finally:
        await bot.session.close()
        await app.engine.dispose()
        logger.info("Воркер остановлен")


if __name__ == "__main__":
    asyncio.run(main())
