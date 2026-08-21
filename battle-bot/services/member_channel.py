"""Личный канал участника.

Участник добавляет бота администратором в свой канал — и бот сам публикует
туда его пары с кнопкой «Голосовать за меня». Это честная реклама самого
себя: подписчики идут в бота по ссылке, где всё равно действуют общие правила
(подписка на главный канал, один бесплатный голос на матч).

Публикуется только то, что касается владельца канала: его пара и его итог.
Ничего чужого бот в личный канал не пишет.
"""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from core.models import MatchStatus
from services import links, texts
from services.emoji import is_emoji_rejection
from services.keyboards import GREEN
from services.tg import is_access_lost
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)

# статусы, при которых человек вправе распоряжаться каналом
OWNERS = {"creator", "administrator"}


def enabled(settings: Settings) -> bool:
    return bool(settings.get("member_channels_enabled"))


def from_forward(message: Message) -> tuple[int | None, str | None, str | None, str]:
    """Разобрать пересланный пост: из какого он канала.

    Возвращает (chat_id, title, username, ошибка). Ошибка непустая — показать
    её человеку и ничего не привязывать.
    """
    origin = getattr(message, "forward_origin", None)
    if origin is None:
        return None, None, None, texts.MY_CHANNEL_NOT_A_CHANNEL

    chat = getattr(origin, "chat", None)
    if chat is None:
        # пересылка со скрытым автором: Telegram не отдаёт исходный чат
        return None, None, None, texts.MY_CHANNEL_HIDDEN
    if getattr(chat, "type", None) != "channel":
        return None, None, None, texts.MY_CHANNEL_NOT_A_CHANNEL

    return chat.id, chat.title, chat.username, ""


async def can_publish(bot: Bot, chat_id: int, user_id: int) -> str:
    """Пустая строка — можно публиковать. Иначе текст отказа для человека."""
    try:
        me = await bot.get_chat_member(chat_id=chat_id, user_id=(await bot.me()).id)
    except TelegramAPIError as error:
        log.info("Канал %s недоступен боту: %s", chat_id, error)
        return texts.MY_CHANNEL_NOT_ADMIN

    if me.status != "administrator" or not getattr(me, "can_post_messages", False):
        return texts.MY_CHANNEL_NOT_ADMIN

    try:
        owner = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except TelegramAPIError as error:
        log.info("Не удалось проверить владельца канала %s: %s", chat_id, error)
        return texts.MY_CHANNEL_NOT_YOURS

    if owner.status not in OWNERS:
        return texts.MY_CHANNEL_NOT_YOURS
    return ""


def keyboard(config: Config, match_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Кнопка поста: ведёт голосовать именно за владельца канала."""
    url = links.vote_link(config.bot_username, match_id, user_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Голосовать за меня", url=url, style=GREEN)]
        ]
    )


async def publish_match(
    bot: Bot, repo: Repo, config: Config, settings: Settings, user_id: int, match_id: int,
    emoji_skip: set[int] | None = None,
) -> bool:
    """Опубликовать пару владельца в его канале. False — публиковать некуда."""
    if not enabled(settings):
        return False

    channel = repo.member_channel(user_id)
    if channel is None or not channel["active"]:
        return False

    match = repo.get_match(match_id)
    if match is None or match["status"] != MatchStatus.VOTING.value:
        return False

    slots = repo.match_slots(match_id)
    me = next((slot for slot in slots if slot.user_id == user_id), None)
    if me is None:
        return False

    body = texts.my_channel_post(
        round_no=int(match["round_no"]),
        is_final=bool(match["is_final"]),
        nickname=me.nickname,
        rivals=[slot.nickname for slot in slots if slot.user_id != user_id],
        deadline=datetime.fromisoformat(match["deadline"]),
        vote_url=links.vote_link(config.bot_username, match_id, user_id),
    )
    return await _send(bot, repo, user_id, int(channel["chat_id"]), body,
                       keyboard(config, match_id, user_id), emoji_skip)


async def publish_result(
    bot: Bot, repo: Repo, settings: Settings, user_id: int,
    round_no: int, is_final: bool, ranking, emoji_skip: set[int] | None = None,
) -> bool:
    """Итог раунда в личном канале — с полным счётом, без прикрас."""
    if not enabled(settings):
        return False

    channel = repo.member_channel(user_id)
    if channel is None or not channel["active"]:
        return False

    body = texts.my_channel_result(round_no, is_final, ranking, user_id)
    return await _send(bot, repo, user_id, int(channel["chat_id"]), body, None, emoji_skip)


async def _send(
    bot: Bot, repo: Repo, user_id: int, chat_id: int, body: str, markup,
    emoji_skip: set[int] | None = None,
) -> bool:
    """Отправить в канал.

    Три разных исхода, и путать их нельзя:
    * премиум-эмодзи не приняли — правами это не лечится, отключаем их для
      этого канала и повторяем обычными;
    * доступ потерян — гасим привязку и говорим владельцу;
    * прочий сбой — просто пропускаем этот пост, привязка остаётся живой.
    """
    try:
        await bot.send_message(
            chat_id, body, reply_markup=markup, disable_web_page_preview=True
        )
    except TelegramAPIError as error:
        if emoji_skip is not None and chat_id not in emoji_skip and is_emoji_rejection(error):
            emoji_skip.add(chat_id)
            log.info("Канал %s не принял премиум-эмодзи, повторяю обычными", chat_id)
            return await _send(bot, repo, user_id, chat_id, body, markup, emoji_skip)

        if is_access_lost(error):
            log.info("Канал участника %s недоступен: %s", user_id, error)
            repo.disable_channel(user_id)
            await _warn_owner(bot, user_id)
            return False

        log.warning("Не удалось опубликовать в канале участника %s: %s", user_id, error)
        return False

    repo.bump_channel_posts(user_id)
    return True


async def _warn_owner(bot: Bot, user_id: int) -> None:
    try:
        await bot.send_message(user_id, texts.MY_CHANNEL_LOST)
    except TelegramAPIError:
        pass  # владелец заблокировал бота — молча оставляем канал выключенным
