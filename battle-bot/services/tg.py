"""Мелкие помощники поверх Telegram API."""
from __future__ import annotations


def is_not_modified(error: BaseException) -> bool:
    """Telegram отказался перерисовывать сообщение тем же содержимым.

    Возникает, когда жмут «Обновить», а данные не изменились. Это не поломка,
    а нормальный ответ — показывать пользователю нечего.
    """
    return "not modified" in str(error).lower()
