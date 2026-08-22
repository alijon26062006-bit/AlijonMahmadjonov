"""Запуск и остановка созданных ботов внутри одного процесса."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError

from .childbot import ChildBotEngine
from .config import Settings
from .crypto import DecryptError, TokenCipher
from .generator import AIHub
from .spec import BotSpec
from .storage import STATUS_ERROR, STATUS_RUNNING, STATUS_STOPPED, BotRecord, Storage

log = logging.getLogger(__name__)

Notify = Callable[[int, str], Awaitable[None]]


class StartError(RuntimeError):
    """Бот не удалось запустить — текст можно показать владельцу."""


@dataclass
class RunningBot:
    bot: Bot
    dispatcher: Dispatcher
    engine: ChildBotEngine
    task: asyncio.Task


class Supervisor:
    def __init__(
        self,
        *,
        storage: Storage,
        cipher: TokenCipher,
        hub: AIHub,
        settings: Settings,
        notify: Notify,
    ) -> None:
        self._storage = storage
        self._cipher = cipher
        self._hub = hub
        self._settings = settings
        self._notify = notify
        self._running: dict[int, RunningBot] = {}

    def is_running(self, bot_id: int) -> bool:
        return bot_id in self._running

    @property
    def running_count(self) -> int:
        return len(self._running)

    # --- запуск ---------------------------------------------------------

    async def start(self, record: BotRecord) -> None:
        if record.id in self._running:
            return

        try:
            token = self._cipher.decrypt(record.token_enc)
        except DecryptError as exc:
            await self._storage.set_status(record.id, STATUS_ERROR, str(exc))
            raise StartError(str(exc)) from exc

        bot = Bot(token=token)

        try:
            await bot.get_me()
        except TelegramUnauthorizedError as exc:
            await bot.session.close()
            message = "Токен больше не действует. Похоже, бот удалён или токен сброшен в @BotFather."
            await self._storage.set_status(record.id, STATUS_ERROR, message)
            raise StartError(message) from exc
        except Exception as exc:  # noqa: BLE001 — сеть, таймаут, что угодно
            await bot.session.close()
            message = f"Не получилось связаться с Telegram: {exc}"
            await self._storage.set_status(record.id, STATUS_ERROR, message)
            raise StartError(message) from exc

        metered = not self._settings.require_own_key
        engine = ChildBotEngine(
            record=record,
            hub=self._hub,
            take_quota=lambda: self._quota(record.id, metered),
            history_limit=self._settings.ai_history_limit,
            metered=metered,
        )
        dispatcher = engine.build_dispatcher()
        await engine.apply_commands(bot)

        task = asyncio.create_task(
            self._poll(record.id, record.owner_id, bot, dispatcher),
            name=f"childbot-{record.id}",
        )
        self._running[record.id] = RunningBot(bot=bot, dispatcher=dispatcher, engine=engine, task=task)
        await self._storage.set_status(record.id, STATUS_RUNNING, None)
        log.info("Бот %s запущен (@%s)", record.id, record.username)

    async def _quota(self, bot_id: int, metered: bool) -> bool:
        """Со своим ключом человек платит сам — считать нечего."""
        if not metered:
            return True
        return await self._storage.take_ai_quota(bot_id, self._settings.ai_monthly_limit)

    async def _poll(self, bot_id: int, owner_id: int, bot: Bot, dispatcher: Dispatcher) -> None:
        try:
            await dispatcher.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            raise
        except TelegramConflictError:
            message = (
                "Этот бот уже где-то запущен — Telegram не разрешает два подключения "
                "с одним токеном. Остановите второй запуск и попробуйте снова."
            )
            await self._fail(bot_id, owner_id, message)
        except TelegramUnauthorizedError:
            message = "Токен перестал работать. Проверьте бота в @BotFather."
            await self._fail(bot_id, owner_id, message)
        except Exception as exc:  # noqa: BLE001
            log.exception("Бот %s упал", bot_id)
            await self._fail(bot_id, owner_id, f"Бот остановился из-за ошибки: {exc}")

    async def _fail(self, bot_id: int, owner_id: int, message: str) -> None:
        self._running.pop(bot_id, None)
        await self._storage.set_status(bot_id, STATUS_ERROR, message)
        try:
            await self._notify(owner_id, message)
        except Exception:  # noqa: BLE001 — владелец мог заблокировать фабрику
            log.warning("Не удалось предупредить владельца бота %s", bot_id, exc_info=True)

    # --- остановка ------------------------------------------------------

    async def stop(self, bot_id: int, *, mark: str = STATUS_STOPPED) -> None:
        running = self._running.pop(bot_id, None)
        if running is None:
            if mark:
                await self._storage.set_status(bot_id, mark, None)
            return

        await running.dispatcher.stop_polling()
        running.task.cancel()
        try:
            await running.task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        await running.bot.session.close()
        if mark:
            await self._storage.set_status(bot_id, mark, None)
        log.info("Бот %s остановлен", bot_id)

    # --- обновление структуры на лету ------------------------------------

    async def apply_spec(self, bot_id: int, spec: BotSpec) -> None:
        running = self._running.get(bot_id)
        if running is None:
            return
        running.engine.spec = spec
        await running.engine.apply_commands(running.bot)
        log.info("Бот %s обновлён без остановки", bot_id)

    # --- массовые операции ------------------------------------------------

    async def restore(self) -> int:
        """Поднять ботов, которые работали до перезапуска фабрики."""
        started = 0
        for record in await self._storage.list_by_status(STATUS_RUNNING):
            try:
                await self.start(record)
                started += 1
            except StartError as exc:
                log.warning("Бот %s не поднялся: %s", record.id, exc)
        return started

    async def shutdown(self) -> None:
        for bot_id in list(self._running):
            await self.stop(bot_id, mark="")
