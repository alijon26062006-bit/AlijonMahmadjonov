"""Помощники поверх Telegram API и разбор его ошибок.

У Telegram есть класс ответов, которые выглядят как ошибка, но поломкой не
являются: человек заблокировал бота, кнопка устарела, сообщение не изменилось.
На тысячах пользователей такое происходит постоянно, поэтому важно отличать
их от настоящих сбоев — иначе админа завалит отчётами о том, что чинить нечего.
"""
from __future__ import annotations

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

# ответы Telegram, которые ничего не требуют от нас
EXPECTED_MARKERS = (
    "not modified",              # перерисовка тем же содержимым
    "message to edit not found",  # сообщение удалили
    "message to delete not found",
    "message can't be deleted",   # старше 48 часов
    "query is too old",           # нажали кнопку на старом сообщении
    "query id is invalid",
    "message is not modified",
    "user is deactivated",        # аккаунт удалён
    "chat not found",             # человек снёс переписку
    "bot was blocked",
    "bot can't initiate conversation",
    "have no rights to send",
    "message thread not found",
)

BLOCKED_MARKERS = (
    "bot was blocked",
    "user is deactivated",
    "chat not found",
    "bot can't initiate conversation",
)


def is_not_modified(error: BaseException) -> bool:
    """Telegram отказался перерисовывать сообщение тем же содержимым.

    Возникает, когда жмут «Обновить», а данные не изменились. Это не поломка,
    а нормальный ответ — показывать пользователю нечего.
    """
    return "not modified" in str(error).lower()


def is_blocked(error: BaseException) -> bool:
    """Писать этому человеку больше нельзя: заблокировал бота или удалил аккаунт."""
    if isinstance(error, TelegramForbiddenError):
        return True
    text = str(error).lower()
    return any(marker in text for marker in BLOCKED_MARKERS)


def is_transient(error: BaseException) -> bool:
    """Сбой сети или сервера — помогает повтор."""
    return isinstance(error, (TelegramNetworkError, TelegramServerError, TelegramRetryAfter))


def is_expected(error: BaseException) -> bool:
    """Обычная жизнь бота, а не то, что нужно чинить."""
    if is_blocked(error) or is_transient(error):
        return True
    if isinstance(error, TelegramBadRequest):
        text = str(error).lower()
        return any(marker in text for marker in EXPECTED_MARKERS)
    return False
