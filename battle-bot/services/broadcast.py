"""Рассылка: одно сообщение любого типа всем пользователям бота.

Telegram различает десяток видов сообщений, и у каждого свой метод отправки.
Здесь они собраны в одном месте, поэтому админ может разослать что угодно —
фото, видео, кружок, голосовое, стикер или просто текст, — а сверху навесить
кнопки со ссылками.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

log = logging.getLogger(__name__)

# как называется поле в сообщении -> каким методом это отправлять
SENDERS = {
    "photo": "send_photo",
    "video": "send_video",
    "animation": "send_animation",
    "document": "send_document",
    "audio": "send_audio",
    "voice": "send_voice",
    "video_note": "send_video_note",
    "sticker": "send_sticker",
}

# что умеет нести подпись; стикер и кружок — нет
CAPTIONABLE = {"photo", "video", "animation", "document", "audio", "voice"}

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096

HUMAN = {
    "photo": "фото",
    "video": "видео",
    "animation": "гифка",
    "document": "файл",
    "audio": "аудио",
    "voice": "голосовое",
    "video_note": "кружок",
    "sticker": "стикер",
}


@dataclass
class Draft:
    """Черновик рассылки."""

    media_type: str | None = None
    file_id: str | None = None
    text: str | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.file_id and not self.text

    @property
    def caption_fits(self) -> bool:
        """Влезает ли текст в подпись к медиа."""
        return (
            self.media_type in CAPTIONABLE
            and len(self.text or "") <= CAPTION_LIMIT
        )

    def describe(self) -> str:
        parts = []
        if self.media_type:
            parts.append(HUMAN.get(self.media_type, self.media_type))
        if self.text:
            parts.append(f"текст {len(self.text)} симв.")
        if self.buttons:
            parts.append(f"кнопок: {len(self.buttons)}")
        return " · ".join(parts) if parts else "пусто"

    def keyboard(self) -> InlineKeyboardMarkup | None:
        if not self.buttons:
            return None
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label, url=url)] for label, url in self.buttons
            ]
        )


def extract_media(message: Message) -> tuple[str, str] | None:
    """Вытащить из сообщения вид медиа и его file_id."""
    for field_name in SENDERS:
        value = getattr(message, field_name, None)
        if not value:
            continue
        if field_name == "photo":
            return field_name, value[-1].file_id  # самый крупный размер
        return field_name, value.file_id
    return None


@dataclass
class Report:
    sent: int = 0
    blocked: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.sent + self.blocked + self.failed


async def deliver(bot: Bot, draft: Draft, chat_id: int) -> None:
    """Отправить черновик одному человеку.

    Медиа с подписью уходит одним сообщением. Стикер и кружок подпись не несут,
    поэтому текст к ним отправляется следом отдельным сообщением.
    """
    markup = draft.keyboard()

    if draft.file_id and draft.media_type:
        send = getattr(bot, SENDERS[draft.media_type])
        with_caption = draft.caption_fits and draft.text

        payload = {"chat_id": chat_id, draft.media_type: draft.file_id}
        if with_caption:
            payload["caption"] = draft.text
            payload["reply_markup"] = markup
        elif not draft.text:
            payload["reply_markup"] = markup
        await send(**payload)

        if draft.text and not with_caption:
            await bot.send_message(
                chat_id=chat_id,
                text=draft.text,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        return

    await bot.send_message(
        chat_id=chat_id,
        text=draft.text or "",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def run(
    bot: Bot,
    draft: Draft,
    user_ids: list[int],
    delay: float = 0.05,
    on_progress=None,
    every: int = 25,
) -> Report:
    """Разослать черновик списку людей.

    Заблокировавшие бота считаются отдельно — это не сбой, а обычное дело.
    """
    report = Report()
    for index, user_id in enumerate(user_ids, start=1):
        try:
            await deliver(bot, draft, user_id)
            report.sent += 1
        except TelegramForbiddenError:
            report.blocked += 1
        except TelegramRetryAfter as error:
            log.warning("Лимит рассылки, ждём %s c", error.retry_after)
            await asyncio.sleep(error.retry_after + 1)
            try:
                await deliver(bot, draft, user_id)
                report.sent += 1
            except TelegramAPIError:
                report.failed += 1
        except TelegramAPIError as error:
            log.info("Рассылка не дошла до %s: %s", user_id, error)
            report.failed += 1

        if on_progress and index % every == 0:
            await on_progress(index, len(user_ids), report)
        await asyncio.sleep(delay)
    return report
