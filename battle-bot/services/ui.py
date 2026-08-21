"""Безопасная работа с сообщением, на котором нажали кнопку.

Telegram присылает вместе с нажатием не всякое сообщение. Если оно удалено
или слишком старое, приходит «недоступное» (`InaccessibleMessage`): у него
есть только чат и номер, а методов `edit_text`, `edit_reply_markup` и поля
`photo` нет вовсе. Обращение к ним — не ошибка Telegram, а AttributeError
внутри бота: человек видит «что-то пошло не так», админ получает отчёт,
а причина всего лишь в возрасте сообщения.

Ещё `callback.message` может быть None — так бывает у кнопок под сообщением,
отправленным через inline-режим.

Поэтому все перерисовки идут через этот модуль: получилось изменить на
месте — хорошо, не получилось — отправляем новое сообщение.
"""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest

from services.tg import is_not_modified

log = logging.getLogger(__name__)

TEXT_LIMIT = 4096
CUT_MARK = "\n\n<i>…список обрезан</i>"


def clip(text: str, limit: int = TEXT_LIMIT) -> str:
    """Подрезать текст под предел Telegram.

    Экран со списком может неожиданно вырасти — от длинных названий каналов
    до подробного ответа Telegram в диагностике. Обрезанный экран лучше, чем
    отказ «message is too long» и отчёт об ошибке на пустом месте.
    """
    if len(text) <= limit:
        return text
    return text[: limit - len(CUT_MARK)] + CUT_MARK


def editable(message) -> bool:
    """Можно ли перерисовать это сообщение на месте.

    Проверяем наличие самого метода, а не тип: именно его нет у недоступного
    сообщения, и именно на нём всё падало.
    """
    return message is not None and hasattr(message, "edit_text")


def photo_of(message):
    """Фото сообщения или None — у недоступного сообщения поля просто нет."""
    return getattr(message, "photo", None)


def is_callback(target) -> bool:
    """Нажатие кнопки отличается от сообщения наличием поля message."""
    return hasattr(target, "message") and hasattr(target, "from_user")


def message_of(target):
    """Сообщение, к которому относится действие. У кнопки его может не быть."""
    return target.message if is_callback(target) else target


def chat_id_of(target) -> int | None:
    chat = getattr(message_of(target), "chat", None)
    return chat.id if chat is not None else None


async def send(target, text: str, reply_markup=None, **kwargs):
    """Отправить новое сообщение туда, откуда пришло нажатие.

    Работает и с обычным сообщением, и с недоступным (у него `answer` есть),
    и с самим CallbackQuery — когда сообщения нет совсем.
    """
    text = clip(text)
    message = message_of(target)

    if message is not None and hasattr(message, "answer"):
        return await message.answer(text, reply_markup=reply_markup, **kwargs)

    # сообщения нет вовсе — пишем человеку напрямую
    bot = getattr(target, "bot", None)
    if is_callback(target) and bot is not None:
        return await bot.send_message(
            target.from_user.id, text, reply_markup=reply_markup, **kwargs
        )

    log.warning("Некуда отправить ответ: %r", type(target).__name__)
    return None


async def edit_or_send(target, text: str, reply_markup=None, **kwargs):
    """Перерисовать на месте, а если нельзя — прислать новым сообщением."""
    text = clip(text)
    message = message_of(target)

    if not editable(message):
        return await send(target, text, reply_markup, **kwargs)

    try:
        return await message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as error:
        if is_not_modified(error):
            return None  # данные те же — перерисовывать нечего
        # сообщение удалили, оно слишком старое или без текста — шлём новое
        log.info("Не смог перерисовать сообщение, отправляю новое: %s", error)
        return await send(target, text, reply_markup, **kwargs)


async def edit_markup(target, reply_markup) -> None:
    """Обновить только кнопки. Нельзя — молча пропускаем: текст уже верный."""
    message = message_of(target)
    if not editable(message):
        return

    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if not is_not_modified(error):
            log.info("Не смог обновить кнопки: %s", error)


__all__ = [
    "clip", "editable", "photo_of", "chat_id_of", "is_callback", "message_of",
    "send", "edit_or_send", "edit_markup",
]
