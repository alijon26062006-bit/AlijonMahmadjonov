"""Общий перехватчик ошибок.

Последний рубеж: сюда попадает всё, что не поймали сами обработчики. Задача —
чтобы человек никогда не оставался без ответа, админ узнал о проблеме, а бот
продолжил работать.
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ErrorEvent, Message

from config import Config
from services.retry import TRANSIENT
from services.tg import is_blocked, is_expected
from services.validation import InputError

log = logging.getLogger(__name__)
router = Router(name="errors")

TO_USER = (
    "⚠️ <b>Что-то пошло не так</b>\n\n"
    "Ошибка записана, админ уже знает. Попробуйте ещё раз или напишите /start."
)

TRACEBACK_LIMIT = 2500  # запас до предела сообщения Telegram

TO_USER_NETWORK = (
    "📡 <b>Сеть подвела</b>\n\n"
    "Telegram не ответил вовремя. Повторите — обычно со второго раза проходит."
)

# одинаковые ошибки не должны заваливать админа: одна весточка в такой период
REPORT_COOLDOWN = timedelta(minutes=15)
_reported: dict[str, datetime] = {}


def _should_report(error: BaseException) -> bool:
    """Не повторять админу один и тот же отчёт чаще, чем раз в четверть часа."""
    signature = f"{type(error).__name__}:{str(error)[:120]}"
    now = datetime.now(timezone.utc)
    last = _reported.get(signature)
    if last is not None and now - last < REPORT_COOLDOWN:
        return False
    _reported[signature] = now
    return True


def _extract(event: ErrorEvent) -> tuple[Message | None, CallbackQuery | None]:
    update = event.update
    return getattr(update, "message", None), getattr(update, "callback_query", None)


def _describe(event: ErrorEvent) -> str:
    """Что именно человек делал, когда всё сломалось."""
    message, callback = _extract(event)
    if callback:
        return f"кнопка <code>{escape(str(callback.data))}</code>"
    if message and message.text:
        return f"сообщение <code>{escape(message.text[:80])}</code>"
    return "неизвестное действие"


def _who(event: ErrorEvent) -> str:
    message, callback = _extract(event)
    user = (callback or message).from_user if (callback or message) else None
    if not user:
        return "неизвестный пользователь"
    handle = f"@{user.username}" if user.username else user.full_name
    return f"{escape(handle)} (<code>{user.id}</code>)"


@router.errors()
async def catch_everything(event: ErrorEvent, bot: Bot, config: Config, repo=None) -> bool:
    """Вернуть True — значит ошибка обработана и бот продолжает работу."""
    message, callback = _extract(event)
    error = event.exception

    # неверный ввод — это не поломка, а разговор с человеком
    if isinstance(error, InputError):
        await _reply(message, callback, f"⚠️ {error}")
        return True

    # сетевой сбой Telegram: повтор уже пробовали, кода это не касается
    if isinstance(error, TRANSIENT):
        log.warning("Сетевой сбой Telegram: %s", error)
        await _reply(message, callback, TO_USER_NETWORK)
        return True

    # обычная жизнь бота: человек заблокировал, кнопка устарела, чат удалён.
    # Чинить нечего, отчёт админу только зашумил бы почту.
    if is_expected(error):
        if is_blocked(error) and repo is not None:
            _remember_blocked(event, repo)
        log.info("Ожидаемый ответ Telegram: %s", error)
        return True

    log.exception("Необработанная ошибка при обработке апдейта", exc_info=error)
    await _reply(message, callback, TO_USER)
    if _should_report(error):
        await _tell_admins(bot, config, event, error)
    return True


def _remember_blocked(event: ErrorEvent, repo) -> None:
    """Запомнить, что человек закрыл дверь: больше ему не пишем."""
    message, callback = _extract(event)
    user = (callback or message).from_user if (callback or message) else None
    if user is not None:
        repo.mark_blocked(user.id)


async def _reply(message: Message | None, callback: CallbackQuery | None, text: str) -> None:
    try:
        if callback:
            await callback.answer()
            await callback.message.answer(text)
        elif message:
            await message.answer(text)
    except TelegramAPIError as send_error:
        # не смогли сообщить об ошибке — тем более не о чем тревожиться
        log.info("Не смог сообщить пользователю об ошибке: %s", send_error)


async def _tell_admins(bot: Bot, config: Config, event: ErrorEvent, error: BaseException) -> None:
    trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    report = (
        f"🛠 <b>Ошибка в боте</b>\n\n"
        f"Кто: {_who(event)}\n"
        f"Что: {_describe(event)}\n"
        f"Тип: <code>{escape(type(error).__name__)}</code>\n\n"
        f"<pre>{escape(trace[-TRACEBACK_LIMIT:])}</pre>"
    )
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, report)
        except TelegramAPIError:
            log.warning("Не смог отправить отчёт админу %s", admin_id)
