"""Правка текста у сообщения-картинки: удалить его и прислать текст новым.

Главное меню и экраны игр теперь бывают с картинкой. Но почти все
остальные экраны перерисовываются правкой текста, а у сообщения с фото
текста нет — Telegram отвечает «there is no text in the message to edit»,
и кнопка выглядит мёртвой. Чинить в каждом из сотни мест нельзя, поэтому
здесь: такая правка превращается в «удалить картинку + прислать текст».
"""
from __future__ import annotations

import logging

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage

log = logging.getLogger(__name__)

MARK = "no text in the message"


class PhotoTextGuard(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            if not isinstance(method, EditMessageText) or MARK not in str(exc).lower() \
                    or not method.chat_id or not method.message_id:
                raise
            try:
                await bot(DeleteMessage(chat_id=method.chat_id, message_id=method.message_id))
            except TelegramAPIError:
                pass
            return await bot(SendMessage(
                chat_id=method.chat_id, text=method.text, parse_mode=method.parse_mode,
                entities=method.entities, reply_markup=method.reply_markup,
                link_preview_options=method.link_preview_options,
            ))
