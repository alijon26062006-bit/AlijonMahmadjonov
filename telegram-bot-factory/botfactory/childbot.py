"""Движок созданного бота: одна и та же логика на всех, разная только структура."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Awaitable, Callable, Deque

from aiogram import Bot, Dispatcher
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from .generator import Generator
from .spec import BotSpec, Command

log = logging.getLogger(__name__)

TELEGRAM_TEXT_LIMIT = 4096
AI_BUSY_TEXT = "Секунду…"


def _chunks(text: str, size: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    text = text.strip() or "…"
    return [text[i : i + size] for i in range(0, len(text), size)]


def _menu_keyboard(spec: BotSpec) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if not spec.menu_buttons:
        return ReplyKeyboardRemove()
    rows: list[list[KeyboardButton]] = []
    for index in range(0, len(spec.menu_buttons), 2):
        pair = spec.menu_buttons[index : index + 2]
        rows.append([KeyboardButton(text=label) for label in pair])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _inline_keyboard(spec: BotSpec, command_index: int) -> InlineKeyboardMarkup | None:
    command = spec.commands[command_index]
    if not command.buttons:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for button_index, button in enumerate(command.buttons):
        if button.action == "url":
            rows.append([InlineKeyboardButton(text=button.text, url=button.value)])
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button.text,
                        callback_data=f"c:{command_index}:{button_index}",
                    )
                ]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


class ChildBotEngine:
    """Исполняет структуру бота. Меняется структура — меняется поведение."""

    def __init__(
        self,
        *,
        bot_id: int,
        spec: BotSpec,
        generator: Generator,
        take_quota: Callable[[], Awaitable[bool]],
        history_limit: int,
    ) -> None:
        self.bot_id = bot_id
        self.spec = spec
        self._generator = generator
        self._take_quota = take_quota
        self._history_limit = max(1, history_limit)
        self._history: dict[int, Deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=self._history_limit * 2)
        )

    def build_dispatcher(self) -> Dispatcher:
        dispatcher = Dispatcher()
        dispatcher.message.register(self.on_message)
        dispatcher.callback_query.register(self.on_callback)
        return dispatcher

    async def apply_commands(self, bot: Bot) -> None:
        """Показать команды бота в меню Telegram."""
        commands = [BotCommand(command="start", description="Начать")]
        commands += [
            BotCommand(command=item.command, description=item.description[:256])
            for item in self.spec.commands
        ]
        try:
            await bot.set_my_commands(commands)
        except Exception:  # noqa: BLE001 — меню не критично для работы бота
            log.warning("Не удалось обновить меню команд бота %s", self.bot_id, exc_info=True)

    # --- обработчики ----------------------------------------------------

    async def on_message(self, message: Message) -> None:
        text = (message.text or message.caption or "").strip()

        if not text:
            await self._reply_fallback(message, "")
            return

        if text.startswith("/"):
            name = text[1:].split()[0].split("@")[0].lower()
            if name == "start":
                await self._send_welcome(message)
                return
            command = self._find_command(name)
            if command is not None:
                await self._send_command(message, command)
                return
            await self._reply_fallback(message, text)
            return

        command = self._command_by_label(text)
        if command is not None:
            await self._send_command(message, command)
            return

        trigger_reply = self._match_trigger(text)
        if trigger_reply is not None:
            await self._send_text(message, trigger_reply)
            return

        await self._reply_fallback(message, text)

    async def on_callback(self, callback: CallbackQuery) -> None:
        data = callback.data or ""
        await callback.answer()
        if not data.startswith("c:") or callback.message is None:
            return
        try:
            _, raw_command, raw_button = data.split(":", 2)
            command = self.spec.commands[int(raw_command)]
            button = command.buttons[int(raw_button)]
        except (ValueError, IndexError):
            return
        for part in _chunks(button.value):
            await callback.message.answer(part)

    # --- отправка -------------------------------------------------------

    async def _send_welcome(self, message: Message) -> None:
        parts = _chunks(self.spec.welcome_text)
        for part in parts[:-1]:
            await message.answer(part)
        await message.answer(parts[-1], reply_markup=_menu_keyboard(self.spec))

    async def _send_command(self, message: Message, command: Command) -> None:
        index = self.spec.commands.index(command)
        parts = _chunks(command.reply_text)
        for part in parts[:-1]:
            await message.answer(part)
        await message.answer(parts[-1], reply_markup=_inline_keyboard(self.spec, index))

    async def _send_text(self, message: Message, text: str) -> None:
        for part in _chunks(text):
            await message.answer(part)

    async def _reply_fallback(self, message: Message, question: str) -> None:
        if not self.spec.ai.enabled or not question:
            await self._send_text(message, self.spec.fallback_text)
            return

        if not await self._take_quota():
            await self._send_text(message, self.spec.fallback_text)
            return

        chat_id = message.chat.id
        history = list(self._history[chat_id])
        try:
            if message.bot is not None:
                await message.bot.send_chat_action(chat_id, "typing")
            answer = await self._generator.answer_as_bot(self.spec, history, question)
        except Exception:  # noqa: BLE001 — клиент не должен видеть техническую ошибку
            log.exception("ИИ-ответ не получился, бот %s", self.bot_id)
            await self._send_text(message, self.spec.fallback_text)
            return

        self._history[chat_id].append({"role": "user", "content": question})
        self._history[chat_id].append({"role": "assistant", "content": answer})
        await self._send_text(message, answer)

    # --- поиск ----------------------------------------------------------

    def _find_command(self, name: str) -> Command | None:
        for command in self.spec.commands:
            if command.command == name:
                return command
        return None

    def _command_by_label(self, text: str) -> Command | None:
        lowered = text.lower()
        for command in self.spec.commands:
            if command.description.lower() == lowered:
                return command
        return None

    def _match_trigger(self, text: str) -> str | None:
        lowered = text.lower()
        best: tuple[int, str] | None = None
        for trigger in self.spec.triggers:
            for keyword in trigger.keywords:
                if keyword and keyword in lowered:
                    score = len(keyword)
                    if best is None or score > best[0]:
                        best = (score, trigger.reply_text)
        return best[1] if best else None
