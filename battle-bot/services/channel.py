"""Публикация матчей в канал и дописывание итогов."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from config import Config
from core.models import Slot
from services import links, texts
from services.emoji import is_emoji_rejection
from storage.repo import Repo

log = logging.getLogger(__name__)


class ChannelPublisher:
    def __init__(
        self, bot: Bot, repo: Repo, config: Config, emoji_skip: set[int] | None = None
    ) -> None:
        self.bot = bot
        self.repo = repo
        self.config = config
        # общий с middleware набор чатов, где премиум-эмодзи не подставляются:
        # добавив сюда канал, мы разом выключаем их для всех будущих постов
        self.emoji_skip = emoji_skip if emoji_skip is not None else set()

    async def publish_match(self, match_id: int) -> int | None:
        """Опубликовать пост матча и запомнить message_id."""
        match = self.repo.get_match(match_id)
        if match is None:
            return None
        slots = self.repo.match_slots(match_id)
        deadline = datetime.fromisoformat(match["deadline"])

        text = texts.channel_post(
            round_no=match["round_no"],
            is_final=bool(match["is_final"]),
            slots=slots,
            prizes=self.config.prizes,
            deadline=deadline,
            vote_url=links.vote_link(self.config.bot_username, match_id),
            join_url=links.join_link(self.config.bot_username),
        )

        message = await self._send(text)
        if message is None:
            return None
        self.repo.set_match_message(match_id, message.message_id)
        return message.message_id

    async def publish_results(self, match_id: int, ranking: list[Slot], tie_broken: bool) -> None:
        """Дописать итог под постом матча."""
        match = self.repo.get_match(match_id)
        if match is None or match["message_id"] is None:
            return
        text = texts.channel_result(
            round_no=match["round_no"],
            is_final=bool(match["is_final"]),
            ranking=ranking,
            tie_broken=tie_broken,
        )
        await self._send(text, reply_to=match["message_id"])

    async def announce(self, text: str) -> None:
        await self._send(text)

    async def _send(self, text: str, reply_to: int | None = None):
        """Отправка с уважением к лимитам Telegram: пауза между постами,
        повтор после 429 и откат на обычные эмодзи, если премиум не приняли."""
        for attempt in range(3):
            try:
                message = await self.bot.send_message(
                    chat_id=self.config.channel_id,
                    text=text,
                    reply_to_message_id=reply_to,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(self.config.publish_delay)
                return message
            except TelegramRetryAfter as error:
                log.warning("Лимит канала, ждём %s c", error.retry_after)
                await asyncio.sleep(error.retry_after + 1)
            except TelegramAPIError as error:
                if self._disable_channel_emoji(error):
                    continue  # тот же текст, но уже без премиум-эмодзи
                log.error("Не удалось отправить пост в канал (попытка %s): %s", attempt + 1, error)
                # выдержка растёт с каждой попыткой и опирается на ту же
                # настройку, что и пауза между постами
                await asyncio.sleep(self.config.publish_delay * 2 * (attempt + 1))
        return None

    def _disable_channel_emoji(self, error: TelegramAPIError) -> bool:
        """Отключить премиум-эмодзи для канала, если Telegram отказал из-за них.

        Купленного на Fragment username у бота может не быть, а проверить это
        заранее нечем. Поэтому первый отказ считаем ответом и дальше постим
        обычными эмодзи — батл важнее оформления.
        """
        channel = self.config.channel_id
        if channel in self.emoji_skip or not is_emoji_rejection(error):
            return False

        self.emoji_skip.add(channel)
        log.warning(
            "Telegram не принял премиум-эмодзи в канале (%s). "
            "Для постов канала они отключены — нужен купленный на Fragment "
            "username. Повторяю обычными.",
            error,
        )
        return True
