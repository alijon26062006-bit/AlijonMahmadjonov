"""Проверка того, что вводит человек.

Задача простая: чтобы бот никогда не падал и никогда не молчал. На любой
неверный ввод человек получает понятное объяснение — что не так, каким должно
быть значение и пример.
"""
from __future__ import annotations

from datetime import time


class InputError(ValueError):
    """Ввод не подошёл. Текст исключения показывается человеку как есть."""


def _clean(raw: str) -> str:
    return (raw or "").strip()


def as_int(raw: str, *, minimum: int | None = None, maximum: int | None = None,
           example: str = "100") -> int:
    """Целое число с проверкой границ."""
    text = _clean(raw)
    if not text:
        raise InputError(f"Пустое значение. Пришлите число, например <code>{example}</code>.")

    # частая опечатка: пробелы или запятая внутри числа
    normalised = text.replace(" ", "").replace(",", ".")
    try:
        value = int(normalised)
    except ValueError:
        if normalised.replace(".", "", 1).isdigit():
            raise InputError(
                f"Нужно целое число, а «{text}» — дробное. "
                f"Например: <code>{example}</code>."
            ) from None
        raise InputError(
            f"Нужно число, а пришло «{text}». Например: <code>{example}</code>."
        ) from None

    if minimum is not None and value < minimum:
        raise InputError(f"Слишком мало: {value}. Минимум — {minimum}.")
    if maximum is not None and value > maximum:
        raise InputError(f"Слишком много: {value}. Максимум — {maximum}.")
    return value


def as_int_list(raw: str, *, minimum: int | None = None, maximum: int | None = None,
                max_items: int | None = None, example: str = "1000,500,250") -> list[int]:
    """Список чисел через запятую."""
    text = _clean(raw)
    if not text:
        raise InputError(f"Пустое значение. Пример: <code>{example}</code>.")

    parts = [part for part in text.replace(";", ",").split(",") if part.strip()]
    if not parts:
        raise InputError(f"Не нашёл ни одного числа. Пример: <code>{example}</code>.")
    if max_items and len(parts) > max_items:
        raise InputError(f"Слишком много значений: {len(parts)}. Максимум — {max_items}.")

    values = []
    for index, part in enumerate(parts, start=1):
        try:
            values.append(as_int(part, minimum=minimum, maximum=maximum))
        except InputError as error:
            raise InputError(f"Значение №{index}: {error}") from None
    return values


def as_times(raw: str, *, max_items: int = 12,
             example: str = "18:00,19:30,21:00") -> list[time]:
    """Список времён через запятую."""
    text = _clean(raw)
    if not text:
        raise InputError(f"Пустое значение. Пример: <code>{example}</code>.")

    parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    if not parts:
        raise InputError(f"Не нашёл ни одного времени. Пример: <code>{example}</code>.")
    if len(parts) > max_items:
        raise InputError(f"Слишком много значений: {len(parts)}. Максимум — {max_items}.")

    result = []
    for part in parts:
        hours, _, minutes = part.partition(":")
        if not hours.isdigit() or (minutes and not minutes.isdigit()):
            raise InputError(
                f"«{part}» не похоже на время. Формат ЧЧ:ММ, например <code>18:00</code>."
            )
        hour, minute = int(hours), int(minutes or 0)
        if not 0 <= hour <= 23:
            raise InputError(f"В «{part}» неверный час: {hour}. Допустимо 0–23.")
        if not 0 <= minute <= 59:
            raise InputError(f"В «{part}» неверные минуты: {minute}. Допустимо 0–59.")
        result.append(time(hour, minute))

    if len(set(result)) != len(result):
        raise InputError("Одно и то же время указано дважды.")
    return sorted(result)


def as_username(raw: str) -> str:
    """@ник или просто ник."""
    text = _clean(raw).lstrip("@")
    if not text:
        raise InputError("Пустой ник. Пришлите, например, <code>@username</code>.")
    if len(text) > 32 or not all(ch.isalnum() or ch == "_" for ch in text):
        raise InputError(
            f"«{raw.strip()}» не похоже на ник Telegram. "
            "Ник состоит из латиницы, цифр и подчёркиваний."
        )
    return text


def as_user_id(raw: str) -> int:
    text = _clean(raw).lstrip("@")
    if not text.isdigit():
        raise InputError(
            f"Нужен числовой ID, а пришло «{_clean(raw)}». "
            "Узнать свой ID можно у @userinfobot."
        )
    return int(text)
