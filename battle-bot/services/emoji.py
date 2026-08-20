"""Премиум-эмодзи (custom emoji).

Telegram показывает премиум-эмодзи через HTML-тег
``<tg-emoji emoji-id="...">запасной символ</tg-emoji>``.

Чтобы не расставлять теги по всем текстам вручную, подмена делается один раз
на выходе — middleware перехватывает исходящие сообщения и заменяет обычные
символы на премиум по таблице из JSON-файла. Тексты в коде остаются обычными,
а таблицу можно править без перезаписи логики.

Ограничения Telegram, о которых стоит помнить:

* подписи кнопок премиум-эмодзи не поддерживают — там всегда обычные символы,
  поэтому middleware трогает только текст сообщений;
* отправлять custom emoji может лишь бот, купивший дополнительный username
  на Fragment. Без этого Telegram вернёт ошибку, поэтому при пустой таблице
  подмена просто не включается.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware

log = logging.getLogger(__name__)

# участки, внутри которых подменять нельзя: уже готовый тег или HTML-атрибут
PROTECTED = re.compile(r"<tg-emoji\b[^>]*>.*?</tg-emoji>|<[^>]+>", re.DOTALL)

TEXT_FIELDS = ("text", "caption")


def load_table(path: str | Path) -> dict[str, str]:
    """Прочитать таблицу «символ -> emoji_id». Пустые значения игнорируются."""
    file = Path(path)
    if not file.exists():
        return {}

    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        log.error("Не удалось прочитать %s: %s — премиум-эмодзи отключены", file, error)
        return {}

    table = {
        char: str(emoji_id).strip()
        for char, emoji_id in raw.items()
        if str(emoji_id).strip() and not str(emoji_id).startswith("<")
    }
    if table:
        log.info("Премиум-эмодзи: подключено %s символов из %s", len(table), file)
    return table


def wrap(char: str, emoji_id: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'


def render(text: str, table: dict[str, str]) -> str:
    """Заменить обычные эмодзи на премиум, не трогая HTML-теги и ссылки."""
    if not table or not text:
        return text

    def substitute(chunk: str) -> str:
        for char, emoji_id in table.items():
            if char in chunk:
                chunk = chunk.replace(char, wrap(char, emoji_id))
        return chunk

    result: list[str] = []
    position = 0
    for match in PROTECTED.finditer(text):
        result.append(substitute(text[position:match.start()]))
        result.append(match.group(0))  # теги оставляем как есть
        position = match.end()
    result.append(substitute(text[position:]))
    return "".join(result)


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет эмодзи в тексте любого исходящего сообщения."""

    def __init__(self, table: dict[str, str]) -> None:
        self.table = table

    async def __call__(self, make_request, bot: Bot, method):
        if self.table:
            for field in TEXT_FIELDS:
                value = getattr(method, field, None)
                if isinstance(value, str):
                    setattr(method, field, render(value, self.table))
        return await make_request(bot, method)
