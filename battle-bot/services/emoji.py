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
* отправлять custom emoji может бот, купивший дополнительный username на
  Fragment, либо — в личных чатах, группах и супергруппах — бот, у владельца
  которого есть Telegram Premium. На посты в канал второе правило НЕ
  распространяется: там нужен именно Fragment-username. Заранее это не
  проверить, поэтому по умолчанию бот пробует отправить премиум-эмодзи в
  канал и при отказе Telegram один раз повторяет обычными — и дальше в канал
  их уже не шлёт (см. ChannelPublisher);
* на кнопках премиум-эмодзи показывается через отдельное поле
  ``icon_custom_emoji_id`` — одна иконка перед подписью, внутрь текста кнопки
  её не вставить.
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

# по этим словам узнаём отказ Telegram именно из-за премиум-эмодзи
REJECTION_MARKERS = ("custom_emoji", "custom emoji", "emoji")


def is_emoji_rejection(error: object) -> bool:
    """Telegram отказал из-за премиум-эмодзи, а не по другой причине?"""
    text = str(error).lower()
    return any(marker in text for marker in REJECTION_MARKERS)


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


def leading_emoji(text: str, table: dict[str, str]) -> tuple[str, str | None]:
    """Отделить эмодзи в начале подписи кнопки от текста.

    Telegram показывает премиум-эмодзи на кнопке отдельным полем
    ``icon_custom_emoji_id``, поэтому символ убираем из подписи и возвращаем
    его id. Если эмодзи нет в таблице, подпись остаётся как была.
    """
    if not table or not text:
        return text, None
    first = text[0]
    emoji_id = table.get(first)
    if not emoji_id:
        return text, None
    return text[1:].lstrip(), emoji_id


def save_table(path: str | Path, table: dict[str, str]) -> None:
    """Записать таблицу на диск, сохранив порядок символов."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect_ids(text: str | None, entities) -> dict[str, str]:
    """Вытащить из сообщения пары «символ -> custom_emoji_id».

    Так владелец бота узнаёт id: присылает боту сообщение с премиум-эмодзи
    (или пересылает чужое), Telegram отдаёт их в entities.
    """
    if not text or not entities:
        return {}
    found: dict[str, str] = {}
    for entity in entities:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            char = entity.extract_from(text)
            if char:
                found[char] = entity.custom_emoji_id
    return found


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    """Подменяет эмодзи в тексте любого исходящего сообщения."""

    def __init__(self, table: dict[str, str], skip_chats: set[int] | None = None) -> None:
        self.table = table
        # Telegram отклоняет custom emoji в канале, если у бота нет
        # Fragment-username. Пропускать такой чат безопаснее, чем сорвать батл.
        self.skip_chats = skip_chats or set()

    async def __call__(self, make_request, bot: Bot, method):
        if self.table and getattr(method, "chat_id", None) not in self.skip_chats:
            for field in TEXT_FIELDS:
                value = getattr(method, field, None)
                if isinstance(value, str):
                    setattr(method, field, render(value, self.table))
        return await make_request(bot, method)
