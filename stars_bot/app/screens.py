"""Экран с картинкой: главное меню, раздел игр, каждая игра и регион.

Картинки владелец загружает в панели (🎨 Оформление → 🖼 Картинки),
хранится file_id Telegram в настройке img:<место>. Нет картинки — экран
обычный текстовый, как раньше.

Места: main, games, glory, fam:<игра>, game:<код категории>. У игры без
своей картинки берётся картинка её семьи (Free Fire для Free Fire ID).
"""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InputMediaPhoto

from app import runtime

log = logging.getLogger(__name__)

#: Подпись к фото у Telegram — до 1024 знаков. Длиннее — без картинки.
CAPTION_MAX = 1000


def image(*keys: str | None) -> str:
    """Первая заданная картинка из списка мест."""
    for key in keys:
        if key:
            value = (runtime.get(f"img:{key}") or "").strip()
            if value:
                return value
    return ""


async def show(target, text: str, markup=None, keys: tuple = (), effect: dict | None = None):
    """Показать экран: с картинкой, если она задана, иначе текстом.

    target — сообщение (команда /start) или нажатие кнопки.
    """
    effect = effect or {}
    photo = image(*keys) if len(text) <= CAPTION_MAX else ""
    message = getattr(target, "message", None)       # нажатие кнопки

    if message is None:                              # пришло сообщение
        if photo:
            try:
                return await target.answer_photo(photo, caption=text,
                                                 reply_markup=markup, **effect)
            except TelegramBadRequest as exc:
                log.warning("Картинка %s не отправилась: %s", keys, exc)
        return await target.answer(text, reply_markup=markup, **effect)

    if not photo:
        # Текстовый экран. Если сейчас на экране фото, правку текста
        # переделает в новое сообщение PhotoTextGuard.
        return await message.edit_text(text, reply_markup=markup)

    if getattr(message, "photo", None):
        try:
            return await message.edit_media(
                InputMediaPhoto(media=photo, caption=text), reply_markup=markup)
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return None
            log.info("Картинку не заменить правкой (%s) — шлю заново", exc)
    try:
        await message.delete()
    except TelegramAPIError:
        pass                                         # старое — не беда
    try:
        return await message.answer_photo(photo, caption=text, reply_markup=markup)
    except TelegramBadRequest as exc:
        log.warning("Картинка %s не отправилась: %s", keys, exc)
        return await message.answer(text, reply_markup=markup)
